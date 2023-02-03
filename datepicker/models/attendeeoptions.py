from django.db import models

from .attendee import Attendee
from .option import Option

class AttendeeOptions(models.Model):
  attendee            = models.ForeignKey(Attendee, on_delete=models.DO_NOTHING, related_name='options')
  option              = models.ForeignKey(Option, on_delete=models.DO_NOTHING, related_name='attendees')
  STATUS_CHOICES = [
    ('Y', 'yes'),
    ('N', 'no'),
    ('M', 'maybe'),
    ('U', 'unknown'),
  ]
  status              = models.CharField(max_length=1, choices=STATUS_CHOICES, default='U')
  amount              = models.PositiveSmallIntegerField(default=1)
  comment             = models.TextField(null=True, blank=True)

  date_created        = models.DateTimeField(auto_now_add=True)
  date_modified       = models.DateTimeField(auto_now=True)
  
  def __str__(self) -> str:
    return f"{ self.attendee } op { self.option }"
  