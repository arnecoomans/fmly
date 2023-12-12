from django.views.generic.edit import CreateView, UpdateView
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.template.defaultfilters import slugify
from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages
from django.utils.translation import gettext as _

from pathlib import Path
from datetime import datetime
from PIL import Image as PIL
from pillow_heif import register_heif_opener

from archive.models import Image
from archive.models import Group, Tag, Attachment, Person

''' EditImageMasterClass
    Some functionality is shared over the edit and add image view.
    This class holds the shared functionality.
'''
class EditImageMaster:
  model = Image
  template_name = 'archive/images/edit.html'

  def get_form(self):
    ''' Add User field for staff '''
    if self.request.user.is_staff == True:
      self.fields.append('user')
    form = super(EditImageMaster, self).get_form()
    return form
 
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'images'
    context['portrait'] = self.object.is_portrait_of
    context['available_portraits'] = self.object.people.all().filter(portrait=None, private=False)
    return context
  
  ''' Catch form validation errors '''
  def form_invalid(self, form):
    messages.add_message(self.request, messages.WARNING,
                         f"{ _('Form cannot be saved because of the following error(s)') }: { form.errors }")
    return super().form_invalid(form)
  
  def form_valid(self, form):
    ''' Force user '''
    if not hasattr(form.instance, 'user'):
      form.instance.user = self.request.user
    elif 'user' in form.changed_data and not self.request.user.is_superuser:
      form.instance.user = self.get_object().user
      messages.add_message(self.request, messages.WARNING,
                           f"{ _('cannot change user for this object') }.")
    ''' Grab title from filename if not supplied. Omit suffix '''
    if not form.instance.title:
      if self.get_object():
        form.instance.title = Path(
            self.get_object().source).stem.replace('_', ' ')
    ''' Grab slug from title '''
    if not hasattr(form.instance, 'slug') or form.instance.slug:
      form.instance.slug = slugify(form.cleaned_data['title'])
    ''' Check if an upload should be processed '''
    if 'source' in form.changed_data:
      form.instance.source = str(form.instance.source)
      form.instance.thumbnail = str(form.instance.thumbnail)
      form_data = {}
      for field in form.changed_data:
        form_data[field] = getattr(form.instance, field)
      image = Image.objects.update_or_create(slug=form.instance.slug,
                                             defaults=form_data)
      messages.add_message(self.request, messages.SUCCESS,
                            f"{ _('successfully uploaded image ') } { form.instance.source }.")
      return redirect('archive:image', form.instance.slug)
    
    ''' If changes are detected, store changes '''
    if len(form.changed_data) > 0:
      messages.add_message(self.request, messages.SUCCESS,
                           f"{ _('successfully updated the following fields') }: { ', '.join(form.changed_data).replace('_', ' ') }.")
    return super().form_valid(form)
  

  ''' Store Source
      Take Source Image and Process it according to the requirements
  '''
  def store_source(self, source):

    ''' Get Uploaded File Info '''
    original_filename = Path(str(source))
    ''' Check extention of file if it can be processed and set the new filename '''
    if original_filename.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.heic']:
      ''' New filename format is YYYY-MM-DD-[original filename].[orignial suffix] '''
      target_filename = Path(datetime.now().strftime(
          "%Y-%m-%d-") + str(original_filename))
    else:
      ''' If the file is of unsupported extention, stop processing '''
      messages.add_message(self.request, messages.INFO,
                           "Unsupported File Type")
      return redirect('archive:add-image')
    ''' Check if .heic-conversion should be done '''
    heic = False
    if original_filename.suffix.lower() == '.heic':
      ''' If a .heic is detected, load heif-opener and add format to target file '''
      register_heif_opener()
      heic = True
      target_filename = target_filename.with_suffix('.jpg')
      messages.add_message(self.request, messages.INFO,
                           f"{ _('detected .heic-image, converting to jpeg') }.")
    ''' Do Sanity Check
        - Target Image should not exist
        - if it does exist, add a number behind the image name
    '''
    if settings.MEDIA_ROOT.joinpath(target_filename).exists():
      messages.add_message(self.request, messages.WARNING,
                           f"{ _('file already exists, selecting a different filename') }.")
      i = 1
      while settings.MEDIA_ROOT.joinpath(target_filename).with_name(f"{ target_filename.stem }-{ str(i) }") .exists():
        i += 1
      target_filename = target_filename.with_name(
          f"{ target_filename.stem }-{ str(i) }").with_suffix(target_filename.suffix)
    ''' Store Image to Filesystem '''
    original_image = self.request.FILES['source']
    with PIL.open(original_image) as image:
      if heic:
        image = image.save(settings.MEDIA_ROOT / target_filename,
                           format="JPEG")
      else:
        image = image.save(settings.MEDIA_ROOT / target_filename)
    return target_filename
  

class EditImageView(EditImageMaster, UpdateView):
  fields = ['source', 'title', 'description',
            'document_source', 'day', 'month', 'year',
            'people',
            'visibility_frontpage', 'visibility_person_page', 'is_deleted',
            'tag', 'in_group', 'attachments', 'is_portrait_of',]

  def get_failure_url(self):
    return reverse_lazy('archive:image-edit', kwargs={'pk': self.get_object().id})
  def get_success_url(self):
    return reverse_lazy('archive:image', kwargs={'slug': self.get_object().slug})

class AddImageView(EditImageMaster, CreateView):
  fields = ['source', 'title', 'description',
            'document_source', 'day', 'month', 'year',
            'people',
            'visibility_frontpage', 'visibility_person_page', 'is_deleted',
            'tag', 'in_group', 'attachments', 'is_portrait_of',]

  def form_valid(self, form):
    ''' Store Image '''
    ''' Check if there is an uploaded file '''
    if len(self.request.FILES) != 1:
      messages.add_message(self.request, messages.INFO,
                           f"{ _('the form cannot be processed: too little or too many files selected') }.")
      return redirect('archive:add-image')
    ''' Store Source and fetch new source filename '''
    form.instance.source = self.store_source(source=self.request.FILES['source'])
    # ''' Store Thumbnail '''
    # form.instance.thumbnail = self.store_thumbnail(form.instance.source)
    ''' Proceed with Operation '''
    return super().form_valid(form)
  
  def get_failure_url(self):
    return reverse_lazy('archive:add-image')
  def get_success_url(self):
    return reverse_lazy('archive:image', kwargs={'slug': self.object.slug})