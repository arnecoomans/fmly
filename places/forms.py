"""
Forms for editing a place on its page (edit mode) - one per block
(Place.api_edit_forms; cmnsd/views/api/object_form.py). Plain ModelForms:
validation is the model's own (Place.clean: no loops in the parents).
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from cmnsd.forms.widgets import PickerInput

from .models import Place
from .places import descendant_tokens


class PlaceNameForm(forms.ModelForm):
  class Meta:
    model = Place
    fields = ['name']
    labels = {'name': _("name")}
    widgets = {'name': forms.TextInput(attrs={'autocomplete': 'off'})}


class PlaceAliasForm(forms.ModelForm):
  class Meta:
    model = Place
    fields = ['alias']
    labels = {'alias': _("also written as")}
    help_texts = {'alias': _("Another spelling or language for the same place in the same time - e.g. Indonesië / Indonesia. A name from another era is a place of its own: add it under “in another era”.")}
    widgets = {'alias': forms.TextInput(attrs={'autocomplete': 'off'})}


class PlaceDescriptionForm(forms.ModelForm):
  class Meta:
    model = Place
    fields = ['description']
    labels = {'description': _("description")}
    widgets = {'description': forms.Textarea(attrs={'rows': 5})}


class PlaceParentForm(forms.ModelForm):
  """The place this one lies in - chosen by searching (a picker, saved on
  choice), or none. The place itself and the places within it aren't
  offered; Place.clean refuses them anyway."""
  parent = forms.ModelChoiceField(
    Place.objects.select_related('parent'), to_field_name='token', required=False, label=_("lies in"),
    widget=PickerInput(
      'place', label=lambda place: ' › '.join(ancestor.name for ancestor in place.ancestors()),
      placeholder=_("search a place"), empty_label=_("nowhere - a country or region of its own"), clear_label=_("remove"),
    ),
  )

  class Meta:
    model = Place
    fields = ['parent']

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    # The field holds tokens; a ModelForm's initial value is the parent's pk.
    if self.instance.parent_id:
      self.initial['parent'] = self.instance.parent.token
    if self.instance.pk:
      self.fields['parent'].widget.exclude = [self.instance.token, *descendant_tokens(self.instance)]

