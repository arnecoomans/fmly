from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from cmnsd.admin.mixins import (
  TimestampAdminMixin, StatusAdminMixin, VisibilityAdminMixin, OwnershipAdminMixin,
)
from events.models import Event
from .models import Person, PersonRelation


class RelationsFromInline(admin.TabularInline):
  # Rows where this person is person_from: their children (PARENT) and,
  # for PARTNER rows, their partner if this person has the lower pk (see
  # PersonRelation.save() - canonical ordering means a given PARTNER row
  # only ever shows on one side, not both).
  model = PersonRelation
  fk_name = 'person_from'
  extra = 0
  verbose_name = 'relation (as person_from)'
  verbose_name_plural = 'relations where this person is person_from'
  autocomplete_fields = ('person_to',)


class RelationsToInline(admin.TabularInline):
  # Mirror of RelationsFromInline: rows where this person is person_to -
  # their parents (PARENT) and, for PARTNER rows, their partner if this
  # person has the higher pk.
  model = PersonRelation
  fk_name = 'person_to'
  extra = 0
  verbose_name = 'relation (as person_to)'
  verbose_name_plural = 'relations where this person is person_to'
  autocomplete_fields = ('person_from',)


class PersonEventInline(admin.TabularInline):
  """This person's events (Event.people - the link lives on Event, so it's
  edited here through the M2M's through table), in date order. Pick an
  existing event (autocomplete, EventAdmin.search_fields) or create one
  with the + next to it; "edit" opens the event itself for its date,
  places and other people."""
  model = Event.people.through
  extra = 0
  autocomplete_fields = ('event',)
  fields = ('event', 'kind', 'date', 'edit')
  readonly_fields = ('kind', 'date', 'edit')
  verbose_name = "event"
  verbose_name_plural = "events"

  def get_queryset(self, request):
    return super().get_queryset(request).select_related('event').order_by(
      'event__year', 'event__month', 'event__day',
    )

  @admin.display(description="kind")
  def kind(self, obj):
    return obj.event.kind_freetext or obj.event.get_kind_display() if obj.pk else '-'

  @admin.display(description="date")
  def date(self, obj):
    return (obj.event.partial_date_display() or '-') if obj.pk else '-'

  @admin.display(description="")
  def edit(self, obj):
    if not obj.pk:
      return ''
    return format_html('<a href="{}">edit</a>', reverse('admin:events_event_change', args=[obj.event_id]))


@admin.register(Person)
class PersonAdmin(
  TimestampAdminMixin, StatusAdminMixin, VisibilityAdminMixin, OwnershipAdminMixin,
  admin.ModelAdmin,
):
  list_display = ('get_full_name', 'family_connection', 'status', 'visibility', 'private')
  list_filter = ('family_connection',)
  search_fields = ('given_name', 'called_name', 'last_name', 'married_name', 'nickname')
  filter_horizontal = ('tags',)
  inlines = [RelationsFromInline, RelationsToInline, PersonEventInline]
  actions = [
    'mark_status_c', 'mark_status_p', 'mark_status_r', 'mark_status_x',
    'mark_visibility_p', 'mark_visibility_c', 'mark_visibility_f', 'mark_visibility_q',
  ]


@admin.register(PersonRelation)
class PersonRelationAdmin(admin.ModelAdmin):
  # No cmnsd mixins - PersonRelation deliberately composes none (see
  # PersonRelations.py: it's a plain link table, not project-specific).
  list_display = ('person_from', 'relation_type', 'person_to')
  list_filter = ('relation_type',)
