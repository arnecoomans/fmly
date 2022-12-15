from django.views import generic
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormView

from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.template.defaultfilters import slugify
from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages

from pathlib import Path
from math import floor

from archive.models import Image, Person


''' List Views
    Default home view:
    List Images By Date Uploaded, newest first, paginated
''' 
class ImageListView(generic.ListView):
  template_name = 'archive/images/list.html'
  context_object_name = 'images'
  paginate_by = settings.PAGINATE

  def get_decade(self, **kwargs):
    return floor(int(self.kwargs['decade']) / 10) * 10
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_tab'] = 'images'
    context['page_description'] = 'Afbeeldingen en documenten met jou gedeeld'
    if 'decade' in self.kwargs:
      context['page_description'] = f"Documenten in periode {str(self.get_decade())} - {str(self.get_decade() + 9)}, gesorteerd op jaartal, nieuwste eerst. <br />"  + \
                                    f"Kijk ook eens bij <a href=\"{reverse_lazy('archive:images-by-decade', args=[self.get_decade()-10])}\">{ str(self.get_decade()-10) } - { str(self.get_decade()-1) }</a> of <a href=\"{reverse_lazy('archive:images-by-decade', args=[self.get_decade()+10])}\">{ str(self.get_decade()+10) } - { str(self.get_decade()+20) }</a>"
    return context
  
  def get_queryset(self):
    queryset = Image.objects.all()
    queryset = queryset.filter(is_deleted=False)
    if 'user' in self.kwargs:
      queryset = queryset.filter(user_id__username=self.kwargs['user'])
    if 'tag' in self.kwargs:
      queryset = queryset.filter(tag__slug=self.kwargs['tag'])
    if 'decade' in self.kwargs:
      queryset = queryset.filter(year__gte=self.get_decade()).filter(year__lte=self.get_decade()+9)
    if hasattr(self.request.user, 'preference') and self.request.user.preference.show_hidden_files == True:
      queryset.exclude(show_in_index=False)
    else:
      if 'user' not in self.kwargs:
        queryset = queryset.filter(show_in_index=True)
    queryset = queryset.order_by('-uploaded_at')
    return queryset

# class ImageSearchView(generic.ListView):
#   template_name = 'archive/images/list.html'
#   context_object_name = ' images'
#   paginate_by = settings.PAGINATE

''' Redirect views
    Redirect id-only link to link with title included
'''
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

# Renamed DocumentView to ImageView
class ImageView(generic.DetailView):
  model = Image
  template_name = 'archive/images/detail.html'


## Add Image / Images
# Renamed AddImage to AddImageView
class AddImageView(PermissionRequiredMixin, CreateView):
  permission_required = 'archive.add_image'
  template_name = 'archive/images/edit.html'
  model = Image
  
  fields = ['source', 'title', 'description',
            'document_source', 'day', 'month', 'year',
            'people', 'tag',
            'in_group',
            'attachments',
            'is_portrait_of',
            'show_in_index', 'is_deleted',
            'user']
  
  def get_initial(self):
    return {'user': self.request.user }

  def form_invalid(self, form):
    messages.add_message(self.request, messages.WARNING, f"Formulier kan niet worden ingediend vanwege de volgende fout(en): { form.errors }")
    return super().form_invalid(form)

  def form_valid(self, form):
    if not hasattr(form.instance, 'user'):
      form.instance.user = self.request.user
    if hasattr(self.request.user, 'preference') and self.request.user.preference.upload_is_hidden == False:
      form.instance.show_in_index = True
    if not form.instance.title:
      form.instance.title = Path(self.request.FILES['source'].name).stem.replace('_', ' ')
    messages.add_message(self.request, messages.SUCCESS, f"Afbeelding \"{ form.instance.title }\" geupload.")
    return super().form_valid(form)

  def get_success_url(self):
    return reverse_lazy('archive:image-redirect', args=[self.object.id])

# # Renamed AddImages to AddImagesView
# class AddImagesView(PermissionRequiredMixin, CreateView):
#   permission_required = 'archive.create_document'
#   model = Image
#   fields = ['source']
#   success_url = reverse_lazy('archive:my-images')
#   template_name = 'images/image_multi_upload.html'
  
#   def form_valid(self, form):
#     form.instance.user = self.request.user
#     form.instance.title = self.request.FILES['source'].name
#     form.instance.show_in_index = False
#     return super().form_valid(form)

class EditImageView(PermissionRequiredMixin, UpdateView):
  permission_required = 'archive.change_image'  
  template_name = 'archive/images/edit.html'
  model = Image
  fields = ['source', 'title', 'description',
            'document_source', 'day', 'month', 'year',
            'people', 'tag',
            'in_group',
            'attachments',
            'is_portrait_of',
            'show_in_index', 'is_deleted',
            'user']

  def form_valid(self, form):
    #if not self.request.user.is_superuser and form.isinstance.user.is_changed():
    #if hasattr(form.changed_data, 'user'):
    if not self.request.user.is_superuser and 'user' in form.changed_data: 
      original = Image.objects.get(pk=self.kwargs['pk'])
      form.instance.user = original.user
      messages.add_message(self.request, messages.WARNING, f"Gebruiker kan niet worden gewijzigd! { original.user } blijft gebruiker.")
    if not form.instance.user:
      form.instance.user = self.request.user
    if len(form.changed_data) > 0:
      messages.add_message(self.request, messages.SUCCESS, f"Wijzigingen opgeslagen.")
      return super().form_valid(form)
    else:
      messages.add_message(self.request, messages.WARNING, f"Geen wijzigingen opgegeven.")
      return redirect(reverse_lazy('archive:image', args=[form.instance.id, slugify(form.instance.title)]))

  def get_success_url(self):
    return reverse_lazy('archive:image-redirect', args=[self.object.id])

## Special views

# # Renamed DocumentPreviewListView to RecentImageListPreView
# class RecentImageListPreView(generic.ListView):
#   # Returns a single page of documents without login.
#   context_object_name = 'images'
#   paginate_by = settings.PAGINATE

#   def get_context_data(self, **kwargs):
#     context = super().get_context_data(**kwargs)
#     context['page_scope'] = 'voorbeelddocumenten'
#     context['page_description'] = 'In dit overzicht zie je een voorbeeld hoe documenten worden weergegeven. Wil je meer zien of details bekijken? Neem contact op.'
#     context['preview'] = True
#     return context
#   def get_queryset(self):
#     return Image.objects.filter(is_deleted=False).filter(show_in_index=True).order_by('-uploaded_at')[:12]


# # Renamed DocumentYearView to ImageYearRedirectView
# class ImageYearRedirectView(generic.DetailView):
#   model = Image
#   context_object_name = 'images'
#   def get(self, request, *args, **kwargs):
#     decade = floor(int(self.kwargs['year']) / 10) * 10
#     return redirect('archive:images-by-decade', decade)




# # Renamed MyDocumentList to ImageListByUserView
# class ImageListByUserView(generic.ListView):
#   context_object_name = 'images'
#   paginate_by = settings.PAGINATE

#   def get_context_data(self, **kwargs):
#     context = super().get_context_data(**kwargs)
#     context['page_scope'] = 'Documenten van ' + self.request.user.username 
#     context['page_description'] = 'Overzicht van documenten geupload door ' + self.request.user.first_name + ' ' + self.request.user.last_name + ' (' + self.request.user.username + ').'
#     context['show_all'] = True
#     context['date_headers'] = True
#     return context

#   def get_queryset(self):
#     # If a username is supplied, use username as search key
#     if 'username' in  self.kwargs:
#       person = get_object_or_404(Person, related_user__username=self.kwargs['username'])
#       user = person.related_user if person else None
#     # If no username is supplied, assume current logged in user
#     else:
#       user = self.request.user
#     return Image.objects.filter(user=user).filter(is_deleted=False).order_by('-uploaded_at')

# class AddAttachmentToImageView(CreateView):
#   model = 'Attachment'
