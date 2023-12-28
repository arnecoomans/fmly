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
from html import escape

from archive.models import Image
from archive.models import Group, Tag, Attachment, Person

''' EditImageMasterClass
    Holds functionality used both by add and edit image views:
    - Build form fields, add "user" for staff
    - Fill context data with special Image fields
    - 
'''
class EditImageMaster:
  model = Image
  template_name = 'archive/images/edit.html'
  fields = ['source', 'title', 'description',
            'document_source', 'day', 'month', 'year',
            'people', 'family',
            'visibility_frontpage', 'visibility_person_page', 'is_deleted',
            'tag', 'in_group', 'attachments', 'is_portrait_of',]

  ''' Get Form
      Add User field when staff
  '''
  def get_form(self):
    ''' Add User field for staff '''
    if self.request.user.is_staff == True:
      self.fields.append('user')
    form = super(EditImageMaster, self).get_form()
    return form
 
  ''' Fill Context Data'''
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'images'
    ''' If an image is updated, it has a self.object,
        in that case add information to the view
    '''
    if self.object:
      ''' Store who this image is a portrait of '''
      context['portrait'] = self.object.is_portrait_of
      ''' Store who this image can be a portrait of '''
      context['available_portraits'] = self.object.people.all().filter(portrait=None, private=False)
      ''' Family Collections '''
      context['active_family_collections_tag'] = self.get_active_family_collections_tag()
    context['available_family_collections'] = self.get_available_family_collections()
    return context
  
  ''' Family Collections '''
  ''' Get Family Collection by Tagged people 
      Returns a list of family collections this person is a member of, via tagged
      people. This is mentioned in the edit view, since maintaining memberships of the
      collection is managed by managing tagged people.
  '''
  def get_active_family_collections_tag(self):
    result = []
    if self.object:
      ''' Loop through tagged people '''
      for person in self.object.people.all():
        ''' If tagged-persons last name or married name is of a configured family '''
        if person.last_name in settings.FAMILIES or person.married_name in settings.FAMILIES:
          ''' Fetch the matching family name '''
          family = person.last_name if person.last_name in settings.FAMILIES else person.married_name
          if family not in result:
            result.append(family)
    return result
  
  ''' Return family collections this image is not yet a member of '''
  def get_available_family_collections(self):
    result = []
    for family in settings.FAMILIES:
      if family not in self.get_active_family_collections_tag():
        result.append(family)
    return result


  ''' Processing
      Use post() to handle change and upload processing manually. This allows better
      support for converting unsupported formats (.heic) to jpeg, and have control
      over the naming, storage and thumbnail process.
      Post is called when the form is submitted
  '''
  def post(self, *args, **kwargs):
    ''' Set Object'''
    if 'slug' in self.kwargs or 'pk' in self.kwargs:
      object = self.get_object()
    else:
      object = None
    ''' Process required fields '''
    form = {}
    form['slug'] = object.slug if object else None
    form['source'] = object.source if object else None
    form['thumbnail'] = object.thumbnail if object else None
    form['title'] = self.request.POST.get('title', None)
    form['description'] = self.request.POST.get('description', '')
    form['document_source'] = self.request.POST.get('document_source', '')
    form['day'] = None if self.request.POST.get('day', None) == '' else self.request.POST.get('day', None)
    form['month'] = None if self.request.POST.get('month', None) == '' else self.request.POST.get('month', None)
    form['year'] = None if self.request.POST.get('year', None) == '' else self.request.POST.get('year', None)
    form['family'] = self.request.POST.get('family', None)
    form['visibility_frontpage'] = True if self.request.POST.get('visibility_frontpage', '') == 'true' else False
    form['visibility_person_page'] = True if self.request.POST.get('visibility_person_page', '') == 'true' else False
    form['is_deleted'] = True if self.request.POST.get('is_deleted', '') == 'true' else False
    ''' Relation holding fields, can have multiple values '''
    form['people'] = self.request.POST.getlist('people', None)
    form['tag'] = self.request.POST.getlist('tag', None)
    form['in_group'] = self.request.POST.getlist('in_group', None)
    form['attachments'] = self.request.POST.getlist('attachments', None)
    form['is_portrait_of'] = self.request.POST.getlist('is_portrait_of', None)
    ''' Handle Uploads '''
    if 'source'in self.request.FILES:
      ''' Only process the first file '''
      form['source'] = self.store_image(self.request.FILES['source'], self.get_upload_filename(self.request.FILES['source']))
    elif object:
      ''' If this is edit view, check for special tasks '''
      ''' Store Source from image '''
      form['source'] = object.source
    else:
      ''' If no source is known, and no source is supplied, return an error '''
      messages.add_message(self.request, messages.ERROR, f"{ _('no uploaded file detected, please select a file to upload') }. { escape(str(object)) }")
      return redirect(self.get_failure_url())
    ''' Form Field Validation: Required fields: Title
        If no title is supplied, take the original filename and remove the suffix 
        Uses self.request.FILES to get the original filename
        Replaces _ by space and removes everything after the last dot (assumed suffix)
    '''
    if not form['title'] or len(form['title']) == 0:
        source = str(self.request.FILES['source']) if 'source' in form else object.source
        form['title'] = str(source).replace('_', ' ')[:str(source).rfind('.')]
    ''' Enforce Slug '''
    if not 'slug' in form or not form['slug'] or len(form['slug']) == 0:
      form['slug'] = slugify(str(form['title']))
    ''' Enforce Thumbnail '''
    if 'thumbnail' not in form or not form['thumbnail'] or len(form['thumbnail']) == 0:
      form['thumbnail'] = self.store_thumbnail(Path(str(form['source'])))
    ''' Enforce User '''
    if 'user' not in form or not form['user'] or len(form['user']) == 0:
      form['user'] = self.request.user
    ''' Store object to database 
        Use single_value_fields to store initial object
    '''
    defaults = {
      'source': str(form['source']),
      'thumbnail': str(form['thumbnail']),
      'title': form['title'],
      'description': form['description'],
      'document_source': form['document_source'],
      'day': form['day'],
      'month': form['month'],
      'year': form['year'],
      'family': form['family'],
      'visibility_frontpage': form['visibility_frontpage'],
      'visibility_person_page': form['visibility_person_page'],
      'is_deleted': form['is_deleted'],
      'user': form['user'],
    }
    image = Image.objects.update_or_create(slug=form['slug'],
                                           defaults=defaults)
    action = 'stored' if image[1] else 'updated'
    image = image[0]
    ''' Process additional fields that require an object to be saved first '''
    image.people.set(form['people'])
    image.tag.set(form['tag'])
    image.in_group.set(form['in_group'])
    image.attachments.set(form['attachments'])
    image.is_portrait_of__id = form['is_portrait_of']
    image.height, image.width = image.get_image_dimensions()
    image.storeSize()
    image.save()
    self.image = image
    messages.add_message(self.request, messages.SUCCESS, f"{ _('sucessfully ' + action + ' information of') } { form['title'] }.")
    ''' Processing succesful; Redirect to success page '''
    # messages.add_message(self.request, messages.INFO, escape(str(form)))
    return redirect(self.get_success_url())


  def get_upload_filename(self, uploaded_file):
    message = []
    ''' Get Uploaded File Info '''
    uploaded_filename = Path(str(uploaded_file))
    ''' Check extention of file if it can be processed and set the new filename '''
    if uploaded_filename.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.heic']:
      ''' New filename format is YYYY-MM-DD-[original filename].[orignial suffix] '''
      target_filename = Path(datetime.now().strftime(
          "%Y-%m-%d-") + str(uploaded_filename))
    else:
      ''' If the file is of unsupported extention, stop processing '''
      messages.add_message(self.request, messages.INFO,
                           f"{ _('unsupported file type') }: { uploaded_filename.suffix }")
      return redirect('archive:add-image')
    ''' Check if .heic-conversion should be done '''
    heic = False
    if uploaded_filename.suffix.lower() == '.heic':
      ''' If a .heic is detected, load heif-opener and add format to target file '''
      register_heif_opener()
      heic = True
      target_filename = target_filename.with_suffix('.jpg')
      message.append(f"{ _('detected .heic-image, converting to jpeg') }.")
    ''' Do Sanity Check
        - Target Image should not exist
        - if it does exist, add a number behind the image name
    '''
    if settings.MEDIA_ROOT.joinpath(target_filename).exists():
      message.append(f"{ _('file already exists, selecting a different filename') }.")
      i = 1
      while settings.MEDIA_ROOT.joinpath(target_filename).with_name(f"{ target_filename.stem }-{ str(i) }").with_suffix(target_filename.suffix).exists():
        i += 1
      target_filename = target_filename.with_name(
          f"{ target_filename.stem }-{ str(i) }").with_suffix(target_filename.suffix)
      messages.add_message(self.request, messages.INFO, '<br>'.join(message))
    return {'filename': target_filename, 'heic': heic}
  
  def store_image(self, uploaded_file, target):
    target_filename = target['filename']
    heic = target['heic']
    ''' Store Image to Filesystem '''
    PIL.MAX_IMAGE_PIXELS = 500000000
    with PIL.open(uploaded_file) as image:
      if heic:
        image = image.save(settings.MEDIA_ROOT / target_filename,
                           format="JPEG")
      else:
        image = image.save(settings.MEDIA_ROOT / target_filename)
    messages.add_message(self.request, messages.SUCCESS,
                         f"{ _('sucesfully stored') } { target_filename }.")
    return target_filename
  
  def store_thumbnail(self, stored_file):
    PIL.MAX_IMAGE_PIXELS = 500000000
    ''' Store Source Information '''
    src_file = settings.MEDIA_ROOT.joinpath(stored_file)
    ''' Store Target Information '''
    tgt_width = 300
    tgt_path = settings.MEDIA_ROOT.joinpath('thumbnails/')
    tgt_file = str(stored_file.name)
    ''' Check if thumbnails_dir exists '''
    if not tgt_path.exists():
      tgt_path.mkdir(parents=True, exist_ok=True)
    ''' Set destination '''
    try:
      with PIL.open(src_file) as img:
        width, height = img.size
        ratio = width / height
        tgt_height = int(tgt_width / ratio)
        img = img.resize((tgt_width, tgt_height), PIL.Resampling.LANCZOS)
        img.save(settings.MEDIA_ROOT.joinpath(tgt_path).joinpath(tgt_file))
        messages.add_message(self.request, messages.SUCCESS,
                             f"{ _('stored thumbnail of image to') }: { str(Path('thumbnails').joinpath(tgt_file)) }")
        return Path('thumbnails').joinpath(tgt_file)
    except Exception as e:
      messages.add_message(self.request, messages.ERROR, f"error when generating thumbnail: { e }")
      return None

class EditImageView(EditImageMaster, UpdateView):
  def get_failure_url(self):
    return reverse_lazy('archive:image-edit', kwargs={'pk': self.get_object().id})
  def get_success_url(self):
    return reverse_lazy('archive:image', kwargs={'slug': self.get_object().slug})

class AddImageView(EditImageMaster, CreateView):
  def get_failure_url(self):
    return reverse_lazy('archive:add-image')
  def get_success_url(self):
    return reverse_lazy('archive:image', kwargs={'slug': self.image.slug})