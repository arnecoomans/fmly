from django.contrib import admin
from datepicker.models import *

class eventAdmin(admin.ModelAdmin):
  prepopulated_fields = {'slug': ('title',)}
  def get_changeform_initial_data(self, request):
    get_data = super(eventAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data

class optionAdmin(admin.ModelAdmin):
  
  def get_changeform_initial_data(self, request):
    get_data = super(optionAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data


# Register your models here.
admin.site.register(attendee.Attendee)
admin.site.register(attendeeoptions.AttendeeOptions)
admin.site.register(event.Event, eventAdmin)
admin.site.register(option.Option, optionAdmin)