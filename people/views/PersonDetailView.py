from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import DetailView

from cmnsd.views.mixins import VisibilityViewMixin
from ..models import Person


class PersonDetailView(VisibilityViewMixin, DetailView):
  """A private person's page opens only for the person themself, their
  parents and staff (people/privacy.py) - for anyone else it 404s, the same as a
  hidden person; status and visibility (VisibilityViewMixin) apply on top."""
  model = Person
  # person/<token>/<slug>/ - the token finds the person, the slug is for
  # reading; another slug redirects (keeping ?open= and the like). Old
  # /person/<slug>/ addresses go through person_redirect.
  slug_field = 'token'
  slug_url_kwarg = 'token'
  context_object_name = 'person'
  template_name = 'people/person_detail.html'

  def get_queryset(self):
    # optimized(): prefetches relations_from/relations_to so
    # get_parents()/get_children()/get_partners()/get_siblings() don't hit
    # the DB once per call on this detail page.
    queryset = Person.objects.optimized()
    # Private people: only the ones this viewer may open (people/privacy.py).
    from ..privacy import opens_every_private_page, private_pages_open_to
    user = self.request.user
    if not opens_every_private_page(user):
      queryset = queryset.filter(Q(private=False) | Q(pk__in=private_pages_open_to(user)))
    # Status + visibility: a concept or deleted person 404s here too, the
    # same as in the People list and the API.
    return self.get_accessible_queryset(queryset)

  def get(self, request, *args, **kwargs):
    self.object = self.get_object()
    if kwargs.get('slug') != self.object.slug:
      return _to_canonical(request, self.object)
    return self.render_to_response(self.get_context_data(object=self.object))

  def get_context_data(self, **kwargs):
    from cmnsd.edit.mode import can_edit, is_edit_mode
    context = super().get_context_data(**kwargs)
    # Edit mode, for someone who may change this person: the blocks, the
    # choices panel, tags, and the family edited in place (people/forms.py,
    # person/_relative_picker.html).
    context['editing'] = is_edit_mode(self.request) and can_edit(self.object, self.request.user)
    return context


def _to_canonical(request, person):
  url = person.page_url()   # access checked by the caller's queryset
  query = request.GET.urlencode()
  return redirect(f"{url}?{query}" if query else url, permanent=True)


def person_redirect(request, key):
  """person/<key>/ - a token-only address, or an old one by slug (links
  in texts, bookmarks: /person/<slug>/ before tokens) - redirects to
  person/<token>/<slug>/. Only a person this viewer may see - a private
  one only for themself, their parents and staff (404, like PersonDetailView)."""
  view = PersonDetailView()
  view.request = request
  person = view.get_queryset().filter(Q(token=key) | Q(slug=key)).first()
  if person is None:
    raise Http404("No such person.")
  return _to_canonical(request, person)
