from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView 

from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.template.defaultfilters import slugify
from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages

from pathlib import Path
from math import floor

from archive.models import Image
from archive.models import Group, Tag, Attachment, Person


''' View Shared Functions '''

''' Get_additional_fields
    Used by add/create view
    Loop through possible fields and add return if field has enough options
'''
def get_additional_fields():
  fields = []
  if Tag.objects.all().count() > 0:
    fields.append('tag')
  if Group.objects.all().count() > 0:
    fields.append('in_group')
  if Attachment.objects.all().count() > 0:
    fields.append('attachments')
  if Person.objects.all().count() > 0:
    fields.append('is_portrait_of')
  return fields

''' List Views
    Default home view:
    List Images By Date Uploaded, newest first, paginated
''' 
class ImageListView(ListView):
  template_name = 'archive/images/list.html'
  context_object_name = 'images'
  paginate_by = settings.PAGINATE
  added_context = {}

  ''' get_decade 
      returns the decade start year of querystring Decade.
      For example; ?decade=1981 returns 1980.
  '''
  def get_decade(self, **kwargs):
    return floor(int(self.kwargs['decade']) / 10) * 10
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_tab'] = 'images'
    ''' Default page description '''
    context['page_description'] = 'Afbeeldingen en documenten met jou gedeeld'
    ''' If user filter is active, add user details '''
    if 'user' in self.kwargs:
      context['page_description'] = f"Afbeeldingen en documenten van { self.kwargs['user'] }"
    ''' If decade filter is active, add decade details '''
    if 'decade' in self.kwargs:
      context['page_description'] = f"Documenten in periode {str(self.get_decade())} - {str(self.get_decade() + 9)}, gesorteerd op jaartal, nieuwste eerst. <br />"  + \
                                    f"Kijk ook eens bij <a href=\"{reverse_lazy('archive:images-by-decade', args=[self.get_decade()-10])}\">{ str(self.get_decade()-10) } - { str(self.get_decade()-1) }</a> of <a href=\"{reverse_lazy('archive:images-by-decade', args=[self.get_decade()+10])}\">{ str(self.get_decade()+10) } - { str(self.get_decade()+20) }</a>"
    ''' Added context, can be placed by get_queryset() '''
    if len(self.added_context) > 0:
      for key in self.added_context:
        context[key] = self.added_context[key]
    return context
  
  ''' Showing hidden files 
      Returns True when
      1. User preference says hidden files should be shown
      2. URL argument ?hidden=true is supplied
      Returns False when URL argument ?hidden=false is supplied
    '''
  def show_hidden_files(self) -> bool:
    result = False
    if hasattr(self.request.user, 'preference'):
      if self.request.user.preference.show_hidden_files == True:
        result = True
    if self.request.GET.get('hidden'):
      if self.request.GET.get('hidden').lower() == 'true':
        result = True
      else:
        result = False
    return result

  ''' Get queryset
  '''
  def get_queryset(self):
    queryset = Image.objects.all()
    ''' Remove deleted images '''
    queryset = queryset.filter(is_deleted=False)
    ''' Show images by a single user '''
    if 'user' in self.kwargs:
      queryset = queryset.filter(user_id__username=self.kwargs['user'])
    ''' Show images with a tag '''
    if 'tag' in self.kwargs:
      queryset = queryset.filter(tag__slug=self.kwargs['tag'])
    ''' Show images in a decade '''
    if 'decade' in self.kwargs:
      queryset = queryset.filter(year__gte=self.get_decade()).filter(year__lte=self.get_decade()+9)
    ''' Show or hide hidden files '''
    if not self.show_hidden_files():
      if queryset.filter(show_in_index=False).count() > 0:
        self.added_context['images_hidden'] = queryset.filter(show_in_index=False).count()
        queryset = queryset.exclude(show_in_index=False)
      else:
        self.added_context['images_hidden'] =  False
    else:
      self.added_context['images_hidden'] = queryset.filter(show_in_index=False).count() * -1
    ''' Order images '''
    queryset = queryset.order_by('-uploaded_at')
    self.added_context['count_images'] = queryset.count()
    ''' Return result '''
    return queryset

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
    return redirect('archive:image', image.id, slugify(title) )

''' ImageView'''
class ImageView(DetailView):
  model = Image
  template_name = 'archive/images/detail.html'
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_tab'] = 'images'
    return context

''' Add Images '''
class AddImageView(PermissionRequiredMixin, CreateView):
  permission_required = 'archive.add_image'
  template_name = 'archive/images/edit.html'
  model = Image
  
  fields = ['source', 'title', 'description',
            'document_source', 'day', 'month', 'year',
            'people', 
            'show_in_index', 'is_deleted',
            'user']
  

  def __init__(self, *args, **kwargs):
    super(AddImageView, self).__init__(*args, **kwargs)
    ''' Only add additional fields if these have enough options to be useful '''
    for field in get_additional_fields():
      self.fields.append(field)
    
  ''' Build initial form '''
  def get_initial(self):
    initial = {'user': self.request.user }
    ''' Only if user has preferences stored, set field to preference '''
    if hasattr(self.request.user, 'preference'):
      initial['show_in_index'] = self.request.user.preference.show_new_uploads
    return initial

  ''' Catch form validation errors '''
  def form_invalid(self, form):
    messages.add_message(self.request, messages.WARNING, f"Formulier kan niet worden ingediend vanwege de volgende fout(en): { form.errors }")
    return super().form_invalid(form)

  def form_valid(self, form):
    ''' Force user '''
    if not hasattr(form.instance, 'user'):
      form.instance.user = self.request.user
    ''' Grab title from filename if not supplied. Omit suffix '''
    if not form.instance.title:
      form.instance.title = Path(self.request.FILES['source'].name).stem.replace('_', ' ')
    messages.add_message(self.request, messages.SUCCESS, f"Afbeelding \"{ form.instance.title }\" geupload.")
    return super().form_valid(form)

  def get_success_url(self):
    return reverse_lazy('archive:image-redirect', args=[self.object.id])

class EditImageView(PermissionRequiredMixin, UpdateView):
  permission_required = 'archive.change_image'  
  template_name = 'archive/images/edit.html'
  model = Image
  fields = ['source', 'title', 'description',
            'document_source', 'day', 'month', 'year',
            'people', 
            'show_in_index', 'is_deleted',
            'user']
  
  def __init__(self, *args, **kwargs):
    super(EditImageView, self).__init__(*args, **kwargs)
    ''' Only add additional fields if these have enough options to be useful '''
    for field in get_additional_fields():
      self.fields.append(field)

  def form_valid(self, form):
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
