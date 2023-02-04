from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.shortcuts import redirect
from django.utils.html import escape


from datepicker.models import Event, Attendee, AttendeeOptions

class EventList(ListView):
  model = Event
  def get_context_data(self,*args, **kwargs):
    context = super().get_context_data(**kwargs)
    context['public'] = True
    return context

class EventDetail(DetailView):
  model = Event

  def get_context_data(self,*args, **kwargs):
    context = super().get_context_data(**kwargs)
    context['attendees'] = self.getAttendees()
    context['public'] = True
    return context
  
  def getAttendees(self):
    attendees = {}
    for option in self.object.options.all():
      for attendee in option.attendees.all():
        if not attendee.attendee in attendees:
          attendees[attendee.attendee] = {}
        attendees[attendee.attendee][option] = {'status':attendee.status, 'amount': attendee.amount }
    return attendees
  
class AttendanceForm(UpdateView):
  model = Event
  fields = ['slug']

  def get_success_url(self) -> str:
    return reverse_lazy('datepicker:event', kwargs={ 'slug': self.get_object().slug })
  
  def get_context_data(self,*args, **kwargs):
    context = super().get_context_data(**kwargs)
    context['public'] = True
    if self.request.user.is_authenticated:
      stored = AttendeeOptions.objects.filter(attendee__email=self.request.user.email)
    else:
      stored = None
    context['stored'] = stored
    return context

  ''' Catch form validation errors '''
  def form_invalid(self, form):
    messages.add_message(self.request, messages.WARNING, f"{ 'Form cannot be saved because of the following error(s)'}: { form.errors }")
    return super().form_invalid(form)
  
  ''' Catch form validation errors '''
  def form_valid(self, form):
    ''' Check if attendee exists '''
    if Attendee.objects.filter(email=self.request.POST.get('attendee__email')).count() == 1:
      attendee = Attendee.objects.get(email=self.request.POST.get('attendee__email'))
      messages.add_message(self.request, messages.SUCCESS, f"Welcome back: { attendee }") 
    else:
      attendee = Attendee(name=self.request.POST.get('attendee__name'), email=self.request.POST.get('attendee__email'))
      attendee.save()
      messages.add_message(self.request, messages.SUCCESS, f"Registered new attendee: { attendee }") 
    ''' Loop through options '''
    for option in self.get_object().options.all():
      option_field = 'option-' + str(option.id)
      status = self.request.POST.get(f"option-{ str(option.id) }-status")
      amount = self.request.POST.get(f"option-{ str(option.id) }-amount")
      ''' See if option exists '''
      try:
        option = AttendeeOptions.objects.get(attendee=attendee, option=option)
        if option.status == status and option.amount == amount:
          messages.add_message(self.request, messages.INFO, f"Option: { option }: not changed ")
        else:
          messages.add_message(self.request, messages.INFO, f"Option: { option }: changed from { option.status } to { status } and { option.amount } to { amount } people")
          option.status = status
          option.amount = amount
          option.save() 
        #messages.add_message(self.request, messages.WARNING, f"Option: { escape(option) }: was { option.status } become { status } ")   
      except:
        option = AttendeeOptions(attendee=attendee, option=option, status=status, amount=amount)
        option.save()
        messages.add_message(self.request, messages.INFO, f"Option: { option }: saved with status { status } and amount { amount }")
        pass
    return super().form_valid(form)


