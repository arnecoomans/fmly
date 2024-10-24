from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView
from django.shortcuts import redirect, reverse
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.models import User
from django.conf import settings
from django.http import JsonResponse
from django.utils.html import strip_tags
import markdown

from archive.models import Person

class AddPerson(CreateView):
  model = Person
  template_name = 'archive/people/addperson.html'
  fields = ['first_names', 'last_name']
