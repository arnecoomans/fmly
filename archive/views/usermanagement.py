from django.views.generic.edit import UpdateView
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.contrib.auth.forms import UserCreationForm

from archive.models.preference import Preference

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
  form_class = UserCreationForm
  success_url = reverse_lazy('login')
  template_name = 'registration/user_register_form.html'
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['register'] = True
    return context