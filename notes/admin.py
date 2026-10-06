from django.contrib import admin

from .models import Note


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
  list_display = ('__str__', 'kind', 'status', 'visibility', 'user', 'date_modified')
  list_filter = ('kind', 'status', 'visibility')
  search_fields = ('title', 'body')
  autocomplete_fields = ('people', 'content', 'places', 'events', 'tags', 'related_notes')
  readonly_fields = ('token', 'date_created', 'date_modified')
