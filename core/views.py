from django.contrib.auth.mixins import LoginRequiredMixin
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.shortcuts import redirect
from django.views.generic import DetailView, ListView, TemplateView

from cmnsd.models.access import filter_accessible
from cmnsd.ui.state import get_sort
from cmnsd.api.filtering import search_character
from cmnsd.views.api.response import api_response
from cmnsd.views.mixins import VisibilityViewMixin

from . import search
from .comments import visible_comment_feed
from .tags import attach_content_counts, by_count, tag_overview
from .models import Tag


class CommentListView(LoginRequiredMixin, ListView):
  """/comments/ - every comment the viewer may see, on anything they may
  see (core/comments.py), newest first, 30 per page. ?on=content|person
  narrows to one kind of target. Signed-in only: comments are family
  conversation. Edit/delete/hide work here too (same API actions)."""
  template_name = 'comment/comment_overview.html'
  context_object_name = 'comments'
  paginate_by = 30
  FILTERS = (('', _('all')), ('content', _('on content')), ('person', _('on people')))

  def get_queryset(self):
    on = self.request.GET.get('on') or None
    self.on = on if on in dict(self.FILTERS) else None
    return visible_comment_feed(self.request, self.on)

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['filters'] = self.FILTERS
    context['active_filter'] = self.on or ''
    # Avatars (authors, and people commented on) and the people's
    # lifespans in batch queries, not one per row.
    from people.models import Person
    comments = context['comments']
    authors = [c.user.person for c in comments if getattr(c.user, 'person', None)]
    targets = [c.target for c in comments if isinstance(c.target, Person)]
    Person._attach_portraits(authors)
    Person._attach_portraits(Person._attach_lifespan(targets))
    return context


class TagListView(TemplateView):
  """/tags/ - every tag this viewer may see that holds content, each with
  its content count (core/tags.py): first the tags that group others
  ("Collection", with its collections), then the rest. Public like a tag's
  own page - the counts only include what this viewer may see."""
  template_name = 'tag/tag_overview.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['groups'], context['loose'] = tag_overview(self.request)
    return context


class TagDetailView(VisibilityViewMixin, DetailView):
  """tags/<token>/<slug>/ - a tag's page: what it groups, with context.

  The tag's name, parent (e.g. "Collection") and description; a cover
  (the earliest image among its items); its content as the shared content
  grid (filters by kind, remembered sort - key 'tag.content', the same on
  every tag page); the people carrying the tag; and its child tags - so
  the "Collection" tag's page lists all collections. Only what this viewer
  may see; an item whose part is tagged shows as its whole."""
  model = Tag
  slug_field = 'token'
  slug_url_kwarg = 'token'
  context_object_name = 'tag'
  template_name = 'tag/tag_detail.html'
  SORTS = ('added', 'date')

  def get_queryset(self):
    return self.get_accessible_queryset(Tag.objects.select_related('parent'))

  def get(self, request, *args, **kwargs):
    self.object = self.get_object()
    if kwargs.get('slug') != self.object.slug and self.object.slug:
      return redirect(self.object.get_absolute_url(), permanent=True)
    return self.render_to_response(self.get_context_data(object=self.object))

  def get_context_data(self, **kwargs):
    from content.models import Content
    from people.models import Person
    context = super().get_context_data(**kwargs)
    tag, request = self.object, self.request
    sort = get_sort(request, 'tag.content', 'added', self.SORTS)
    items = list(
      Content.objects.visible_to(request).listable()
      .filter(Q(tags=tag) | Q(parts__tags=tag)).distinct()
      .select_related('photo_detail', 'document_detail', 'book_detail')
      .in_order(sort)
    )
    context['items'] = items
    context['sort'] = sort
    dated_images = sorted(
      (item for item in items if item.file and item.media_type == 'image' and item.year),
      key=lambda item: (item.year, item.month or 0, item.day or 0),
    )
    context['cover'] = dated_images[0] if dated_images else next(
      (item for item in items if item.file and item.media_type == 'image'), None,
    )
    people = filter_accessible(tag.people.all(), request)
    context['people'] = Person._attach_portraits(Person._attach_lifespan(people))
    context['children'] = by_count(attach_content_counts(filter_accessible(Tag.objects.filter(parent=tag), request), request))
    return context


class SearchView(LoginRequiredMixin, TemplateView):
  """/search/?q=... - everything this viewer may see that matches, per kind
  (core/search.py); ?kind=person|content|... narrows to all hits of one
  kind. Signed-in only, like the More menu: signed out there's little to
  find, and the way in is an account. A plain GET form; while typing,
  cmnsd.js list.js (data-cmnsd-list-url) asks this same address for JSON
  and swaps in just the results (search/_results.html)."""
  template_name = 'search/search.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    query = self.request.GET.get(search_character(), '').strip()
    kind = self.request.GET.get('kind', '')
    kinds = {name: label for name, _model, label, _icon in search.kinds()}
    context.update({
      'search_query': query, 'kind': kind if kind in kinds else '', 'kind_label': kinds.get(kind, ''),
      'sections': search.search(self.request, query, kind),
      'too_short': 0 < len(query) < search.MIN_LENGTH,
    })
    return context

  def render_to_response(self, context, **kwargs):
    if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
      html = render_to_string('search/_results.html', context, request=self.request)
      return api_response(self.request, html=html)
    return super().render_to_response(context, **kwargs)


class PreferencesView(LoginRequiredMixin, TemplateView):
  """/preferences/ - your own preferences: the interface language and who
  you count as family (core.forms.PreferencesForm). Signed-in only;
  the Preferences row is made on first visit."""
  template_name = 'preferences/preferences.html'

  def preferences(self):
    from .models import Preferences
    return Preferences.objects.get_or_create(user=self.request.user)[0]

  def get_context_data(self, **kwargs):
    from .forms import PreferencesForm
    context = super().get_context_data(**kwargs)
    context['form'] = kwargs.get('form') or PreferencesForm(instance=self.preferences(), user=self.request.user)
    return context

  def post(self, request, *args, **kwargs):
    from django.contrib import messages
    from django.utils.translation import get_language, gettext, override
    from .forms import PreferencesForm
    form = PreferencesForm(request.POST, instance=self.preferences(), user=request.user)
    if not form.is_valid():
      return self.render_to_response(self.get_context_data(form=form))
    form.save()
    # The message in the language just chosen - override, not activate: that
    # would stay on for whatever this thread does next.
    with override(form.cleaned_data.get('language') or get_language()):
      messages.success(request, gettext("Preferences saved."))
    return redirect('core:preferences')
