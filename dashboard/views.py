from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _, ngettext
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django_sendfile import sendfile

from content.views.upload import others_drafts

from . import accounts, blocks, housekeeping


class DashboardView(TemplateView):
  """/ - the dashboard: where you land. For everyone: what happened on this
  day (or the coming week), what's recently added, the conversation, one
  item from the archive, the archive in numbers, and your own record. For
  someone who edits also their work - the inbox (with a dropzone), open
  notes - and the loose ends. Each block only what this viewer may see
  (dashboard/blocks.py). Signed out: only a welcome, sign in and
  request an account - nothing advertised."""
  template_name = 'dashboard/dashboard.html'

  def get(self, request, *args, **kwargs):
    # "Another" from the archive (cmnsd.js list.js): only that block, as JSON.
    if request.user.is_authenticated and request.headers.get('x-requested-with') == 'XMLHttpRequest':
      from django.template.loader import render_to_string
      from cmnsd.views.api.response import api_response
      html = render_to_string('dashboard/_random.html', {'random_item': blocks.from_the_archive(request)}, request=request)
      return api_response(request, html=html)
    return super().get(request, *args, **kwargs)

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    request = self.request
    if not request.user.is_authenticated:
      # Signed out: a welcome and a way in, nothing else.
      from django.conf import settings
      context['approval'] = getattr(settings, 'CMNSD_REGISTRATION_REQUIRES_APPROVAL', False)
      return context
    anniversaries, anniversaries_label = blocks.on_this_day(request)
    context.update({
      'anniversaries': anniversaries,
      'anniversaries_label': anniversaries_label,
      'recent': blocks.recently_added(request),
      'comments': blocks.conversation(request),
      'random_item': blocks.from_the_archive(request),
      'numbers': blocks.numbers(request),
      'work': blocks.your_work(request),
      'loose_ends': blocks.loose_ends(request),
      'you': blocks.you(request),
      # Staff: other people's drafts waiting, counted on the inbox block.
      'others_drafts': sum(group['count'] for group in others_drafts(request)),
      'accounts': (
        {'waiting': list(accounts.waiting()[:5]), 'active': accounts.activity()[:5]}
        if accounts.may_manage_accounts(request.user) else None
      ),
    })
    return context


class LooseEndView(TemplateView):
  """dashboard/loose-ends/<name>/ - the items behind one loose end (people
  without a birth, photos without people, ...) - for someone who edits,
  each linking to where it's fixed, or "fine as it is" (a POST: dismissed
  from this loose end, dashboard.LooseEndDismissal). ?dismissed=1: the
  dismissed ones, with who, when and why, each to restore."""
  template_name = 'dashboard/loose_end.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    name = kwargs['name']
    if name not in blocks.LOOSE_ENDS or not blocks.is_editor(self.request.user):
      raise Http404
    context.update({'name': name, 'label': blocks.LOOSE_ENDS[name]})
    if name == 'marked':
      context['marked'] = blocks.marked_loose_ends(self.request)
      context['items'] = [obj for objects in context['marked'].values() for obj in objects]
      return context
    from .progress import bar
    context['bar'] = bar(name, self.request)
    show_dismissed = self.request.GET.get('dismissed') == '1'
    items = blocks.loose_end_items(name, self.request, dismissed=show_dismissed)
    if items is None:
      raise Http404
    context['items'] = list(items.distinct()[:300])
    context['show_dismissed'] = show_dismissed
    context['dismissed_count'] = blocks.loose_end_items(name, self.request, dismissed=True).distinct().count()
    if show_dismissed:
      # Who, when and why, on each item.
      from django.contrib.contenttypes.models import ContentType
      from .models import LooseEndDismissal
      rows = LooseEndDismissal.objects.filter(
        name=name, content_type=ContentType.objects.get_for_model(items.model),
        object_id__in=[item.pk for item in context['items']],
      ).select_related('user')
      by_id = {row.object_id: row for row in rows}
      for item in context['items']:
        item.dismissal = by_id.get(item.pk)
      return context
    if name == 'undated-events':
      # Each person's together: what's undated in one life, side by side.
      context['items'] = blocks.undated_by_person(items.distinct().filter(pk__in=[e.pk for e in context['items']]), self.request)
    return context


  def post(self, request, *args, **kwargs):
    """Dismiss an item from this loose end ("fine as it is", with an
    optional note) or restore it - only an item this loose end holds for
    this viewer (checked again here, not trusted from the form)."""
    from django.contrib.contenttypes.models import ContentType
    from django.urls import reverse
    from .models import LooseEndDismissal
    name = kwargs['name']
    if not blocks.DISMISSABLE(name) or not blocks.is_editor(request.user):
      raise Http404
    restore = request.POST.get('action') == 'restore'
    items = blocks.loose_end_items(name, request, dismissed=restore)
    try:
      pk = int(request.POST.get('object_id', ''))
    except ValueError:
      raise Http404
    item = items.filter(pk=pk).first()
    if item is None:
      raise Http404
    content_type = ContentType.objects.get_for_model(items.model)
    if restore:
      LooseEndDismissal.objects.filter(name=name, content_type=content_type, object_id=pk).delete()
      messages.success(request, _("Back on the list."))
    else:
      LooseEndDismissal.objects.get_or_create(
        name=name, content_type=content_type, object_id=pk,
        defaults={'user': request.user, 'note': request.POST.get('note', '').strip()[:255]},
      )
      messages.success(request, _("Off the list - fine as it is."))
    url = reverse('dashboard:loose_end', args=[name])
    return redirect(f'{url}?dismissed=1' if restore else url)


class HousekeepingView(TemplateView):
  """dashboard/housekeeping/ - the archive's storage, checked by eye
  (dashboard/housekeeping.py): an overview of counts in groups - to review,
  files, tags and places - and dashboard/housekeeping/<section>/, one
  section's list (housekeeping/<section>.html). Staff who may delete content
  only. A POST of a selection shows what exactly would go
  (housekeeping_confirm.html); only a POST with confirm=1 deletes, and then
  it's back to the section."""
  template_name = 'dashboard/housekeeping.html'

  def dispatch(self, request, *args, **kwargs):
    if not housekeeping.may_housekeep(request.user):
      raise Http404
    section = kwargs.get('section')
    if section and section not in housekeeping.SECTION_BY_NAME:
      raise Http404
    return super().dispatch(request, *args, **kwargs)

  def get_template_names(self):
    return ['dashboard/housekeeping_section.html' if self.kwargs.get('section') else self.template_name]

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    section = self.kwargs.get('section')
    if not section:
      context['groups'] = housekeeping.overview()
      return context
    label, name, find = housekeeping.SECTION_BY_NAME[section]
    items = find()
    context.update({
      'section': section, 'label': label, 'count': len(items), name: items,
      'section_template': f'dashboard/housekeeping/{section}.html',
      'may_delete_tags': housekeeping.may_delete(self.request.user, 'tags'),
      'may_delete_places': housekeeping.may_delete(self.request.user, 'places'),
    })
    return context

  def back(self):
    """After a delete: the section it was done in."""
    section = self.kwargs.get('section')
    return redirect('dashboard:housekeeping_section', section) if section else redirect('dashboard:housekeeping')

  def post(self, request, *args, **kwargs):
    from content.models import Content
    action = request.POST.get('action')
    if action == 'purge':
      tokens = request.POST.getlist('item')
      items = list(Content.objects.filter(token__in=tokens, status=Content.Status.DELETED))
      if request.POST.get('confirm') == '1':
        gone = housekeeping.purge(items, request.user)
        messages.success(request, ngettext("%(n)s record purged.", "%(n)s records purged.", gone) % {'n': gone})
        return self.back()
      housekeeping.attach_consequences(items)
      return self.render_to_response({'action': action, 'items': items}, template_name='dashboard/housekeeping_confirm.html')
    if action == 'files':
      names = [name for name in request.POST.getlist('file') if housekeeping.safe_name(name)]
      known = housekeeping.stored_names()
      names = [name for name in names if name not in known]
      if request.POST.get('confirm') == '1':
        gone = housekeeping.delete_files(names)
        messages.success(request, ngettext("%(n)s file deleted.", "%(n)s files deleted.", gone) % {'n': gone})
        return self.back()
      files = [{'name': name, 'image': housekeeping.is_image_name(name)} for name in names]
      return self.render_to_response({'action': action, 'files': files}, template_name='dashboard/housekeeping_confirm.html')
    if action in ('tags', 'places'):
      if not housekeeping.may_delete(request.user, action):
        raise Http404
      objects = housekeeping.selected_unused(action, request.POST.getlist('object'))
      if request.POST.get('confirm') == '1':
        gone = housekeeping.delete_unused(objects, request.user)
        message = ngettext("%(n)s tag deleted.", "%(n)s tags deleted.", gone) if action == 'tags' else ngettext("%(n)s place deleted.", "%(n)s places deleted.", gone)
        messages.success(request, message % {'n': gone})
        return self.back()
      return self.render_to_response({'action': action, 'objects': objects}, template_name='dashboard/housekeeping_confirm.html')
    messages.error(request, _("Nothing selected."))
    return self.back()

  def render_to_response(self, context, template_name=None, **kwargs):
    if template_name:
      from django.template.response import TemplateResponse
      context.setdefault('section', self.kwargs.get('section'))   # the confirmation's way back
      return TemplateResponse(self.request, template_name, context)
    return super().render_to_response(context, **kwargs)


@require_GET
def housekeeping_preview(request):
  """dashboard/housekeeping/preview/?token=|?name= - a small thumbnail of
  an item (any status: a deleted one is hidden everywhere else) or of a
  file without a record, for the housekeeping page. Staff who may delete
  content only; a name only under content/."""
  from content.models import Content
  from sorl.thumbnail import get_thumbnail
  if not housekeeping.may_housekeep(request.user):
    raise Http404
  token = request.GET.get('token')
  if token:
    item = get_object_or_404(Content, token=token)
    if not item.file or item.media_type != 'image':
      raise Http404
    source = item.file
  else:
    name = housekeeping.safe_name(request.GET.get('name', ''))
    if name is None or not housekeeping.is_image_name(name):
      raise Http404
    source = name
  thumbnail = get_thumbnail(source, '160x160', crop='center')
  from django.core.files.storage import default_storage
  if not default_storage.exists(thumbnail.name):
    raise Http404
  return sendfile(request, default_storage.path(thumbnail.name), attachment=False)


class AccountsView(TemplateView):
  """dashboard/accounts/ - accounts waiting for approval (approve / decline)
  and every active account's last sign-in and last activity
  (dashboard/accounts.py). Staff who may change users only."""
  template_name = 'dashboard/accounts.html'

  def dispatch(self, request, *args, **kwargs):
    if not accounts.may_manage_accounts(request.user):
      raise Http404
    return super().dispatch(request, *args, **kwargs)

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context.update({'waiting': list(accounts.waiting()), 'active': accounts.activity()})
    return context

  def post(self, request, *args, **kwargs):
    from django.contrib.auth import get_user_model
    account = get_object_or_404(get_user_model(), pk=request.POST.get('account'))
    name = account.username
    if request.POST.get('action') == 'approve' and accounts.approve(account):
      messages.success(request, _("%(name)s can sign in now.") % {'name': name})
    elif request.POST.get('action') == 'decline' and accounts.decline(account):
      messages.success(request, _("%(name)s was declined and removed.") % {'name': name})
    else:
      messages.error(request, _("%(name)s isn't waiting for approval.") % {'name': name})
    return redirect('dashboard:accounts')
