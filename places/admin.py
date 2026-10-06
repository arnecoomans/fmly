from django.contrib import admin

from cmnsd.admin.mixins import TimestampAdminMixin, OwnershipAdminMixin, HierarchyAdminMixin
from .models import Place


@admin.register(Place)
class PlaceAdmin(TimestampAdminMixin, OwnershipAdminMixin, HierarchyAdminMixin, admin.ModelAdmin):
  # No Status/Visibility - Place doesn't compose those mixins.
  list_display = ('name', 'alias')
  search_fields = ('name', 'alias', 'description')
