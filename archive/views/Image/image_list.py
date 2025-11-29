from django.views.generic import ListView
from django.urls import reverse, reverse_lazy
from django.shortcuts import redirect
from django.template.defaultfilters import slugify
from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages
from django.utils.translation import gettext as _

from pathlib import Path
from math import floor

from archive.models import Image
from archive.models import Group, Tag, Attachment, Person

from cmnsd.views.cmnsd_filter import FilterMixin
from cmnsd.views.utils__request import RequestMixin

''' Image List View 
    Show a list of images based on filters
'''
class ImageListView(FilterMixin, RequestMixin, ListView):
  model = Image
  template_name = 'archive/images/list.html'
  context_object_name = 'images'
  paginate_by = settings.PAGINATE
  ''' Allow for context to be added by get_queryset '''
  added_context = {}
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'images'
    ''' Default page description '''
    context['page_description'] = f"{ _('Images and documents') }"
    ''' If user filter is active, add user details '''
    if 'user' in self.kwargs:
      context['page_description'] += f" { _('from') } { self.kwargs['user'] }"
    ''' If decade filter is active, add decade details '''
    if 'decade' in self.kwargs:
      decade = floor(int(self.kwargs['decade']) / 10) * 10
      context['page_description'] += f" {_('in the period') } { str(decade) } - { str(decade + 9) }, { _('sorted on date, newest first') }. <br />"  + \
                                    f"{ _('You can also check out')} <a href=\"{reverse_lazy('archive:images-by-decade', args=[decade-10])}\">{ str(decade-10) } - { str(decade-1) }</a> { _('or') } <a href=\"{reverse_lazy('archive:images-by-decade', args=[decade+10])}\">{ str(decade+10) } - { str(decade+20) }</a>"
    ''' If search string is passed '''
    if self.request.GET.get('search', False):
      context['page_description'] += f" { _('searching for') } \"{ self.request.GET.get('search') }\""
    if self.request.GET.get('family', False):
      context['page_description'] += f" { _('with tagged family members of') } \"{ self.request.GET.get('family')[:1].upper() }{ self.request.GET.get('family')[1:].lower() }\""
      context['current_family'] = self.request.GET.get('family', '')
    ''' Categories for filtering '''
    context['categories'] = Image.objects.values_list('category__slug', flat=True).distinct()
    if self.request.GET.get('category', False):
      context['current_category'] = self.request.GET.get('category', '')
    ''' Added context, can be placed by get_queryset() '''
    if len(self.added_context) > 0:
      for key in self.added_context:
        context[key] = self.added_context[key]
    return context


  def get_queryset(self):
    queryset = Image.objects.all()
    ''' Remove Deleted Images '''
    # queryset = queryset.filter(status='p')
    ''' Use CMNSD Filter Mixin to filter '''
    mapping = {
      'tag': 'tag__slug',
      'user': 'user__username',
      'category': 'category__slug',
    }
    queryset = self.filter(queryset, mapping=mapping)
    ''' Process Custom Query '''
    queryset = self.filter_objects(queryset)
    
    queryset = queryset.distinct().order_by('-date_created')
    self.added_context['total_images'] = queryset.count()
    return queryset
  
  ''' Show Hidden Files
      Returns True if hidden files should be displayed  
  '''
  def show_hidden_files(self) -> bool:
    result = False
    ''' Check Preferences '''
    if hasattr(self.request.user, 'preference'):
      if self.request.user.preference.show_hidden_files == True:
        result = True
    ''' Check querystring argument, overriding pereference '''
    if self.request.GET.get('hidden', False):
      if self.request.GET.get('hidden').lower() == 'true':
        result = True
      else:
        result = False
    return result
  
  ''' Process Search and Visibility Filter to Queryset '''
  def filter_objects(self, queryset):
    ''' Show or hide hidden images '''
    if self.show_hidden_files():
      ''' Show how many images can be hidden'''
      self.added_context['images_hidden'] = queryset.filter(visibility_frontpage=False).count() * -1
    else:
      if queryset.filter(visibility_frontpage=False).count() > 0:
        ''' Show how many images are hidden '''
        self.added_context['images_hidden'] = queryset.filter(visibility_frontpage=False).count()
        queryset = queryset.exclude(visibility_frontpage=False)
      else:
        ''' No images available to hide '''
        self.added_context['images_hidden'] =  False
    ''' Loved images '''
    if self.request.user.is_authenticated and hasattr(self.request.user, 'preference'):
      if self.request.GET.get('loved', 'false') != 'false':
        queryset = queryset.filter(slug__in=self.request.user.preference.favorites.values_list('slug', flat=True))

    ''' Return filtered queryset '''
    return queryset