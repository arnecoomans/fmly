from django.contrib import admin
from datepicker.models import *
# Register your models here.
admin.site.register(attendee.Attendee)
admin.site.register(attendeeoptions.AttendeeOptions)
admin.site.register(event.Event)
admin.site.register(option.Option)