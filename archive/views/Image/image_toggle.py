from django.db.models.base import Model as Model
from django.db.models.query import QuerySet
from django.views.generic.edit import CreateView, UpdateView
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.template.defaultfilters import slugify
from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages
from django.utils.translation import gettext as _

from html import escape

from archive.models import Image
from archive.models import Preference


class ToggleFavoriteImage(UpdateView):
  model = Preference
  fields = ['favorites']

  def get_object(self):
    return Preference.objects.get_or_create(user=self.request.user)[0]
  
  def get(self, *args, **kwargs):
    ''' Fetch Profile '''
    profile = self.get_object()

    ''' Fetch Image '''
    try:
      image = Image.objects.get(slug=self.kwargs['slug'])
    except Image.DoesNotExist:
      messages.add_message(self.request, messages.ERROR, f"{ _('image to love not found') }.")
      return redirect('archive:images')
    ''' Toggle favorite status of image '''
    if image in profile.favorites.all():
      profile.favorites.remove(image)
      messages.add_message(self.request, messages.SUCCESS, f"{ _('i see you stopped loving') } { image.title }.")
    else:
      profile.favorites.add(image)
      messages.add_message(self.request, messages.SUCCESS, f"{ _('i see you love') } { image.title }.")      
    profile.save()
    return redirect('archive:image', image.slug)
