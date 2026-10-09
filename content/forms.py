"""
Forms for editing an item's fields on its page (edit mode) - one per
block (Content.api_edit_forms; cmnsd/views/api/object_form.py). Plain
ModelForms: validation is the model's own (Content.clean included).
"""

from django import forms
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from cmnsd.forms.widgets import SuggestInput
from core.forms import StatusActionsForm

from .models import BookContent, Content, DocumentContent, PhotoContent, Transcript


class ContentNameForm(forms.ModelForm):
  class Meta:
    model = Content
    fields = ['name']
    labels = {'name': _("name")}
    widgets = {'name': forms.TextInput(attrs={'autocomplete': 'off'})}


class ContentDescriptionForm(forms.ModelForm):
  class Meta:
    model = Content
    fields = ['description']
    labels = {'description': _("description")}
    help_texts = {'description': _("What you see - Markdown: *italic*, **bold**, [link](https://...).")}
    widgets = {'description': forms.Textarea(attrs={'rows': 6})}


class ContentDateForm(forms.ModelForm):
  """The item's partial date - year, month and day each optional, and how
  sure it is. The rules (a day needs a month, no 31 February, ...) are
  the model's (PartialDateMixin.clean). Laid out as one line:
  content/forms/date.html."""
  class Meta:
    model = Content
    fields = ['date_qualifier', 'day', 'month', 'year']
    labels = {'date_qualifier': _("how sure"), 'day': _("day"), 'month': _("month"), 'year': _("year")}
    widgets = {
      'day': forms.NumberInput(attrs={'min': 1, 'max': 31, 'inputmode': 'numeric'}),
      'year': forms.NumberInput(attrs={'min': 1, 'inputmode': 'numeric'}),
    }

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    # An empty month is "unknown", not "- Select an option -".
    self.fields['month'].choices = [('', '—'), *[choice for choice in self.fields['month'].choices if choice[0] != '']]


class ContentSourceForm(forms.ModelForm):
  """Where the item came from: a person, an archive or a URL."""
  block_class = 'content-detail__field--wide'

  class Meta:
    model = Content
    fields = ['source']
    labels = {'source': _("source")}
    widgets = {'source': forms.TextInput(attrs={'autocomplete': 'off'})}


class BookPublicationForm(forms.ModelForm):
  """A book's publisher (with suggestions from other books - a recurring
  name, not a model of its own). Its authors are linked people (the
  author row); the year it was published is the item's own date (the date
  block)."""

  class Meta:
    model = BookContent
    fields = ['publisher']
    labels = {'publisher': _("publisher")}
    widgets = {
      'publisher': SuggestInput(url=reverse_lazy('cmnsd_api:object_suggest', args=['content', 'publisher'])),
    }

  @staticmethod
  def instance_for(content):
    content.ensure_detail()
    return content.book_detail


class BookIsbnForm(forms.ModelForm):
  class Meta:
    model = BookContent
    fields = ['isbn']
    labels = {'isbn': 'ISBN'}
    widgets = {'isbn': forms.TextInput(attrs={'autocomplete': 'off', 'inputmode': 'numeric'})}

  @staticmethod
  def instance_for(content):
    content.ensure_detail()
    return content.book_detail


# --- Choices: saved on click (cmnsd/edit/choices.html) -------------------

class ContentThumbnailForm(forms.ModelForm):
  """The item's own thumbnail, in a dialog (content/forms/thumbnail.html):
  the image in a 4:3 frame - the card's shape - to drag and zoom, and to
  turn a sideways scan (cmnsd.js viewer.js crop mode, as the portrait
  cropper). Applies to the cards and the small square thumbnails, not to
  the large view on the item's page. "Automatic" clears the crop: the
  center of the image again (the turn stays)."""
  dialog_title = _("Thumbnail")

  class Meta:
    model = Content
    fields = ['thumb_crop_x', 'thumb_crop_y', 'thumb_crop_w', 'thumb_crop_h', 'thumb_rotation']
    widgets = {
      'thumb_crop_x': forms.HiddenInput(attrs={'data-crop': 'x'}), 'thumb_crop_y': forms.HiddenInput(attrs={'data-crop': 'y'}),
      'thumb_crop_w': forms.HiddenInput(attrs={'data-crop': 'w'}), 'thumb_crop_h': forms.HiddenInput(attrs={'data-crop': 'h'}),
      'thumb_rotation': forms.HiddenInput(attrs={'data-crop': 'rotate'}),
    }

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['thumb_rotation'].required = False   # not sent: not turned
    if self.instance.thumb_crop_box is None:
      # No crop yet: open on the automatic one - the whole image filling the
      # frame, centred (viewer.js fills the frame with the stored box).
      self.initial.update({'thumb_crop_x': 0.0, 'thumb_crop_y': 0.0, 'thumb_crop_w': 1.0, 'thumb_crop_h': 1.0})

  def clean_thumb_rotation(self):
    return self.cleaned_data.get('thumb_rotation') or 0

  def clean(self):
    data = super().clean()
    if self.data.get(f'{self.prefix}-reset' if self.prefix else 'reset'):
      data.update({'thumb_crop_x': None, 'thumb_crop_y': None, 'thumb_crop_w': None, 'thumb_crop_h': None})
    return data


class ContentVisibilityForm(forms.ModelForm):
  choice = True

  class Meta:
    model = Content
    fields = ['visibility']
    labels = {'visibility': _("visible to")}


class ContentStatusForm(StatusActionsForm):
  """Status as actions (core.forms.StatusActionsForm): publish, back to
  draft, staff revoke - asked why, the reason kept as a comment - owners
  delete their own item."""
  confirm = {
    'x': _("Delete this item? It will be hidden from everyone - it can be recovered in the admin."),
  }
  prompt = {
    'r': _("Why is this item revoked? Only staff will see it until it's restored; your reason is kept as a comment on it."),
  }

  class Meta(StatusActionsForm.Meta):
    model = Content


class ContentKindForm(forms.ModelForm):
  """What the item is. Changing it reloads the page: the kind decides which
  other fields exist (kind of photo, of document, language, book details)
  - a detail filled in before is kept when switching back. 'unknown' isn't
  offered: it only means not decided yet."""
  choice = True
  reload_page = True

  class Meta:
    model = Content
    fields = ['kind']
    labels = {'kind': _("kind")}

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['kind'].choices = [c for c in self.fields['kind'].choices if c[0] != Content.Kind.UNKNOWN]


class PhotoKindForm(forms.ModelForm):
  """The photo details' kind (PhotoContent) - edited through the item.
  Posed or not comes first: posed for the camera is a portrait (one
  person) or a group (two or more, a couple too); not posed is candid,
  however many are in it. Historical when no family is the subject; other:
  not classified yet."""
  choice = True
  choice_hints = {
    'portrait': _("Posed, one person - head and shoulders up to full length; a passport photo too."),
    'group': _("Posed, two or more people - a couple, a family, a class, a team."),
    'candid': _("Not posed, however many people - caught in a moment: a party, a holiday, at home."),
    'historical': _("No family as the subject: the setting or the time - a street, a ship, a building."),
    'other': _("Not classified yet, or none of these."),
  }

  class Meta:
    model = PhotoContent
    fields = ['photo_kind']
    labels = {'photo_kind': _("kind of photo")}

  @staticmethod
  def instance_for(content):
    content.ensure_detail()
    return content.photo_detail


class DocumentKindForm(forms.ModelForm):
  choice = True

  class Meta:
    model = DocumentContent
    fields = ['document_kind']
    labels = {'document_kind': _("kind of document")}

  @staticmethod
  def instance_for(content):
    content.ensure_detail()
    return content.document_detail


class DocumentLanguageForm(forms.ModelForm):
  choice = True

  class Meta:
    model = DocumentContent
    fields = ['language']
    labels = {'language': _("language")}

  @staticmethod
  def instance_for(content):
    content.ensure_detail()
    return content.document_detail


# --- Child records (cmnsd object_children) ------------------------------------

class TranscriptForm(forms.ModelForm):
  """A transcript or translation of an item (Content.api_editable_children).
  The rules - one per language, one original - are the model's constraints,
  checked by cmnsd. Typed by hand: method manual; an automatic one you've
  corrected can be marked checked."""

  class Meta:
    model = Transcript
    fields = ['kind', 'language', 'method', 'incomplete', 'text']
    labels = {'kind': _("original or translation"), 'language': _("language"), 'method': _("how it was made"),
              'incomplete': _("transcription incomplete"), 'text': _("text")}
    widgets = {'text': forms.Textarea(attrs={'rows': 10})}
