from django.contrib import messages
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.views.generic import FormView

from cmnsd.edit.mode import set_edit_mode
from cmnsd.models.access import filter_accessible

from ..forms import NAME_FIELDS, PersonCreateForm
from ..models import Person
from ..relatives import KINDS, add_relative


class PersonCreateView(PermissionRequiredMixin, FormView):
  """people/new/ - add a person: names and the basics, then on to their
  page in edit mode for the rest. Reached from a picker's "+ new person"
  (content, notes, a person's family) with the search as ?given_name=,
  and - from a family picker - ?relation=parent|partner|child&of=<token>:
  the new person becomes that relative of <token> (only someone the user
  may see; the rules of people/relatives.py). Published, visible to
  signed-in users, like the rest of the tree. Needs people.add_person."""
  permission_required = 'people.add_person'
  form_class = PersonCreateForm
  template_name = 'people/person_create.html'

  def relative_of(self):
    """(relation, person) from ?relation=&of= - or (None, None)."""
    data = self.request.POST if self.request.method == 'POST' else self.request.GET
    relation, token = data.get('relation', ''), data.get('of', '')
    if relation not in KINDS or not token:
      return None, None
    return relation, filter_accessible(Person.objects.all(), self.request).filter(token=token).first()

  def get_initial(self):
    initial = {name: self.request.GET.get(name, '') for name in NAME_FIELDS if self.request.GET.get(name)}
    relation, other = self.relative_of()
    # A child usually carries the parent's family name: the married name
    # when there is one, else the last name - changeable in the form.
    family_name = other and (other.married_name or other.last_name)
    if relation == 'child' and family_name and 'last_name' not in initial:
      initial['last_name'] = family_name
    if relation == 'child' and other:
      initial['child_of'] = other.token   # the form offers the other parent
    if other:
      initial['relative_of'] = other.token   # family as they are
    return initial

  def get_form(self, form_class=None):
    from cmnsd.views.api.object_form import make_form
    return make_form(form_class or self.get_form_class(), self.request, **self.get_form_kwargs())

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['relation'], context['relative_of'] = self.relative_of()
    return context

  def form_valid(self, form):
    person = form.save(commit=False)
    person.user = self.request.user
    person.save()
    form.save_m2m()   # also links the other parent (PersonCreateForm)
    LogEntry.objects.log_actions(self.request.user.pk, [person], ADDITION, change_message="Created on the site", single_object=True)
    relation, other = self.relative_of()
    if other is not None:
      # "child of X" here means the new person is X's child: from X's side,
      # the new person is X's <relation>.
      try:
        add_relative(other, relation, person.token, self.request)
      except ValidationError as error:
        messages.warning(self.request, _("Added, but not linked: %(error)s") % {'error': ' '.join(error.messages)})
      except PermissionDenied:
        messages.warning(self.request, _("Added, but not linked: you may not change %(name)s.") % {'name': other})
    messages.success(self.request, _("%(name)s added.") % {'name': person})
    try:
      set_edit_mode(self.request, True)
    except PermissionError:
      return redirect(person.page_url())
    return redirect(f"{person.page_url()}?open=birth")
