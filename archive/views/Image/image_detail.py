from django.views.generic import DetailView
from django.shortcuts import redirect
from django.conf import settings
from django.utils.translation import gettext as _


from archive.models import Image

''' ImageRedirectView
    Redirects calls to object/{id} to object/{id}/{slug}/ for seo purposes
'''
class ImageRedirectView(DetailView):
  model = Image
  context_object_name = 'images'

  def get(self, request, *args, **kwargs):
    ''' Fetch image to read title '''
    image = Image.objects.get(pk=self.kwargs['pk'])
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