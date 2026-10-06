"""
Forms for editing a note on its page (edit mode) - one per block
(Note.api_edit_forms; cmnsd/views/api/object_form.py). Plain ModelForms:
validation is the model's own (PartialDateMixin.clean for the date).
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from core.forms import StatusActionsForm

from .models import Note


class NoteTitleForm(forms.ModelForm):
  class Meta:
    model = Note
    fields = ['title']
    labels = {'title': _("title")}
    help_texts = {'title': _("Optional - without one, the first line of the text names the note.")}
    widgets = {'title': forms.TextInput(attrs={'autocomplete': 'off'})}


class NoteBodyForm(forms.ModelForm):
  class Meta:
    model = Note
    fields = ['body']
    labels = {'body': _("text")}
    help_texts = {'body': _("Markdown: *italic*, **bold**, [link](https://...), # heading, - list.")}
    widgets = {'body': forms.Textarea(attrs={'rows': 14})}


class NoteDateForm(forms.ModelForm):
  """When it's about - year, month and day each optional, and how sure
  (PartialDateMixin, the same as an item's date). One line:
  note/forms/date.html."""
  class Meta:
    model = Note
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


# --- Choices: saved on click (cmnsd/edit/choices.html) -------------------

class NoteKindForm(forms.ModelForm):
  """What the note is - a question becomes a hypothesis, then a
  conclusion: the same note, another kind (the change is in its history)."""
  choice = True

  class Meta:
    model = Note
    fields = ['kind']
    labels = {'kind': _("kind")}


class NoteConfidenceForm(forms.ModelForm):
  """How sure the claim is - for a hypothesis or conclusion. Empty: not
  said."""
  choice = True

  class Meta:
    model = Note
    fields = ['confidence']
    labels = {'confidence': _("confidence")}

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['confidence'].choices = [('', _("not said")), *[c for c in self.fields['confidence'].choices if c[0] != '']]


class NoteVisibilityForm(forms.ModelForm):
  choice = True

  class Meta:
    model = Note
    fields = ['visibility']
    labels = {'visibility': _("visible to")}


class NoteStatusForm(StatusActionsForm):
  """Status as actions (core.forms.StatusActionsForm): a note starts as a
  draft; publish it to let others see it (with its visibility)."""
  confirm = {
    'x': _("Delete this note? It will be hidden from everyone - it can be recovered in the admin."),
    'r': _("Revoke this note? Only staff will see it until it's restored."),
  }

  class Meta(StatusActionsForm.Meta):
    model = Note
