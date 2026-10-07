"""
Forms for events: the blocks of an event's page (edit mode, Event.api_edit_forms;
cmnsd object_form) and a new event in a dialog (Event.api_create_form; cmnsd
object_create). Plain ModelForms: validation is the model's own (Event.clean:
an 'other' event needs its own label; PartialDateMixin: the date's rules).
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from cmnsd.forms.widgets import PickerInput
from cmnsd.models.access import filter_accessible
from core.forms import StatusActionsForm
from people.models import Person
from places.models import Place

from .models import Event

DATE_FIELDS = ['date_qualifier', 'day', 'month', 'year']
DATE_LABELS = {'date_qualifier': _("how sure"), 'day': _("day"), 'month': _("month"), 'year': _("year")}
DATE_WIDGETS = {
  'day': forms.NumberInput(attrs={'min': 1, 'max': 31, 'inputmode': 'numeric'}),
  'year': forms.NumberInput(attrs={'min': 1, 'inputmode': 'numeric'}),
}
WHAT_LABELS = {
  'kind': _("kind"), 'title': _("title"), 'kind_freetext': _("own label"),
}
WHAT_HELP = {
  'title': _("Optional - e.g. 'Inval Japan Nederlands Indië'. Without one, the kind names it."),
  'kind_freetext': _("For kind 'other': what it was - e.g. 'verhuizing naar Medan'."),
}


def _month_choices(form):
  # An empty month is "unknown", not "- Select an option -".
  form.fields['month'].choices = [('', '—'), *[c for c in form.fields['month'].choices if c[0] != '']]


class EventWhatForm(forms.ModelForm):
  """What the event is: its kind, and a title or own label."""
  class Meta:
    model = Event
    fields = ['kind', 'title', 'kind_freetext']
    labels = WHAT_LABELS
    help_texts = WHAT_HELP
    widgets = {'title': forms.TextInput(attrs={'autocomplete': 'off'}), 'kind_freetext': forms.TextInput(attrs={'autocomplete': 'off'})}


class EventDateForm(forms.ModelForm):
  """When - year, month and day each optional, and how sure (one line:
  event/forms/date.html)."""
  class Meta:
    model = Event
    fields = DATE_FIELDS
    labels = DATE_LABELS
    widgets = DATE_WIDGETS

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    _month_choices(self)


class EventDescriptionForm(forms.ModelForm):
  class Meta:
    model = Event
    fields = ['description']
    labels = {'description': _("description")}
    help_texts = {'description': _("What happened, and the sources - Markdown: [bron](https://...).")}
    widgets = {'description': forms.Textarea(attrs={'rows': 8})}


class EventStatusForm(StatusActionsForm):
  """Status as actions (core.forms.StatusActionsForm): deleting hides the
  event from everyone - also from the timelines and a person's birth and
  death - and can be undone in the admin."""
  confirm = {
    'x': _("Delete this event? It disappears everywhere, also from timelines - it can be recovered in the admin."),
    'r': _("Revoke this event? Only staff will see it until it's restored."),
  }

  class Meta(StatusActionsForm.Meta):
    model = Event


class EventCreateForm(forms.ModelForm):
  """A new event, in a dialog (cmnsd object_create): what, when, where, who
  and the description; the documenting items are added on its page.
  Prefilled from the query: ?kind= (the events page's kind), ?person=<token>
  (a person's timeline - linked to the new event, if this user may see
  them). Published, like the rest.

  Who, besides that person: `with_people`, their close family to tick
  (partners, parents, children - those this user may see), and
  `other_person`, anyone else, through the person picker. More people are
  added on the event's page. For a marriage or a divorce the others are
  expected to be partners (the form hints so - event/forms/new.html): one
  who isn't yet is linked as a partner on save, through people/relatives.py
  with its own permission check and rules; a refusal leaves the event as it
  is, with the reason as a message."""
  place = forms.ModelChoiceField(
    Place.objects.select_related('parent'), to_field_name='token', required=False, label=_("place"),
    widget=PickerInput(
      'place', label=lambda place: ' › '.join(ancestor.name for ancestor in place.ancestors()),
      placeholder=_("search a place"), empty_label=_("unknown"), clear_label=_("remove"), submit=False,
      create_label=_("+ new place"),
    ),
  )
  person = forms.CharField(required=False, widget=forms.HiddenInput)
  with_people = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple, label=_("with"))
  other_person = forms.ModelChoiceField(
    Person.objects.none(), to_field_name='token', required=False, label=_("someone else"),
    widget=PickerInput(
      'person', placeholder=_("search a person"), empty_label=_("no one"), clear_label=_("remove"), submit=False,
    ),
  )

  # Kinds whose people are expected to be partners: a missing partner link is made on save.
  PARTNER_KINDS = (Event.Kind.MARRIAGE, Event.Kind.DIVORCE)

  # The template groups these (event/forms/new.html).
  what_fields = ['kind', 'title', 'kind_freetext']
  date_fields = DATE_FIELDS

  class Meta:
    model = Event
    fields = ['kind', 'title', 'kind_freetext', *DATE_FIELDS, 'description']
    labels = {**WHAT_LABELS, **DATE_LABELS, 'description': _("description")}
    help_texts = WHAT_HELP
    widgets = {**DATE_WIDGETS, 'description': forms.Textarea(attrs={'rows': 4})}

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    _month_choices(self)
    self.linked_person = None

  def prepare(self):
    """The person from ?person= - only one this user may see - and the
    people to choose from: their close family to tick, anyone this user
    may see in the picker."""
    visible = filter_accessible(Person.objects.all(), self.request)
    token = (self.data.get('person') if self.is_bound else self.initial.get('person')) or ''
    if token:
      self.linked_person = visible.filter(token=token).first()
    self.fields['other_person'].queryset = visible
    family = self._family(visible)
    if family:
      self.fields['with_people'].choices = family
    else:
      del self.fields['with_people']
    self.fields['other_person'].widget.exclude = [t for t in [getattr(self.linked_person, 'token', None), *(t for t, _l in family)] if t]

  def _family(self, visible):
    """[(token, "Jacoba Bake (wife)")] - the linked person's partners, then
    parents, then children, as far as this user may see them."""
    person = self.linked_person
    if person is None:
      return []
    from people.timeline import _relation
    groups = [('partner', person.get_partners()), ('parent', person._get_parents_flat()), ('child', person._get_children_flat())]
    seen = set(visible.filter(pk__in=[p.pk for _k, people in groups for p in people]).values_list('pk', flat=True))
    choices = []
    for kind, people in groups:
      for relative in people:
        if relative.pk in seen:
          seen.discard(relative.pk)
          choices.append((relative.token, f"{relative.get_full_name()} ({_relation(kind, relative)})"))
    return choices

  def chosen_people(self):
    """Everyone the new event is about, besides the linked person: the
    ticked family and the picked someone else."""
    tokens = self.cleaned_data.get('with_people') or []
    people = list(Person.objects.filter(token__in=tokens)) if tokens else []
    other = self.cleaned_data.get('other_person')
    if other is not None and other not in people and other != self.linked_person:
      people.append(other)
    return people

  def clean(self):
    from places.places import picked_place
    data = super().clean()
    picked_place(self)   # a typed new place: made on save
    return data

  def save(self, commit=True):
    self.instance.status = Event.Status.PUBLISHED
    return super().save(commit=commit)

  def _save_m2m(self):
    from places.places import create_picked_place
    super()._save_m2m()
    place = create_picked_place(self)
    if place:
      self.instance.places.add(place)
    others = self.chosen_people()
    if self.linked_person is not None:
      self.instance.people.add(self.linked_person)
    if others:
      self.instance.people.add(*others)
    if self.linked_person is not None and self.instance.kind in self.PARTNER_KINDS:
      self._link_partners(others)

  def _link_partners(self, others):
    """A marriage or divorce is between partners: link the ones who aren't
    yet. Each refusal (no permission to change the person, a parent can't
    be a partner, ...) as a message - the event itself is saved."""
    from django.contrib import messages
    from django.core.exceptions import PermissionDenied, ValidationError
    from people.relatives import PARTNER, add_relative
    partners = {p.pk for p in self.linked_person.get_partners()}
    for other in others:
      if other.pk in partners:
        continue
      try:
        add_relative(self.linked_person, PARTNER, other.token, self.request)
      except (PermissionDenied, ValidationError) as error:
        reason = ' '.join(error.messages) if isinstance(error, ValidationError) else _("You may not change their family.")
        messages.warning(self.request, _("%(name)s wasn't linked as a partner: %(reason)s") % {'name': other.get_full_name(), 'reason': reason})
