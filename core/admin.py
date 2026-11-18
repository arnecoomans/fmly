from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.db.models import Q
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _

from cmnsd.admin.login_links import LoginLinkUserAdminMixin
from cmnsd.admin.mixins import (
  TimestampAdminMixin, StatusAdminMixin, VisibilityAdminMixin, OwnershipAdminMixin,
  HierarchyAdminMixin, TranslationAliasAdminMixin,
)
from .models import Tag, Comment, Preferences


@admin.register(Tag)
class TagAdmin(
  TimestampAdminMixin, StatusAdminMixin, VisibilityAdminMixin, OwnershipAdminMixin,
  HierarchyAdminMixin, TranslationAliasAdminMixin,
  admin.ModelAdmin,
):
  list_display = ('name',)
  search_fields = ('name', 'slug', 'description')
  actions = [
    'mark_status_c', 'mark_status_p', 'mark_status_r', 'mark_status_x',
    'mark_visibility_p', 'mark_visibility_c', 'mark_visibility_f', 'mark_visibility_q',
    'refetch_translation_aliases',
  ]


@admin.register(Comment)
class CommentAdmin(TimestampAdminMixin, StatusAdminMixin, OwnershipAdminMixin, admin.ModelAdmin):
  # No Visibility - Comment doesn't compose that mixin.
  list_display = ('__str__', 'target', 'status')
  actions = ['mark_status_c', 'mark_status_p', 'mark_status_r', 'mark_status_x']


@admin.register(Preferences)
class PreferencesAdmin(TimestampAdminMixin, admin.ModelAdmin):
  # No Status/Visibility/Ownership - Preferences composes only TimestampMixin.
  list_display = ('user', 'language')
  filter_horizontal = ('family',)


class PersonChoiceField(forms.ModelChoiceField):
  """A person by name and year of birth - namesakes apart. The years come
  in one query for all choices (set_years), not one per person."""

  years = {}

  def label_from_instance(self, person):
    year = self.years.get(person.pk)
    return f"{person} ({year})" if year else str(person)


class AccountChangeForm(UserChangeForm):
  """Django's user form, plus the account's person (Person.related_user -
  the link lives on the person): "what is this person to you" and "your
  own record" follow from it. Only living people without an account yet
  (an account holder is alive: anyone with a death event - "died, details
  unknown" too - is left out), or this account's own; never a deleted
  person. The most likely ones first (people.names.likely_people)."""

  person = PersonChoiceField(
    queryset=None, required=False, label=_("person"),
    help_text=_("Who this account is in the family tree. Only living people without an account yet."),
  )

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    from events.models import Event
    from people.models import Person
    from people.names import likely_people
    user = self.instance
    field = self.fields['person']
    died = Event.objects.current().filter(kind=Event.Kind.DEATH).values('people')
    free = Q(related_user__isnull=True) & ~Q(pk__in=died)
    field.queryset = (
      Person.objects.exclude(status=Person.Status.DELETED)
      .filter(free | Q(related_user=user.pk))
      .order_by('last_name', 'given_name', 'pk')
    )
    field.years = dict(
      Event.objects.current().filter(kind=Event.Kind.BIRTH, year__isnull=False).values_list('people', 'year')
    )
    field.initial = getattr(user, 'person', None) if user.pk else None
    # The most likely people first, by the account's name and address
    # (people.names.likely_people) - suggested, never chosen for you.
    # Then everyone else by how they belong: family, possibly family,
    # outsiders - an account is nearly always family.
    people = list(field.queryset)
    suggested = likely_people(user, people) if user.pk else []
    label = field.label_from_instance
    groups = [(capfirst(_("suggested")), suggested)] if suggested else []
    for connection, title in (
      (Person.FamilyConnection.FAMILY, _("family")),
      (Person.FamilyConnection.POSSIBLY_FAMILY, _("possibly family")),
      (Person.FamilyConnection.OUTSIDER, _("outsiders")),
    ):
      members = [person for person in people if person.family_connection == connection and person not in suggested]
      if members:
        groups.append((capfirst(title), members))
    field.choices = [('', field.empty_label)] + [(title, [(person.pk, label(person)) for person in members]) for title, members in groups]

  def save_person(self, user):
    """Link the chosen person to `user` - and unlink whoever it was before."""
    from people.models import Person
    chosen = self.cleaned_data.get('person')
    Person.objects.filter(related_user=user).exclude(pk=getattr(chosen, 'pk', None)).update(related_user=None)
    if chosen is not None and chosen.related_user_id != user.pk:
      Person.objects.filter(pk=chosen.pk).update(related_user=user)


# Users: Django's own admin, plus the account's person and "send login
# link" and their links (cmnsd/login_links.py) - while CMNSD_LOGIN_LINKS is on.
admin.site.unregister(get_user_model())


@admin.register(get_user_model())
class UserAdmin(LoginLinkUserAdminMixin, DjangoUserAdmin):
  form = AccountChangeForm
  # Under personal info, next to the name and address.
  fieldsets = tuple(
    (title, {**options, 'fields': (*options['fields'], 'person')}) if options['fields'] == ('first_name', 'last_name', 'email') else (title, options)
    for title, options in DjangoUserAdmin.fieldsets
  )

  def save_model(self, request, obj, form, change):
    super().save_model(request, obj, form, change)
    if hasattr(form, 'save_person'):
      form.save_person(obj)
