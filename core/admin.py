from django.contrib import admin

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
