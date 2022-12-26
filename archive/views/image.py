from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView 

from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django.template.defaultfilters import slugify
from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages

from django_sendfile import sendfile

from pathlib import Path
from math import floor


from archive.models import Image
from archive.models import Group, Tag, Attachment, Person


''' View Shared Functions '''

''' Get_additional_fields
    Used by add/create view
    When building a form, it makes no sense to allow to select certain fields if there are
    no selectable options, for example show an empty tag list.
    So, loop through the Objects themselves, and add the field to the form if the Object
    has items.
'''
def get_additional_fields():
  ''' Allow to skip checking each object by using the setting OBJECT_FORM_FIELDS '''
  if hasattr(settings, 'OBJECT_FORM_FIELDS') and len(settings.OBJECT_FORM_FIELDS) > 0:
    return settings.OBJECT_FORM_FIELDS
  else:
    ''' If no fields have been configured, check each related field and count the
        number of objects. If there are objects in a related field, add the related
        field to the fields list.
    '''
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
    context['active_page'] = 'images'
    ''' Default page description '''
    context['page_description'] = 'Afbeeldingen en documenten'
    ''' If user filter is active, add user details '''
    if 'user' in self.kwargs:
      context['page_description'] = f"Afbeeldingen en documenten van { self.kwargs['user'] }"
    ''' If decade filter is active, add decade details '''
    if 'decade' in self.kwargs:
      context['page_description'] = f"Documenten in periode {str(self.get_decade())} - {str(self.get_decade() + 9)}, gesorteerd op jaartal, nieuwste eerst. <br />"  + \
                                    f"Kijk ook eens bij <a href=\"{reverse_lazy('archive:images-by-decade', args=[self.get_decade()-10])}\">{ str(self.get_decade()-10) } - { str(self.get_decade()-1) }</a> of <a href=\"{reverse_lazy('archive:images-by-decade', args=[self.get_decade()+10])}\">{ str(self.get_decade()+10) } - { str(self.get_decade()+20) }</a>"
    ''' If search string is passed '''
    if self.request.GET.get('search'):
      context['page_description'] += f" met zoekwoord \"{ self.request.GET.get('search') }\""
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
    ''' Check Preferences '''
    if hasattr(self.request.user, 'preference'):
      if self.request.user.preference.show_hidden_files == True:
        result = True
    ''' Check querystring argument, overriding pereference '''
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
    ''' Image search 
        Free text search in Image title, description, filename
        Person names,
        Tag title,
        Attachment title
    '''
    if self.request.GET.get('search'):
      search_text = self.request.GET.get('search').lower()
      queryset = queryset.filter(title__icontains=search_text) | \
                 queryset.filter(description__icontains=search_text) | \
                 queryset.filter(source__icontains=search_text) | \
                 queryset.filter(people__first_name__icontains=search_text) | \
                 queryset.filter(people__given_names__icontains=search_text) | \
                 queryset.filter(people__last_name__icontains=search_text) | \
                 queryset.filter(people__married_name__icontains=search_text) | \
                 queryset.filter(tag__title__icontains=search_text) | \
                 queryset.filter(attachments__file__icontains=search_text) | \
                 queryset.filter(attachments__description__icontains=search_text)
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
    queryset = queryset.distinct().order_by('-uploaded_at')
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
    context['active_page'] = 'images'
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
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'images'
    return context

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

''' Edit Image '''
class EditImageView(PermissionRequiredMixin, UpdateView):
  permission_required = 'archive.change_image'  
  template_name = 'archive/images/edit.html'
  model = Image
  fields = ['source', 'title', 'description',
            'document_source', 'day', 'month', 'year',
            'people', 
            'show_in_index', 'is_deleted',
            'user']
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'images'
    return context
    
  def __init__(self, *args, **kwargs):
    super(EditImageView, self).__init__(*args, **kwargs)
    ''' Only add additional fields if these have enough options to be useful '''
    for field in get_additional_fields():
      self.fields.append(field)

  def form_valid(self, form):
    ''' Only allow user change by superuser '''
    if not self.request.user.is_superuser and 'user' in form.changed_data: 
      ''' User change is initiated by non_superuser. 
          Fetch user from stored object and retain'''
      original = Image.objects.get(pk=self.kwargs['pk'])
      form.instance.user = original.user
      messages.add_message(self.request, messages.WARNING, f"Gebruiker kan niet worden gewijzigd! { original.user } blijft gebruiker.")
    elif not form.instance.user:
      ''' If for some reason no user it set, set user to current user '''
      form.instance.user = self.request.user
    if len(form.changed_data) > 0:
      ''' Only if data has changed, save the Object '''
      messages.add_message(self.request, messages.SUCCESS, f"Wijzigingen opgeslagen.")
      return super().form_valid(form)
    else:
      ''' No changes are detected, redirect to image without saving. '''
      messages.add_message(self.request, messages.WARNING, f"Geen wijzigingen opgegeven.")
      return redirect(reverse_lazy('archive:image', args=[form.instance.id, slugify(form.instance.title)]))

  def get_success_url(self):
    return reverse_lazy('archive:image', args=[self.object.id, slugify(self.object.title)])

'''
    ATTACHMENTS
'''

''' Show a list of Attachment by User '''
class AttachmentListView(PermissionRequiredMixin, ListView):
  model = Attachment
  permission_required = 'archive.view_attachment'
  permission_denied_message = 'Geen rechten toegekend om Attachments te bekijken'
  template_name = 'archive/attachments/list.html'

  def get_queryset(self):
    queryset = Attachment.objects.all().filter(is_deleted=False).order_by('user', 'description')
    ''' Allow to filter attachments per user '''
    if 'user' in self.kwargs:
      queryset = queryset.filter(user__username__iexact=self.kwargs['user'])
    return queryset

''' AddAttachment '''
class AttachmentAddView(PermissionRequiredMixin, CreateView):
  model = Attachment
  permission_required = 'archive.create_attachment'
  template_name = 'archive/attachments/edit.html'
  fields = ['file', 'description', ]

  def form_invalid(self, form):
    messages.add_message(self.request, messages.WARNING, f"Formulier kan niet worden ingediend vanwege de volgende fout(en): { form.errors }")
    return super().form_invalid(form)

  def form_valid(self, form):
    form.instance.user = self.request.user
    form.instance.slug = slugify(str(form.instance.file))
    if not form.instance.description:
      form.instance.description = str(form.instance.file)
    return super().form_valid(form)
  
  def get_success_url(self):
    return reverse('archive:attachments') + '?mark=' + self.object.slug

''' Stream Attachment to User as download, but only if user is authenticated.
    This aviods files being downloaded by non-users.
    Requires django-sendfile2, add sendfile-settings in settings.py and support of
    sendfile in nginx.
    https://pypi.org/project/django-sendfile2/
    See /documentation for more information
'''
class AttachmentStreamView(PermissionRequiredMixin, DetailView):
  model = Attachment
  permission_required = 'archive.view_attachment'

  def get(self, request, *arg, **kwargs):
    ''' Only allow for not-deleted files'''
    file = self.get_object()
    ''' Prepare filename '''
    filename = Path(str(file.file))
    if len(filename.stem) > 24:
      filename = f"{filename.stem[:22]}..{filename.suffix}"
    ''' Sanity Checks '''
    if file.is_deleted:
      ''' If file is marked as deleted, show an error message '''
      ''' Send message that file is not available '''
      messages.add_message(self.request, messages.WARNING, f"Bestand \"{ filename }\"is niet meer beschikbaar.")
      ''' Return to Attachment List '''
      return redirect(reverse('archive:attachments'))
    elif not settings.MEDIA_ROOT.joinpath(str(file.file)).exists():
      ''' Check if file exists on filesystem '''
      ''' Send message that file is not available '''
      messages.add_message(self.request, messages.ERROR, f"Bestand \"{ filename }\"is niet beschikbaar.")
      ''' Return to Attachment List '''
      return redirect(reverse('archive:attachments'))
    ''' Allow download of file by user '''
    file = Path(settings.MEDIA_ROOT).joinpath(str(file.file))
    return sendfile(request, file)

  
  
  