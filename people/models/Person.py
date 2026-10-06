from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from cmnsd.models.mixins import (
  TimestampMixin, TokenMixin, StatusMixin, OwnershipMixin,
  VisibilityMixin, SearchableMixin, SlugMixin, EditableRelationsMixin,
)

from cmnsd.models.access import filter_accessible
from core.models import CommentableMixin, Tag

from .PersonManager import PersonManager
from .FamilyShorthand import FamilyShorthand
from .EventShorthand import EventShorthand
from .RelationshipLabel import RelationshipLabel
from .SectionShorthand import SectionShorthand
from .RelativesEditing import RelativesEditing

from cmnsd.api.registry import api_model, api_field

@api_model(search_fields=['given_name', 'called_name', 'last_name', 'married_name', 'nickname', 'biography'])
class Person(TimestampMixin, TokenMixin, SlugMixin, StatusMixin, OwnershipMixin, VisibilityMixin,
             FamilyShorthand, EventShorthand, RelationshipLabel, SectionShorthand, CommentableMixin,
             EditableRelationsMixin, RelativesEditing, models.Model):
  class Gender(models.TextChoices):
    MALE = "m", _("male")
    FEMALE = "f", _("female")
    OTHER = "o", _("other")
    UNKNOWN = "x", _("unknown")

  given_name = models.CharField(max_length=255, blank=True, help_text=_("All official first name(s) of the person"))
  called_name = models.CharField(max_length=255, blank=True, help_text=_("The name the person is commonly called by, if different from the given name"))
  last_name = models.CharField(max_length=255, blank=True,  help_text=_("Last name of the person at birth"))
  married_name = models.CharField(max_length=255, blank=True, help_text=_("Married name of the person, if any"))
  nickname = models.CharField(max_length=255, blank=True, help_text=_("Nickname of the person, if any"))

  class FamilyConnection(models.TextChoices):
    FAMILY = 'family', _('family')
    POSSIBLY_FAMILY = 'possibly_family', _('possibly family')
    OUTSIDER = 'outsider', _('outsider')

  gender = models.CharField(max_length=1, choices=Gender.choices, default=Gender.UNKNOWN)

  # How this person relates to the family: in the tree, suspected but not
  # proven (e.g. a namesake whose link isn't found yet), or an outsider -
  # relevant to the archive (an author, a historical figure, a friend) but
  # not related. One model for all three, so "possibly family" can become
  # "family" by changing this field. Filterable in the list API.
  family_connection = api_field(readonly=True)(models.CharField(
    max_length=20, choices=FamilyConnection.choices, default=FamilyConnection.FAMILY,
    help_text=_("How this person relates to the family"),
  ))

  biography =models.TextField(blank=True)

  # Relationships
  private = models.BooleanField(default=False, help_text=_("If checked, this person still appears in the family tree but has no clickable detail page - for people who are part of the tree (e.g. living relatives) but not represented with viewable details"))
  related_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='person', help_text=_("The user account associated with this person, if any"))

  tags = models.ManyToManyField(Tag, blank=True, related_name='people', help_text=_("Tags for categorizing or labeling this person"))

  objects = PersonManager()
  # Dismissed from a loose end ("fine as it is", dashboard.LooseEndDismissal):
  # the rows go with the item.
  loose_end_dismissals = GenericRelation('dashboard.LooseEndDismissal')

  # Edit mode (cmnsd object_form): block -> form (dotted: people/forms.py
  # imports this model). The page shows person/blocks/<block>.html. Birth
  # and death edit the person's birth/death Event (created when missing).
  # Not here: private and the linked user account - the admin's.
  api_edit_forms = {
    'names': 'people.forms.PersonNamesForm',
    'portrait': 'people.forms.PersonPortraitForm',
    'biography': 'people.forms.PersonBiographyForm',
    'birth': 'people.forms.PersonBirthForm',
    'death': 'people.forms.PersonDeathForm',
    'gender': 'people.forms.PersonGenderForm',
    'family_connection': 'people.forms.PersonFamilyConnectionForm',
    'visibility': 'people.forms.PersonVisibilityForm',
    'status': 'people.forms.PersonStatusForm',
  }

  # A new person from a picker's "+ new person" dialog (cmnsd object_create)
  # - the same form as /people/new/.
  api_create_form = 'people.forms.PersonCreateForm'

  # Edit mode: tags (EditableRelationsMixin link/unlink). Family links are
  # add_relative/remove_relative (RelativesEditing).
  api_editable_relations = {
    'tags': {'create': {'status': 'p', 'visibility': 'c'}},
  }

  class Meta:
    ordering = ['last_name', 'given_name', 'married_name', 'called_name', 'nickname']
    indexes = [
      models.Index(fields=['last_name', 'given_name']),
      models.Index(fields=['slug']),
    ]
    verbose_name = _("Person")
    verbose_name_plural = _("People")

  def __str__(self):
    return self.get_full_name() or f"Person {self.id}"

  def get_absolute_url(self):
    # private: no address where nobody asks who's looking (the admin's
    # "view on site") - the page itself opens for the person and their
    # parents and staff (people/privacy.py); page_url_for() decides per viewer.
    if self.private:
      return None
    return self.page_url()

  def page_url(self):
    """The page's address, private or not - for code that checked access."""
    return reverse('people:person_detail', kwargs={'token': self.token, 'slug': self.slug})

  def page_url_for(self, user):
    """The page's address if this user may open it as far as `private`
    goes - the person themself, their parents and staff (people/privacy.py) -
    else None: their name shows without a link."""
    from ..privacy import may_open_page
    return self.page_url() if may_open_page(self, user) else None

  def get_list_url(self):
    """Where to go when this person is gone for the viewer (set to
    deleted in edit mode - cmnsd object_form)."""
    return reverse('people:person_list')

  def get_full_name(self):
    if not any((self.given_name, self.last_name, self.married_name, self.called_name, self.nickname)):
      return f"{_('person')} {self.id}"
    parts = []
    if self.given_name:
      parts.append(self.given_name)
    if self.nickname:
      parts.append(f"({self.nickname})")
    if self.married_name:
      parts.append(self.married_name)
      if self.last_name:
        parts.append(f"({_('née')} {self.last_name})")
    elif self.last_name:
      parts.append(self.last_name)
    if not parts:
      # given_name/nickname/married_name/last_name were all blank - clean()
      # only requires *one* of the five name fields, so called_name alone
      # must still produce a name here, not silently disappear.
      parts.append(self.called_name)
    return " ".join(parts)

  def get_short_name(self):
    """A shorter version of the name, for use in lists and other places where
    a full name is too long. Uses called_name if available, otherwise
    given_name, otherwise nickname, otherwise married_name, otherwise
    last_name."""
    first_name = self.called_name or self.given_name or self.nickname
    last_name = self.last_name or self.married_name
    # Build from only the truthy parts and join, rather than an f-string
    # with a possible None - get_full_name() does the same for the same
    # reason: f"{None}" renders the literal word "None" (e.g. a person with
    # only last_name set would otherwise produce "None Smith").
    parts = [part for part in (first_name, last_name) if part]
    if not parts:
      return f"{_('person')} {self.id}"
    return " ".join(parts)
  
  def initials(self):
    """First-name/last-name initials, for the avatar fallback when there's no photo."""
    first = self.given_name or self.called_name or self.nickname
    last = self.last_name or self.married_name
    letters = [name[0] for name in (first, last) if name]
    return "".join(letters).upper() or "?"

  def other_parent(self, known_parent):
    """The other recorded parent of self, given an already-known parent -
    e.g. child.other_parent(viewed_person) when grouping a person's
    children by co-parent on the parent's own detail page (see
    CSS_BRIEFING.md section 2). Returns None if there's no other parent
    recorded. Confirmed against real data that no child currently has more
    than 2 recorded parents, so the ambiguous 3+ case shouldn't occur
    today - but this degrades to None (the "not recorded" bucket) rather
    than guessing if it ever does, instead of assuming exactly one match."""
    others = [p for p in self._get_parents_flat() if p.pk != known_parent.pk]
    return others[0] if len(others) == 1 else None

  @api_field(readonly=True)
  def get_tags(self, request=None):
    """This person's tags, filtered to whichever this viewer can see -
    status and visibility (cmnsd filter_accessible), so a deleted tag
    disappears too. Visibility is a filtering concern here, not a per-tag
    rendering check (CSS_BRIEFING.md section 2's Tags subsection): a
    private tag is just absent from this list for a viewer who can't see
    it, so the template never checks tag visibility itself. request=None
    (anonymous/no request) still returns public tags, unlike
    get_relation_to_user() - showing tags is useful without a viewer
    identity; relating to a viewer isn't."""
    return filter_accessible(self.tags.all(), request)

  @property
  def primary_portrait_link(self):
    """The primary content.Portrait (photo + crop) for this person's
    avatar, or None - regardless of who's looking; use content_tags'
    visible_portrait filter to render it. Reads the batch-attached value
    when a list attached one (FamilyShorthand._attach_portraits())."""
    if not hasattr(self, '_primary_portrait_link'):
      from content.models import Portrait
      self._primary_portrait_link = (
        Portrait.objects.filter(person=self, is_primary=True).select_related('content').first()
      )
    return self._primary_portrait_link

  @classmethod
  def comment_targets(cls, queryset):
    # CommentableMixin: a private person has no page, so their comments
    # stay out of the comment list (there's nothing to link to).
    return queryset.filter(private=False)

  def get_slug_source(self):
    # SlugMixin: set once from the full name, then fixed. The URL is led by
    # the token (person/<token>/<slug>/); the slug stays fixed because old
    # person/<slug>/ links in texts still find people by it (person_redirect).
    return self.get_full_name()

  def save(self, *args, **kwargs):
    # Validate the model before saving
    # Run a full clean, so clean() is called and all field validators are run
    self.full_clean()
    super().save(*args, **kwargs)

  def clean(self):
    # Ensure that at least one of the name fields is provided
    if not any((self.given_name, self.last_name, self.married_name, self.called_name, self.nickname)):
      raise ValidationError(_("A person needs at least one of given names, last name, married name, called name or nickname."))

  # Family relation shortcuts (get_children/get_parents/get_partners/
  # get_siblings) live in FamilyShorthand; event shortcuts
  # (get_birth_event/get_death_event) live in EventShorthand - see those
  # files, not here.
