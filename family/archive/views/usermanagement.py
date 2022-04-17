from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.contrib.auth.forms import UserCreationForm


# USER MANAGEMENT
class SignUpView(CreateView):
  form_class = UserCreationForm
  success_url = reverse_lazy('login')
  template_name = 'registration/user_register_form.html'
  #success_message = "Your profile was created successfully"