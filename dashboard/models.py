from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _


class LooseEndDismissal(models.Model):
  """"Fine as it is" for one item in one loose end (dashboard/blocks.py
  LOOSE_ENDS): it leaves that check - and its count - not the others (a
  clipping as sharp as it gets is still a photo without people). Who and
  when, and why if they said. Any model (generic foreign key: content,
  people, events); removed with its item (a GenericRelation on each,
  as comments are). Maintenance only - never shown in the archive itself."""
  content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
  object_id = models.PositiveIntegerField()
  target = GenericForeignKey('content_type', 'object_id')
  name = models.CharField(max_length=50, help_text=_("The loose end (dashboard/blocks.py LOOSE_ENDS)"))
  user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
  note = models.CharField(max_length=255, blank=True)
  date_created = models.DateTimeField(auto_now_add=True)

  class Meta:
    constraints = [
      models.UniqueConstraint(fields=['content_type', 'object_id', 'name'], name='dashboard_dismissal_once_per_check'),
    ]
    ordering = ['-date_created']

  def __str__(self):
    return f"{self.name}: {self.content_type.model} {self.object_id}"
