"""
Forms for events: the blocks of an event's page (edit mode, Event.api_edit_forms;
cmnsd object_form) and a new event in a dialog (Event.api_create_form; cmnsd
object_create). Plain ModelForms: validation is the model's own (Event.clean:
an 'other' event needs its own label; PartialDateMixin: the date's rules).
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from cmnsd.forms.widgets import PickerInput, MentionTextarea
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
WHAT_LABELS = {'kind': _("kind"), 'title': _("title")}
# One field for what it was and what it's called (it used to be two, title
# and own label - the same text in practice). Hidden for the kinds that
# name themselves (Event.UNTITLED_KINDS, components.css).
WHAT_HELP = {
  'title': _("What it was, or its name - e.g. 'Aanstelling als Beheerder bij departement Zoutaanmaak' or 'Inval Japan Nederlands Indië'. Required for 'other'; a historical event needs one to say what it is."),
}


def year_problem(kind, year):
  """Why an event of this kind can't be without a year, or None. A birth or
  a death may be undated - it has a place in a life anyway (the start, the
  end); anything else without a year has no place on any timeline. Not
  sure: a guess with "ca.". In the forms only - the admin and the legacy
  import may still store one, and the loose end "events without a date"
  lists them."""
  from .models import LIFE_KINDS
  if kind and kind not in LIFE_KINDS and not year:
    return _("A year is needed - if you're not sure, give your best guess with “ca.”.")
  return None


def _month_choices(form):
  # An empty month is "unknown", not "- Select an option -".
  form.fields['month'].choices = [('', '—'), *[c for c in form.fields['month'].choices if c[0] != '']]


class EventWhatForm(forms.ModelForm):
  """What the event is: its kind, and its title. Not a birth or death its
  people can't have (life_event_problem)."""
  class Meta:
    model = Event
    fields = ['kind', 'title']
    labels = WHAT_LABELS
    help_texts = WHAT_HELP
    widgets = {'title': forms.TextInput(attrs={'autocomplete': 'off'})}

  def clean_kind(self):
    from .models import life_event_problem
    kind = self.cleaned_data.get('kind')
    problem = life_event_problem(kind, self.instance.people.all(), event=self.instance) if self.instance.pk else None
    if problem:
      raise forms.ValidationError(problem)
    # An undated birth made into another kind would lose its place on the timeline.
    problem = year_problem(kind, self.instance.year)
    if problem:
      raise forms.ValidationError(problem)
    return kind


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

  def clean(self):
    data = super().clean()
    problem = year_problem(self.instance.kind, data.get('year'))
    if problem:
      self.add_error('year', problem)
    return data


class EventDescriptionForm(forms.ModelForm):
  class Meta:
    model = Event
    fields = ['description']
    labels = {'description': _("description")}
    help_texts = {'description': _("What happened, and the sources - Markdown: [bron](https://...).")}
    widgets = {'description': MentionTextarea(attrs={'rows': 8})}


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
  them), ?content=<token> (an item documenting it). Published, like the rest.

  Who, besides that person: `with_people`, their close family to tick
  (partners, parents, children - those this user may see), and
  `other_person`, anyone else, through the person picker. More people are
  added on the event's page. For a marriage or a divorce the others are
  expected to be partners (the form hints so - event/forms/new.html): one
  who isn't yet is linked as a partner on save, through people/relatives.py
  with its own permission check and rules; a refusal leaves the event as it
  is, with the reason as a message.

  From an item (?from_item=<token> - "make an event from this item", issue
  #487): an item this user may see and change, the page they're on (a
  part, not its whole). The item is linked as "documented by" on save; its
  people and places to tick. Ticked by role: no role or subject - moved
  (on the event, the item's own link removed: the event brings the item
  to their page, as related content); depicted - copied (who's on a photo
  is more than who was there); creator, addressee, owner - not ticked, and
  copied when ticked (they say something about the item). Someone with a
  frame is never moved. The description stays with the item. A refused
  event (a second birth) moves nothing: the form isn't valid."""
  # Roles whose link to the item the event replaces - moved, not copied.
  MOVED_ROLES = ('', 'subject')
  # Ticked to start with: the moved ones, and who's on it.
  TICKED_ROLES = ('', 'subject', 'depicted', 'possibly_depicted')

  from_item = forms.CharField(required=False, widget=forms.HiddenInput)
  item_people = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple, label=_("people on the item"))
  item_places = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple, label=_("places of the item"))
  place = forms.ModelChoiceField(
    Place.objects.select_related('parent'), to_field_name='token', required=False, label=_("place"),
    widget=PickerInput(
      'place', label=lambda place: ' › '.join(ancestor.name for ancestor in place.ancestors()),
      placeholder=_("search a place"), empty_label=_("unknown"), clear_label=_("remove"), submit=False,
      create_label=_("+ new place"), empty_until_cleared=True,
    ),
  )
  person = forms.CharField(required=False, widget=forms.HiddenInput)
  with_people = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple, label=_("with"))
  other_person = forms.ModelChoiceField(
    Person.objects.none(), to_field_name='token', required=False, label=_("someone else"),
    widget=PickerInput(
      'person', placeholder=_("search a person"), empty_label=_("no one"), clear_label=_("remove"), submit=False, empty_until_cleared=True,
    ),
  )
  # The evidence to hand, if any: one item, linked as "documented by" on
  # save. More, with suggestions from its people, on the event's page.
  # ?content=<token> prefills it (residence suggestions, #465); left out
  # when the dialog comes from an item's page, which links that item itself
  # (?from_content=1).
  content = forms.ModelChoiceField(
    Person.objects.none(), to_field_name='token', required=False, label=_("documented by"),
    widget=PickerInput(
      'content', placeholder=_("search an item"), empty_label=_("nothing yet"), clear_label=_("remove"), submit=False, empty_until_cleared=True,
    ),
  )

  # Kinds whose people are expected to be partners: a missing partner link is made on save.
  PARTNER_KINDS = (Event.Kind.MARRIAGE, Event.Kind.DIVORCE)

  # The template groups these (event/forms/new.html).
  what_fields = ['kind', 'title']
  date_fields = DATE_FIELDS

  class Meta:
    model = Event
    fields = ['kind', 'title', *DATE_FIELDS, 'description']
    labels = {**WHAT_LABELS, **DATE_LABELS, 'description': _("description")}
    help_texts = WHAT_HELP
    widgets = {**DATE_WIDGETS, 'description': MentionTextarea(attrs={'rows': 4})}

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    _month_choices(self)
    self.linked_person = None
    self.item = None
    self.item_links = {}

  def prepare(self):
    """The person from ?person= - only one this user may see - and the
    people to choose from: their close family to tick, anyone this user
    may see in the picker."""
    visible = filter_accessible(Person.objects.all(), self.request)
    token = (self.data.get('person') if self.is_bound else self.initial.get('person')) or ''
    if token:
      self.linked_person = visible.filter(token=token).first()
    if self.linked_person is not None:
      # A person's birth and death have their own place on their page (the
      # birth and death records) - one way in, not two.
      from .models import LIFE_KINDS
      self.fields['kind'].choices = [choice for choice in self.fields['kind'].choices if choice[0] not in LIFE_KINDS]
    self.fields['other_person'].queryset = visible
    family = self._family(visible)
    if family:
      self.fields['with_people'].choices = family
    else:
      del self.fields['with_people']
    self._prepare_item(visible)
    self.fields['other_person'].widget.exclude = [t for t in [
      getattr(self.linked_person, 'token', None), *(t for t, _l in family), *self.item_links,
    ] if t]
    # Documented by: an item this user may see; not from an item's page.
    from content.models import Content
    if self.item is not None or (not self.is_bound and self.request.GET.get('from_content')):
      del self.fields['content']
    else:
      self.fields['content'].queryset = Content.objects.visible_to(self.request)

  def _prepare_item(self, visible):
    """From an item (?from_item=): its people this user may see, each
    saying whether it moves or stays, and its places - ticked as the
    class docstring says. Without one (or one this user may not change):
    neither field."""
    from cmnsd.edit.mode import can_edit
    from content.models import Content, ContentPerson
    token = (self.data.get('from_item') if self.is_bound else self.initial.get('from_item')) or ''
    item = Content.objects.visible_to(self.request).filter(token=token).first() if token else None
    if item is None or not can_edit(item, self.request.user):
      for name in ('from_item', 'item_people', 'item_places'):
        del self.fields[name]
      return
    self.item = item
    links = ContentPerson.objects.filter(content=item, person__in=visible).select_related('person').order_by('person__given_name', 'pk')
    self.item_links = {link.person.token: link for link in links}
    choices, ticked = [], []
    for token, link in self.item_links.items():
      name = link.person.get_full_name()
      role = ContentPerson.Role(link.role).label if link.role else ''
      label = f"{name} ({role})" if role else name
      choices.append((token, label))
      if link.role in self.TICKED_ROLES:
        ticked.append(token)
    places = list(item.places.select_related('parent'))
    if choices:
      self.fields['item_people'].choices = choices
      self.fields['item_people'].initial = ticked
    else:
      del self.fields['item_people']
    if places:
      self.fields['item_places'].choices = [(place.token, place.name) for place in places]
      self.fields['item_places'].initial = [place.token for place in places]
    else:
      del self.fields['item_places']

  def moves(self, link):
    """Whether ticking this item link moves it to the event (the item's own
    link removed) rather than copying it."""
    return link.role in self.MOVED_ROLES and not link.has_region

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
    tokens = [*(self.cleaned_data.get('with_people') or []), *self.ticked_item_tokens()]
    people = list(Person.objects.filter(token__in=tokens)) if tokens else []
    other = self.cleaned_data.get('other_person')
    if other is not None and other not in people and other != self.linked_person:
      people.append(other)
    return people

  def ticked_item_tokens(self):
    """The item's people ticked - only those offered (item_links)."""
    return [token for token in self.cleaned_data.get('item_people') or [] if token in self.item_links]

  def clean(self):
    from places.places import picked_place
    from .models import life_event_problem
    data = super().clean()
    picked_place(self)   # a typed new place: made on save
    people = [*([self.linked_person] if self.linked_person else []), *self.chosen_people()]
    problem = life_event_problem(data.get('kind'), people)
    if problem:
      self.add_error('kind', problem)
    problem = year_problem(data.get('kind'), data.get('year'))
    if problem:
      self.add_error('year', problem)
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
    item = self.cleaned_data.get('content')
    if item is not None:
      self.instance.content.add(item)
    if self.item is not None:
      self._from_item()
    if self.linked_person is not None and self.instance.kind in self.PARTNER_KINDS:
      self._link_partners(others)

  def _from_item(self):
    """The item it was made from: linked as "documented by", its ticked
    places added, and its ticked people that move taken off the item - each
    logged on it, said in one message."""
    from django.contrib import messages
    from cmnsd.edit.log import log_change
    event, item = self.instance, self.item
    event.content.add(item)
    places = self.cleaned_data.get('item_places') or []
    if places:
      event.places.add(*item.places.filter(token__in=places))
    moved = [self.item_links[token] for token in self.ticked_item_tokens() if self.moves(self.item_links[token])]
    for link in moved:
      link.delete()
    if moved:
      names = ', '.join(link.person.get_full_name() for link in moved)
      log_change(self.request, item, f"Removed people: {names} (moved to the event {event.label()})")
      messages.info(self.request, _("Moved from the item to the event: %(names)s.") % {'names': names})

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
