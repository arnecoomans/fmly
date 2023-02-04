from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum


from .event import Event
#from .attendeeoptions import AttendeeOptions

class Option(models.Model):
  event               = models.ForeignKey(Event, on_delete=models.DO_NOTHING, related_name='options')

  event_start         = models.DateTimeField()
  event_end           = models.DateTimeField()

  date_created        = models.DateTimeField(auto_now_add=True)
  date_modified       = models.DateTimeField(auto_now=True)
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  is_deleted          = models.BooleanField(default=False)

  def __str__(self) -> str:
    return f"{ str(self.event) }: { self.event_start }"
  
  def confirmedAttendees(self):
    return self.attendees.filter(status='Y')
  
  def totalAttendees(self):
    return self.confirmedAttendees().aggregate(Sum('amount'))

  class Meta:
    ordering = ['event_start']