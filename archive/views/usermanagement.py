from django.views.generic.edit import UpdateView
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.contrib.auth.models import User
from django.utils.translation import gettext as _
from django.contrib import messages
from django.shortcuts import redirect
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from archive.models.preference import Preference
from django.contrib.auth.models import Group
from django.conf import settings


''' Preferences '''
class PreferencesView(UpdateView):
  model = Preference
  template_name = 'archive/settings/edit.html'
  fields = ['show_hidden_files', 'show_new_uploads']

  def get_object(self):
    if Preference.objects.filter(user=self.request.user.id).count() > 0:
      object = Preference.objects.get(user=self.request.user.id)
    else:
      object = Preference(user=self.request.user)
      object.save()
    return object
  
  def get_success_url(self) -> str:
    return reverse_lazy('archive:settings')
    

''' Sign-up '''
class SignUpView(CreateView):
  model = User
  #form_class = UserCreationForm
  success_url = reverse_lazy('archive:signup')
  template_name = 'registration/user_register_form.html'
  fields = ['password', 'first_name', 'last_name', 'email']

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['register'] = True
    return context
  
  def form_invalid(self, form):
    messages.add_message(self.request, messages.INFO, 'invalid form: ' + str(form.errors))
    return super().form_invalid(form)

  def form_valid(self, form):
    ''' Process form input '''
    username = form.cleaned_data['email'].lower()
    email = form.cleaned_data['email']
    password = form.cleaned_data['password']
    first_name = form.cleaned_data['first_name']
    last_name = form.cleaned_data['last_name']
    ''' Username validation 
        Username and e-mail should be unique. In rare cases that username is not the same as e-mail 
        (legacy users, superuser), avoid that the email is re-used for registering an account.
    '''
    objects = User.objects.filter(username=username) | User.objects.filter(email=email)
    if objects.count() > 0:
      messages.add_message(self.request, messages.ERROR, f"{ _('Error when registering') }:<br>{ _('Username or e-mail is already registered') }. { _('You can') } <a href=\"\">{ _('log in here') }</a>.")
      return redirect(reverse_lazy('archive:signup'))  
    ''' Password validation
    '''
    try:
      validate_password(password, user=username)
    except ValidationError as e:
      messages.add_message(self.request, messages.ERROR, f"{ _('Your password does not meet the requirements') }:<br> { '.<br>'.join(e) }")
      return redirect(reverse_lazy('archive:signup'))  
    if username.lower() == password.lower() or password.lower() in username.lower() or username.lower() in password.lower():
      messages.add_message(self.request, messages.ERROR, f"{ _('Your password does not meet the requirements') }:<br> { _('The password cannot overlap with the username') }.")
      
      return redirect(reverse_lazy('archive:signup'))  
    ''' Create new user '''
    user = User.objects.create_user(username, email, password, first_name=first_name, last_name=last_name)
    user.save()
    messages.add_message(self.request, messages.SUCCESS, _('Succesfully registered your account. Please log in with your e-mail address and chosen password. '))
    ''' Set default groups '''
    if hasattr(settings, 'NEW_USER_DEFAULT_GROUP'):
      group = Group.objects.get(name=settings.NEW_USER_DEFAULT_GROUP)
      group.user_set.add(user)
    ''' Redirect to login page '''
    return redirect(reverse_lazy('archive:home'))

  