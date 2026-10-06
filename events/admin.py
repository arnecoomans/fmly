from django.contrib import admin

from cmnsd.admin.mixins import TimestampAdminMixin, OwnershipAdminMixin
from content.models import Content
from .models import Event


class EventContentInline(admin.TabularInline):
  """The content documenting this event (Content.events - the link lives
  on Content, so it's edited here through the M2M's through table).
  Autocomplete searches the content admin's search_fields."""
  model = Content.events.through
  extra = 0
  autocomplete_fields = ('content',)
  verbose_name = "linked content"
  verbose_name_plural = "linked content"


@admin.register(Event)
class EventAdmin(TimestampAdminMixin, OwnershipAdminMixin, admin.ModelAdmin):
  # No Status/Visibility - Event doesn't compose those mixins.
  list_display = ('__str__', 'kind', 'year', 'month', 'day')
  list_filter = ('kind',)
  # Also what the person admin's event autocomplete searches.
  search_fields = ('title', 'kind_freetext', 'description', 'people__given_name', 'people__called_name', 'people__last_name', 'year')
  autocomplete_fields = ('people', 'places')
  inlines = [EventContentInline]
