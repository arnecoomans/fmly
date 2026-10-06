"""
Forms for editing a person on their page (edit mode) - one per block
(Person.api_edit_forms; cmnsd/views/api/object_form.py) - and for adding
a person (PersonCreateView). Plain ModelForms: validation is the model's
own (Person.clean: at least one name).
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from cmnsd.forms.widgets import PickerInput
from cmnsd.models.access import filter_accessible
from content.models import Portrait
from core.forms import StatusActionsForm
from events.models import Event
from places.models import Place

from .models import Person

NAME_FIELDS = ['given_name', 'called_name', 'last_name', 'married_name', 'nickname']
NAME_LABELS = {
  'given_name': _("given names"), 'called_name': _("called"), 'last_name': _("last name at birth"),
  'married_name': _("married name"), 'nickname': _("nickname"),
}


class PersonNamesForm(forms.ModelForm):
  """All names in one block: together they make the name shown (Person.
  get_full_name) - and the slug, set once, stays."""
  class Meta:
    model = Person
    fields = NAME_FIELDS
    labels = NAME_LABELS
    widgets = {name: forms.TextInput(attrs={'autocomplete': 'off'}) for name in NAME_FIELDS}


class PersonBiographyForm(forms.ModelForm):
  class Meta:
    model = Person
    fields = ['biography']
    labels = {'biography': _("biography")}
    help_texts = {'biography': _("Markdown: *italic*, **bold**, [link](https://...).")}
    widgets = {'biography': forms.Textarea(attrs={'rows': 10})}


class LifeEventForm(forms.ModelForm):
  """Birth or death: the person's Event of that kind - its partial date and
  its place (a picker, saved with the form's Save). instance_for() gives the
  existing event, or a new one that save() creates and links to the
  person. History and the stale check stay on the person (cmnsd
  object_form). The place chosen here replaces the event's places: one
  place of birth, one of death. Saving an unchanged form creates nothing -
  unless the form offers to record the event as such (RECORD_LABEL: "Died,
  details unknown") and that button is pressed."""
  KIND = None
  RECORD_LABEL = None   # a button to record the event without date or place, when there's none yet

  place = forms.ModelChoiceField(
    Place.objects.select_related('parent'), to_field_name='token', required=False, label=_("place"),
    widget=PickerInput(
      'place', label=lambda place: ' › '.join(ancestor.name for ancestor in place.ancestors()),
      placeholder=_("search a place"), empty_label=_("unknown"), clear_label=_("remove"), submit=False,
      create_label=_("+ new place"),
    ),
  )

  class Meta:
    model = Event
    fields = ['date_qualifier', 'day', 'month', 'year']
    labels = {'date_qualifier': _("how sure"), 'day': _("day"), 'month': _("month"), 'year': _("year")}
    widgets = {
      'day': forms.NumberInput(attrs={'min': 1, 'max': 31, 'inputmode': 'numeric'}),
      'year': forms.NumberInput(attrs={'min': 1, 'inputmode': 'numeric'}),
    }

  @classmethod
  def instance_for(cls, person):
    event = getattr(person, cls.KIND)   # Person.birth / Person.death
    if event is None:
      event = Event(kind=cls.KIND)
    event._for_person = person
    return event

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['month'].choices = [('', '—'), *[choice for choice in self.fields['month'].choices if choice[0] != '']]
    # "Record without details" (person/forms/_life_event.html): only while
    # there's no event yet.
    self.record_label = self.RECORD_LABEL if not self.instance.pk else None
    self.record_name = self.add_prefix('record')
    if self.instance.pk:
      first = self.instance.places.first()
      if first:
        self.initial['place'] = first.token

  def clean(self):
    from places.places import picked_place
    data = super().clean()
    picked_place(self)   # a typed new place: made on save
    return data

  def save(self, commit=True):
    event = super().save(commit=False)
    record = bool(self.record_label) and bool(self.data.get(self.record_name))
    if not event.pk and not record and not self.changed_data and not getattr(self, '_new_place_name', '') and not getattr(self, '_picked_by_name', None):
      return event   # nothing filled in: no empty event
    if not event.pk:
      event.user = self.request.user
    event.save()
    person = getattr(event, '_for_person', None)
    if person is not None:
      event.people.add(person)
    if 'place' in self.changed_data or getattr(self, '_new_place_name', '') or getattr(self, '_picked_by_name', None):
      from places.places import create_picked_place
      place = create_picked_place(self)
      event.places.set([place] if place else [])
    return event


class PersonBirthForm(LifeEventForm):
  KIND = Event.Kind.BIRTH


class PersonDeathForm(LifeEventForm):
  KIND = Event.Kind.DEATH
  # Known to have died, nothing else: date and place to follow (or never).
  RECORD_LABEL = _("Died, details unknown")


class PersonPortraitForm(forms.ModelForm):
  """The person's portrait, in a dialog (person/forms/portrait.html): which
  photo - a strip of the images they're tagged in (content/portraits.py
  portrait_candidates) - and its crop, chosen in a square frame over the
  photo (cmnsd.js viewer.js crop mode): fractions of the photo as shown,
  turned first by `rotation` (0/90/180/270, the rotate button: a photo
  pasted sideways). "Whole photo" saves the whole photo as the crop (a
  document portrait is only used with a crop); the turn stays. Choosing
  another photo makes that the primary portrait (an earlier one stays a
  portrait). Any photo the person isn't tagged in is made a portrait from
  its own page (Content.set_portrait)."""
  dialog_title = _("Portrait")
  block_class = 'person-profile-card__portrait'

  class Meta:
    model = Portrait
    fields = ['crop_x', 'crop_y', 'crop_w', 'crop_h', 'rotation']
    widgets = {
      'crop_x': forms.HiddenInput(attrs={'data-crop': 'x'}), 'crop_y': forms.HiddenInput(attrs={'data-crop': 'y'}),
      'crop_w': forms.HiddenInput(attrs={'data-crop': 'w'}), 'crop_h': forms.HiddenInput(attrs={'data-crop': 'h'}),
      'rotation': forms.HiddenInput(attrs={'data-crop': 'rotate'}),
    }
    labels = {
      'crop_x': _("crop left"), 'crop_y': _("crop top"), 'crop_w': _("crop width"), 'crop_h': _("crop height"),
      'rotation': _("rotation"),
    }

  CROP_FIELDS = ('crop_x', 'crop_y', 'crop_w', 'crop_h')

  @staticmethod
  def instance_for(person):
    """The primary portrait, or a new one to choose a photo for - knowing
    the page's person, so save() can update what it caches."""
    portrait = person.primary_portrait_link or Portrait(person=person)
    portrait._for_person = person
    return portrait

  @property
  def person(self):
    return getattr(self.instance, '_for_person', None) or self.instance.person

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['rotation'].required = False   # not sent: not turned
    self.candidates = {}

  def prepare(self):
    """The photos to choose from (needs the viewer: only what they may see)."""
    from django.http import Http404
    from content.portraits import portrait_candidates
    images = portrait_candidates(self.person, self.request)
    if not images:
      raise Http404("No photo to make a portrait of.")
    self.candidates = {image.token: image for image in images}
    current = self.instance.content if self.instance.content_id else None
    self.default_photo = current.token if current else self._first_choice(images)
    self.fields['photo'] = forms.ChoiceField(
      label=_("photo"), choices=[(token, str(image)) for token, image in self.candidates.items()],
      initial=self.default_photo, required=False,   # not sent: the current one
    )

  @staticmethod
  def _first_choice(images):
    """Without a portrait yet, the dialog opens on a photo - a posed
    portrait first, then any photo - rather than the oldest image they're
    tagged in (often a document, e.g. a passport page)."""
    def rank(image):
      detail = getattr(image, 'photo_detail', None) if image.kind == 'photo' else None
      if detail is not None and detail.photo_kind == 'portrait':
        return 0
      return 1 if image.kind == 'photo' else 2
    return min(images, key=rank).token   # min is stable: the oldest within a rank

  def clean_photo(self):
    return self.cleaned_data.get('photo') or self.default_photo

  def chosen_photo(self):
    """The photo shown in the frame when the dialog opens (or comes back
    with an error): the one chosen, else the current one."""
    token = self['photo'].value() if 'photo' in self.fields else None
    return self.candidates.get(token) or self.candidates.get(getattr(self, 'default_photo', None))

  def clean_rotation(self):
    return self.cleaned_data.get('rotation') or 0

  def clean(self):
    data = super().clean()
    if self.data.get(f'{self.prefix}-reset' if self.prefix else 'reset'):
      # The whole photo, as an explicit crop - not "no crop": a document
      # portrait without a crop isn't used for the avatar (visible_portrait).
      # The turn stays.
      data.update({'crop_x': 0.0, 'crop_y': 0.0, 'crop_w': 1.0, 'crop_h': 1.0})
    return data

  def save(self, commit=True):
    photo = self.candidates[self.cleaned_data['photo']]
    if self.instance.pk and self.instance.content_id == photo.pk:
      return super().save(commit=commit)
    # Another photo (or the first): its Portrait - an earlier one is reused -
    # with this crop, made primary.
    person = self.person
    portrait, _created = Portrait.objects.get_or_create(person=person, content=photo)
    for name in (*self.CROP_FIELDS, 'rotation'):
      setattr(portrait, name, self.cleaned_data.get(name))
    portrait.full_clean()
    Portrait.objects.filter(person=person, is_primary=True).exclude(pk=portrait.pk).update(is_primary=False)
    portrait.is_primary = True
    portrait.save()
    person._primary_portrait_link = portrait   # the block re-renders with it (Person.primary_portrait_link)
    self.instance = portrait
    return portrait


# --- Choices: saved on click (cmnsd/edit/choices.html) -------------------

class PersonGenderForm(forms.ModelForm):
  choice = True

  class Meta:
    model = Person
    fields = ['gender']
    labels = {'gender': _("gender")}


class PersonFamilyConnectionForm(forms.ModelForm):
  choice = True

  class Meta:
    model = Person
    fields = ['family_connection']
    labels = {'family_connection': _("family")}


class PersonVisibilityForm(forms.ModelForm):
  choice = True

  class Meta:
    model = Person
    fields = ['visibility']
    labels = {'visibility': _("visible to")}


class PersonStatusForm(StatusActionsForm):
  confirm = {
    'x': _("Delete this person? They will be hidden from everyone - it can be recovered in the admin."),
    'r': _("Revoke this person? Only staff will see them until restored."),
  }

  class Meta(StatusActionsForm.Meta):
    model = Person


# --- Adding a person (PersonCreateView) -------------------------------------

class PersonCreateForm(forms.ModelForm):
  """The names and the basics; everything else is edited on the new
  person's page. Used by /people/new/ (PersonCreateView) and by a picker's
  "+ new person" dialog (Person.api_create_form, cmnsd object_create). Published, visible to signed-in users - like the rest
  of the tree; visibility can be tightened right here."""
  class Meta:
    model = Person
    fields = [*NAME_FIELDS, 'gender', 'family_connection', 'visibility']
    labels = {**NAME_LABELS, 'gender': _("gender"), 'family_connection': _("family"), 'visibility': _("visible to")}
    widgets = {name: forms.TextInput(attrs={'autocomplete': 'off'}) for name in NAME_FIELDS}

  name_fields = NAME_FIELDS   # the template groups these (people/_person_create_fields.html)

  # Adding a child of someone: their token - then the form offers the other
  # parent (prepare). Linking the child to that someone is the caller's
  # job (the picker's add_relative, PersonCreateView).
  child_of = forms.CharField(required=False, widget=forms.HiddenInput)
  # Adding a parent, partner or child of someone (a family picker): their
  # token - the new person takes their family connection (prepare).
  relative_of = forms.CharField(required=False, widget=forms.HiddenInput)

  def prepare(self):
    """With child_of: an "other parent" choice - one of that person's
    partners this user may see, as toggle buttons. None pressed by default:
    an unknown other parent is a fact, not a gap to guess over."""
    if not self.is_bound:
      self._split_typed_name()
    self._inherit_family_connection()
    self.other_parents = {}
    token = (self.data.get('child_of') if self.is_bound else self.initial.get('child_of')) or ''
    request = getattr(self, 'request', None)
    if not token or request is None:
      return
    parent = filter_accessible(Person.objects.all(), request).filter(token=token).first()
    if parent is None:
      return
    partner_ids = [partner.pk for partner in parent.get_partners()]
    partners = filter_accessible(Person.objects.filter(pk__in=partner_ids), request)
    self.other_parents = {partner.token: partner for partner in partners}
    if self.other_parents:
      # Toggle buttons (people/_person_create_fields.html): none pressed =
      # not set; one at most - a child has two parents (cmnsd.js
      # toggles.js keeps one pressed, clean_other_parent checks).
      self.fields['other_parent'] = forms.MultipleChoiceField(
        label=_("other parent"), required=False, widget=forms.CheckboxSelectMultiple,
        choices=[(token, partner.get_full_name()) for token, partner in self.other_parents.items()],
      )

  def _inherit_family_connection(self):
    """A relative of someone (relative_of, or child_of) is family as they
    are: family, possibly family or an outsider - not asked, but said
    (`self.relative`, people/_person_create_fields.html); changeable later
    on the new person's page. Only someone this viewer may see."""
    self.relative = None
    source = self.data if self.is_bound else self.initial
    token = source.get('relative_of') or source.get('child_of') or ''
    request = getattr(self, 'request', None)
    if not token or request is None:
      return
    self.relative = filter_accessible(Person.objects.all(), request).filter(token=token).first()
    if self.relative is None:
      return
    field = self.fields['family_connection']
    field.widget = forms.HiddenInput()
    if not self.is_bound:
      self.initial['family_connection'] = self.relative.family_connection

  def _split_typed_name(self):
    """A picker sends the whole search as ?given_name= ("Emma van der
    Wall"): split off the last name (people/names.py) - known names only
    from people this viewer may see. A last name given already (a child
    gets the parent's) is only taken off the end."""
    typed = (self.initial.get('given_name') or '').strip()
    if not typed:
      return
    last_name = self.initial.get('last_name') or ''
    if last_name:
      if typed.lower().endswith(' ' + last_name.lower()):
        self.initial['given_name'] = typed[:-len(last_name)].strip()
      return
    from .names import split_name
    request = getattr(self, 'request', None)
    people = filter_accessible(Person.objects.all(), request) if request is not None else Person.objects.none()
    self.initial['given_name'], self.initial['last_name'] = split_name(typed, people)

  def clean_other_parent(self):
    chosen = self.cleaned_data.get('other_parent') or []
    if len(chosen) > 1:
      raise forms.ValidationError(_("Choose one other parent at most."))
    return chosen[0] if chosen else ''

  def _save_m2m(self):
    super()._save_m2m()
    # The other parent, once the new person exists - with the family rules
    # and history of people/relatives.py.
    partner = getattr(self, 'other_parents', {}).get(self.cleaned_data.get('other_parent') or '')
    if partner is not None:
      from django.contrib import messages
      from django.core.exceptions import PermissionDenied, ValidationError
      from .relatives import add_relative
      try:
        add_relative(partner, 'child', self.instance.token, self.request)
      except ValidationError as error:
        messages.warning(self.request, ' '.join(error.messages))
      except PermissionDenied:
        messages.warning(self.request, _("The other parent wasn't linked: you may not change them."))

  def save(self, commit=True):
    # Published, like the rest of the tree (the site's default status is
    # concept). The owner is set by the caller (the view, cmnsd
    # object_create).
    self.instance.status = Person.Status.PUBLISHED
    return super().save(commit=commit)
