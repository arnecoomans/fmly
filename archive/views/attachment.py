from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView 

from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django.template.defaultfilters import slugify
from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages

''' Required for streaming downloads to user '''
from django_sendfile import sendfile
''' Required for Attachment to Image '''
import fitz

from pathlib import Path

from archive.models import Image, Attachment

'''
    ATTACHMENTS
'''

''' Show a list of Attachment by User '''
class AttachmentListView(ListView):
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

''' Delete attachment '''
class AttachmentDeleteView(PermissionRequiredMixin, DetailView):
  model = Attachment
  permission_required = 'archive.change_attachment'

  def get(self, request, *args, **kwargs):
    object = self.get_object()
    if object.user == request.user:
      object.is_deleted = True
      object.save()
      messages.add_message(self.request, messages.SUCCESS, f"Attachment \"{ object.file } ({ object.description })\" is verwijderd en is niet meer te downloaden.")
      messages.add_message(self.request, messages.WARNING, f"Let op! Het bestand is niet verwijderd van de server. <br>Neem contact op met de beheerder als het bestand ook van de server moet worden verwijderd.")
    else:
      messages.add_message(self.request, messages.ERROR, f"Kan \"{ object.file }\" niet verwijderen. <br>Attachment kan alleen verwijderd worden door de attachment eigenaar en de site-beheerder.")
    return redirect(reverse('archive:attachments'))

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

class CreateImageFromAttachmentView(PermissionRequiredMixin, DetailView):
  model = Attachment
  permission_required = 'archive.create_image'

  def get(self, request, *args, **kwargs):
    attachment = self.get_object()
    if attachment.extension() == 'pdf':
      ''' For PDF attachment, create image of first page and create Image '''
      
      source = settings.MEDIA_ROOT.joinpath(str(attachment.file))
      destination = settings.MEDIA_ROOT.joinpath(source.stem).with_suffix('.jpg')
      ''' Check if source exists and destination does not already exist '''
      if not source.exists() or destination.exists():
        if not source.exists():
          messages.add_message(request, messages.ERROR, f"Kan geen afbeelding maken van \"{ attachment }\". Bestand wordt niet gevonden.")
        if destination.exists():
          messages.add_message(request, messages.ERROR, f"Kan geen afbeelding maken van \"{ attachment }\". Doelbestand bestaat al.")
        return redirect(reverse('archive:attachments'))
      ''' Proceed with creating image of first page '''
      
      pdf = fitz.open(source)
      page = pdf.load_page(0)
      image_source = page.get_pixmap(matrix=fitz.Matrix(4, 4))
      image_source.save(destination)
      ''' Create new Image object '''
      image = Image()
      image.source.name = destination.name
      ''' Set Image name to filename stem '''
      image.title = source.stem
      ''' Set Image user to current user '''
      image.user = request.user
      image.save()
      ''' Link originating attachment to image'''
      image.attachments.set([attachment])
      image.save()
      messages.add_message(request, messages.SUCCESS, f"Afbeelding van attachment \"{ str(source.name) }\" aangemaakt.")
      return redirect(reverse_lazy('archive:image', kwargs={'pk': image.id, 'slug': slugify(image.title)}))
    else:
      messages.add_message(request, messages.WARNING, f"Kan geen afbeelding maken van \"{ attachment }\". Bestandstype \"{ attachment.extension }\" wordt niet ondersteund.")
    pass
    return redirect(reverse('archive:attachments'))