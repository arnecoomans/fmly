from django.views.generic import DetailView
from django.shortcuts import redirect
from django.conf import settings
from django.contrib import messages
from django.utils.translation import gettext as _


from archive.models import Image
# from archive.models import Group, Tag, Attachment, Person

''' ImageRedirectView
    Redirects calls to object/{id} to object/{id}/{slug}/ for seo purposes
'''
class ImageRedirectView(DetailView):
  model = Image
  context_object_name = 'images'

  def get(self, request, *args, **kwargs):
    ''' Fetch image to read title '''
    image = Image.objects.get(pk=self.kwargs['pk'])
    ''' Get title or use default '''
    title = 'needs a title' if image.title == '' else image.title
    ''' Redirect to proper view '''
    return redirect('archive:image', image.slug)


''' ImageView'''


class ImageView(DetailView):
  model = Image
  template_name = 'archive/images/detail.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'images'
    return context
