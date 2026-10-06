import re

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from cmnsd.edit.log import log_change
from cmnsd.views.api.response import api_response, api_view

from ..models import Content
from ..uploads import create_upload, file_date


class UploadView(PermissionRequiredMixin, TemplateView):
  """content/new/ - add content: a dropzone (cmnsd.js upload.js) that sends
  each file on its own to content/new/upload/. Every file becomes a draft
  in the uploader's inbox; one that's in the archive already is pointed
  out instead. Needs content.add_content."""
  permission_required = 'content.add_content'
  template_name = 'content/upload.html'


@api_view
@require_POST
def content_upload(request):
  """POST content/new/upload/ (multipart, `file`) - one file: a draft item
  (content/uploads.py). Answers in the cmnsd API shape:
  {created: {token, name, url, thumb}} or {duplicate: {...}} - a file
  that's in the archive already (by checksum); `duplicate` has a url only
  when this user may see that item. 403 without content.add_content."""
  if not (request.user.is_authenticated and request.user.has_perm('content.add_content')):
    return api_response(request, status=403, error=_("You may not add content."), errors={'permission': True})
  uploaded = request.FILES.get('file')
  if uploaded is None:
    return api_response(request, status=400, error=_("No file sent."), errors={'request': 'file'})
  content, duplicate = create_upload(uploaded, request.user)
  if duplicate is not None:
    visible = Content.objects.visible_to(request).filter(pk=duplicate.pk).exists()
    return api_response(request, duplicate={
      'name': str(duplicate) if visible else '',
      'url': duplicate.get_absolute_url() if visible else '',
      'deleted': duplicate.status == Content.Status.DELETED,
    })
  log_change(request, content, "Uploaded")
  return api_response(request, obj=content, created={
    'token': content.token, 'name': str(content), 'url': content.get_absolute_url(),
    'thumb': reverse('content:thumbnail', args=[content.token, 'avatar']) if content.media_type == 'image' else '',
  })


def inbox_items(user):
  """A user's drafts - their uploads not yet published - oldest first (a
  queryset; for the inbox's own order see inbox_order)."""
  return Content.objects.filter(user=user, status=Content.Status.CONCEPT).order_by('date_created', 'pk')


def draft_people(user):
  """People this user added that aren't published yet."""
  from people.models import Person
  return Person.objects.filter(user=user, status=Person.Status.CONCEPT).order_by('date_created', 'pk')


def draft_events(user):
  """Events this user added that aren't published yet."""
  from events.models import Event
  return Event.objects.filter(user=user, status=Event.Status.CONCEPT).order_by('date_created', 'pk')


def others_drafts(request):
  """For staff: everyone else's drafts this viewer may see (a draft its
  owner made private stays theirs) - in case they forget them. [{owner,
  content, people, events, count, oldest}], the longest-waiting first."""
  from cmnsd.models.access import filter_accessible
  from events.models import Event
  from people.models import Person
  user = request.user
  if not (user and user.is_authenticated and user.is_staff):
    return []
  sources = (
    ('content', Content.objects.visible_to(request).filter(status=Content.Status.CONCEPT)),
    ('people', filter_accessible(Person.objects.filter(status=Person.Status.CONCEPT), request)),
    ('events', filter_accessible(Event.objects.filter(status=Event.Status.CONCEPT), request).prefetch_related('people', 'places__parent')),
  )
  groups = {}
  for kind, queryset in sources:
    for obj in queryset.exclude(user=user).select_related('user__person').order_by('date_created', 'pk'):
      group = groups.setdefault(obj.user_id, {'owner': obj.user, 'content': [], 'people': [], 'events': [], 'oldest': obj.date_created})
      group[kind].append(obj)
      group['oldest'] = min(group['oldest'], obj.date_created)
  for group in groups.values():
    group['count'] = len(group['content']) + len(group['people']) + len(group['events'])
  return sorted(groups.values(), key=lambda group: group['oldest'])


def inbox_total(user):
  """Everything in a user's inbox: their draft content, people and events."""
  if not (user and user.is_authenticated):
    return 0
  return inbox_items(user).count() + draft_people(user).count() + draft_events(user).count()


def _natural(text):
  """'page 10' after 'page 2': the numbers in a name compared as numbers."""
  return [int(part) if part.isdigit() else part.casefold() for part in re.split(r'(\d+)', text or '')]


def inbox_order(items):
  """The inbox's order: by upload batch (the minute it arrived), and within
  a batch by file name, numbers as numbers - so a scanner's "page 1" ...
  "page 18" read in order, also when the browser sent them otherwise."""
  return sorted(items, key=lambda item: (
    item.date_created.replace(second=0, microsecond=0), _natural(item.original_filename or item.name), item.pk,
  ))


class InboxView(PermissionRequiredMixin, TemplateView):
  """content/inbox/ - your drafts: content, oldest first (and people and
  events you added that aren't published yet, below): open one to describe it
  (its page, in edit mode - "next in inbox" goes on), publish it and it
  leaves the inbox. Select several and "make these one item": the first
  becomes the whole, the others its parts in this order (content.parts
  tools afterwards). Needs content.add_content or people.add_person - anyone
  who adds to the archive has drafts to find here."""
  template_name = 'content/inbox.html'

  def has_permission(self):
    user = self.request.user
    return user.has_perm('content.add_content') or user.has_perm('people.add_person')

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    items = inbox_order(inbox_items(self.request.user).select_related('parent'))
    for item in items:
      item.file_date = file_date(item)
    context['items'] = items
    context['people'] = list(draft_people(self.request.user))
    context['events'] = list(draft_events(self.request.user).prefetch_related('people', 'places__parent'))
    context['total'] = len(items) + len(context['people']) + len(context['events'])
    context['others_drafts'] = others_drafts(self.request)   # staff: other people's drafts
    return context


@require_POST
def inbox_group(request):
  """POST content/inbox/group/ (tokens=...) - the selected drafts become
  one item: the first the whole, the others its parts, in the inbox's
  order. Only the user's own drafts. Back to the inbox, with a message."""
  if not (request.user.is_authenticated and request.user.has_perm('content.change_content')):
    raise Http404
  tokens = request.POST.getlist('tokens')
  chosen = {item.token: item for item in inbox_items(request.user).filter(token__in=tokens)}
  ordered = [item for item in inbox_order(inbox_items(request.user)) if item.token in chosen]
  if len(ordered) < 2:
    messages.warning(request, _("Choose at least two to make one item."))
    return redirect('content:inbox')
  whole, parts = ordered[0], ordered[1:]
  try:
    whole.make_parts_of(parts)
  except ValidationError as error:
    messages.error(request, ' '.join(error.messages))
    return redirect('content:inbox')
  log_change(request, whole, f"Made one item with {len(parts)} part(s) (inbox)")
  messages.success(request, _("“%(whole)s” now has %(count)s parts.") % {'whole': whole, 'count': len(parts)})
  return redirect('content:inbox')
