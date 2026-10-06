from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView

from cmnsd.api.filtering import build_list, list_context
from ..models import Person


class PersonListView(ListView):
  """/people/ - every person visible to this viewer, unpaginated, grouped
  A-Z (person/person_list.html). Visibility, status and ?q=/field
  filtering all come from cmnsd.api.filtering.build_list(), the same
  function the API's list endpoint uses, so this page and
  GET api/person/?... always agree on who is listed.

  private=True people are included on purpose (unlike PersonDetailView):
  they're part of the tree, the row just renders them without a link.

  ?family_connection= family (the default when absent) / possibly_family
  / outsider, or empty for everyone - the filter links above the list."""
  model = Person
  template_name = 'people/person_list.html'

  CONNECTION_FILTERS = (
    ('family', _('family')), ('possibly_family', _('possibly family')),
    ('outsider', _('outsiders')), ('', _('all')),
  )

  def get(self, request, *args, **kwargs):
    params = request.GET.copy()
    params.setdefault('family_connection', Person.FamilyConnection.FAMILY)
    self.connection = params['family_connection']
    self.result = build_list(Person, request, params=params)
    return super().get(request, *args, **kwargs)

  def get_queryset(self):
    return self.result['objects']

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context.update(list_context(Person, self.result, self.request))
    context['connection_filters'] = self.CONNECTION_FILTERS
    context['active_connection'] = self.connection
    return context
