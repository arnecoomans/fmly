from django import forms
from django.forms import ClearableFileInput
#from django.contrib.auth.models import User
#from django.contrib.auth.forms import UserCreationForm

#from .models import Document

# Multiple File Upload
class ImagesUploadForm(forms.Form):
    # Keep name to 'file' because that's what Dropzone is using
    source = forms.ImageField(required=True)
#class ImagesUploadForm(forms.Form):
#  file_field = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}))