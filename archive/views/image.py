from django.views import generic
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormView

from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.template.defaultfilters import slugify

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from math import floor

from archive.models import Image, Person


class RecentImageListView(generic.ListView):
  context_object_name = 'images'
  paginate_by = 12

  def get_queryset(self):
    return Image.objects.filter(is_deleted=False).filter(show_in_index=True).order_by('-uploaded_at')

# Renamed DocumentView to ImageView
class ImageView(generic.DetailView):
  model = Image

## Add Image / Images
# Renamed AddImage to AddImageView
class AddImageView(PermissionRequiredMixin, CreateView):
  permission_required = 'archive.create_document'
  model = Image
  fields = ['source']
  success_url = reverse_lazy('archive:image')

  template_name = 'images/image_single_upload.html'

  def form_valid(self, form):
    form.instance.user = self.request.user
    form.instance.title = self.request.FILES['source'].name
    form.instance.show_in_index = False
    return super().form_valid(form)

# Renamed AddImages to AddImagesView
class AddImagesView(PermissionRequiredMixin, CreateView):
  permission_required = 'archive.create_document'
  model = Image
  fields = ['source']
  success_url = reverse_lazy('archive:my-images')
  template_name = 'images/image_multi_upload.html'
  
  def form_valid(self, form):
    form.instance.user = self.request.user
    form.instance.title = self.request.FILES['source'].name
    form.instance.show_in_index = False
    return super().form_valid(form)

class EditImageView(PermissionRequiredMixin, UpdateView):
  permission_required = 'archive.change_document'  

  model = Image
  fields = ['title', 'description',
            'document_source', 'date', 'year',
            'people', 'tag',
            'in_group',
            'attachments',
            'show_in_index']
  #fields = '__all__'
    
  def form_valid(self, form):
    form.instance.user = self.request.user
    return super().form_valid(form)


## Special views

# Renamed DocumentPreviewListView to RecentImageListPreView
class RecentImageListPreView(generic.ListView):
  # Returns a single page of documents without login.
  context_object_name = 'images'
  paginate_by = 12

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['page_scope'] = 'voorbeelddocumenten'
    context['page_description'] = 'In dit overzicht zie je een voorbeeld hoe documenten worden weergegeven. Wil je meer zien of details bekijken? Neem contact op.'
    context['preview'] = True
    return context
  def get_queryset(self):
    return Image.objects.filter(is_deleted=False).filter(show_in_index=True).order_by('-uploaded_at')[:12]

# Renamed DocumentDecadeView to ImageDecadeListView
class ImageDecadeListView(generic.ListView):
  #template_name = 'archive/documents-decade.html'
  template_name = 'archive/images/images-list.html'
  context_object_name = 'images'

  paginate_by = 12

  def get_decade(self, **kwargs):
    return floor(int(self.kwargs['decade']) / 10) * 10
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    #decade = floor(int(self.kwargs['decade']) / 10) * 10
    context['page_scope'] = 'documenten in periode ' + str(self.get_decade()) + ' - ' + str(self.get_decade() + 9)
    #context['page_scope'] = 'documenten in periode ' + str(decade) + ' - ' + str(decade + 9)
    return context

  def get_queryset(self):
    #decade = floor(int(self.kwargs['decade']) / 10) * 10
    return Image.objects.filter(is_deleted=False).filter(year__gte=self.get_decade()).filter(year__lte=self.get_decade()+9).order_by('-year')

# Renamed DocumentYearView to ImageYearRedirectView
class ImageYearRedirectView(generic.DetailView):
  model = Image
  context_object_name = 'images'
  def get(self, request, *args, **kwargs):
    decade = floor(int(self.kwargs['year']) / 10) * 10
    return redirect('archive:images-by-decade', decade)


# Renamed DocumentRedirectView to ImageRedirectView
class ImageRedirectView(generic.DetailView):
  # redirect /document/1/ to /document/1/title-included/
  model = Image
  context_object_name = 'images'
  def get(self, request, *args, **kwargs):
    # Redirect to document with slug
    image = Image.objects.get(pk=self.kwargs['pk'])
    title = 'needs a title' if image.title == '' else image.title
    return redirect('archive:image', image.id, slugify(title) )

# Renamed MyDocumentList to ImageListByUserView
class ImageListByUserView(generic.ListView):
  context_object_name = 'images'
  paginate_by = 15

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['page_scope'] = 'Documenten van ' + self.request.user.username 
    context['page_description'] = 'Overzicht van documenten geupload door ' + self.request.user.first_name + ' ' + self.request.user.last_name + ' (' + self.request.user.username + ').'
    context['show_all'] = True
    context['date_headers'] = True
    return context

  def get_queryset(self):
    # If a username is supplied, use username as search key
    if 'username' in  self.kwargs:
      person = get_object_or_404(Person, related_user__username=self.kwargs['username'])
      user = person.related_user if person else None
    # If no username is supplied, assume current logged in user
    else:
      user = self.request.user
    return Image.objects.filter(user=user).filter(is_deleted=False).order_by('-uploaded_at')

class AddAttachmentToImageView(CreateView):
  model = 'Attachment'
