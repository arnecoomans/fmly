"""
Edit-mode forms shared by fmly's models (cmnsd object_form blocks).
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from cmnsd.forms.widgets import PickerInput

from .models import Tag


class TagNameForm(forms.ModelForm):
  """A tag's name (Tag.api_edit_forms) - the slug follows (Tag.save). The
  model's own rules: unique among its siblings."""

  class Meta:
    model = Tag
    fields = ['name']
    labels = {'name': _("name")}
    widgets = {'name': forms.TextInput(attrs={'autocomplete': 'off'})}

  def clean_name(self):
    """Unique among its siblings - the model's constraint, checked here as a
    form error: Django leaves out a constraint involving a field the form
    doesn't have (parent), and the model would refuse at save instead."""
    name = self.cleaned_data['name']
    siblings = Tag.objects.filter(parent=self.instance.parent).exclude(pk=self.instance.pk)
    if siblings.filter(name__iexact=name).exists():
      raise forms.ValidationError(_("There's already a tag with this name here."))
    return name


class TagParentForm(forms.ModelForm):
  """The tag this one sits under - chosen by searching (a picker, saved on
  choice), or none: a tag of its own. Not offered: the tag itself and the
  tags below it (HierarchyMixin.clean refuses a loop anyway). The name must
  be free under the new parent; the "Loose end" tag stays on top - it's
  found there (core.tags.loose_end_tag).

  "+ new tag": a name typed without a match makes a new parent on save -
  published, with the visibility of the tag it's made for (a family-only
  tag gets a family-only parent) - for someone with core.add_tag. An existing tag
  of that name is used instead; "Media: Books" makes Books under Media
  (HierarchyMixin), reusing what exists of that path."""
  parent = forms.ModelChoiceField(
    Tag.objects.none(), to_field_name='token', required=False, label=_("under"),
    widget=PickerInput(
      'tag', label=lambda tag: str(tag), placeholder=_("search a tag"),
      empty_label=_("nothing - a tag of its own"), clear_label=_("remove"), create_label=_("+ new tag"),
    ),
  )

  class Meta:
    model = Tag
    fields = ['parent']

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    # The field holds tokens; a ModelForm's initial value is the parent's pk.
    if self.instance.parent_id:
      self.initial['parent'] = self.instance.parent.token

  def prepare(self):
    """Only tags this user may see; not the tag itself or those below it."""
    from cmnsd.models.access import filter_accessible
    from .tags import descendant_tokens
    self.fields['parent'].queryset = filter_accessible(Tag.objects.select_related('parent'), self.request)
    if self.instance.pk:
      self.fields['parent'].widget.exclude = [self.instance.token, *descendant_tokens(self.instance)]

  def clean_parent(self):
    from .tags import LOOSE_END_SLUG
    self.new_parent_name = ''
    parent = self.cleaned_data['parent'] or self._typed_parent()
    if parent is None and self.new_parent_name:
      if self.instance.slug == LOOSE_END_SLUG and self.instance.parent_id is None:
        raise forms.ValidationError(_("The Loose end tag stays a tag of its own."))
      return None   # made in save(); new, so no name below it is taken yet
    if parent is not None and self.instance.slug == LOOSE_END_SLUG and self.instance.parent_id is None:
      raise forms.ValidationError(_("The Loose end tag stays a tag of its own."))
    others = Tag.objects.filter(parent=parent).exclude(pk=self.instance.pk)
    if others.filter(name__iexact=self.instance.name).exists():
      raise forms.ValidationError(_("There's already a tag with this name there."))
    return parent

  def _typed_parent(self):
    """A name typed with "+ new tag": the existing tag it names (a path
    "Media: Books" followed from the top), else remembered for save() - for
    someone who may add tags."""
    from django.conf import settings
    name = PickerInput.new_name(self, 'parent')
    if not name:
      return None
    node = None
    for part in [p.strip() for p in name.split(getattr(settings, 'CMNSD_PARENT_COMPOUNDER', ': '))]:
      node = Tag.objects.filter(parent=node, name__iexact=part).first()
      if node is None:
        break
    if node is not None:
      return node
    if not self.request.user.has_perm('core.add_tag'):
      raise forms.ValidationError(_("You may not add tags - choose an existing one."))
    self.new_parent_name = name
    return None

  def save(self, commit=True):
    if getattr(self, 'new_parent_name', ''):
      self.instance.parent = self._make_path(self.new_parent_name)
    return super().save(commit=commit)

  def _make_path(self, name):
    """The tag a typed "Media: Books" names, made where missing - each
    published, visible as the tag it's made for (not HierarchyMixin's
    split, which would make "Media" with the site's defaults: a concept,
    community), each new one in the admin history."""
    from django.conf import settings
    from django.contrib.admin.models import ADDITION, LogEntry
    node = None
    for part in [p.strip() for p in name.split(getattr(settings, 'CMNSD_PARENT_COMPOUNDER', ': ')) if p.strip()]:
      node, created = Tag.objects.get_or_create(parent=node, name__iexact=part, defaults={
        'name': part, 'user': self.request.user, 'status': Tag.Status.PUBLISHED, 'visibility': self.instance.visibility,
      })
      if created:
        LogEntry.objects.log_actions(self.request.user.pk, [node], ADDITION, change_message="Created while editing", single_object=True)
    return node


class TagDescriptionForm(forms.ModelForm):
  """Why a tag is there - the context it gives its content."""

  class Meta:
    model = Tag
    fields = ['description']
    labels = {'description': _("description")}
    widgets = {'description': forms.Textarea(attrs={'rows': 5})}


class StatusActionsForm(forms.ModelForm):
  """Status as actions - what can be done next, at most two:
  - concept: Publish; and the way out (below);
  - published: Back to draft; and the way out (below);
  The way out: staff Revoke - also their own records, never delete
  directly; anyone else may Delete their own record.
  - revoked (only staff see it): Republish or Delete - revoking puts a
    record up for review, and a staff member decides.
  Delete and Revoke ask first; deleting goes to the model's list (the
  record is gone for everyone). The form refuses anything it didn't offer.

  For any model with StatusMixin and OwnershipMixin (Content, Note):
    class NoteStatusForm(StatusActionsForm):
      class Meta(StatusActionsForm.Meta):
        model = Note
  """
  choice = True
  confirm = {
    'x': _("Delete this? It will be hidden from everyone - it can be recovered in the admin."),
    'r': _("Revoke this? Only staff will see it until it's restored."),
  }

  class Meta:
    fields = ['status']
    labels = {'status': _("status")}

  def actions(self, user):
    S = self._meta.model.Status
    current = self.instance.status if self.instance.pk else S.CONCEPT
    owner = bool(user and user.is_authenticated and self.instance.user_id == user.pk)
    staff = bool(user and user.is_authenticated and user.is_staff)
    # Staff revoke (their own records too) - a deletion then goes through
    # the review of a revoked record; other owners delete their own.
    way_out = [(S.REVOKED, _("revoke"))] if staff else [(S.DELETED, _("delete"))] if owner else []
    if current == S.CONCEPT:
      return [(S.PUBLISHED, _("publish"))] + way_out
    if current == S.PUBLISHED:
      return [(S.CONCEPT, _("back to draft"), 'before')] + way_out
    if current == S.REVOKED and staff:
      return [(S.PUBLISHED, _("republish"), 'before'), (S.DELETED, _("delete"))]
    return []

  def clean_status(self):
    value = self.cleaned_data['status']
    allowed = {action[0] for action in self.actions(getattr(getattr(self, 'request', None), 'user', None))}
    if value != self.instance.status and value not in allowed:
      raise forms.ValidationError(_("That isn't possible for you from here."))
    return value

  def success_message(self):
    S = self._meta.model.Status
    return {
      S.DELETED: _("“%(item)s” deleted - it can be recovered in the admin."),
      S.REVOKED: _("“%(item)s” revoked - only staff see it now."),
      S.PUBLISHED: _("“%(item)s” published."),   # also after republishing a revoked record
      S.CONCEPT: _("“%(item)s” is a draft again."),
    }.get(self.instance.status, '') % {'item': self.instance}


class PreferencesForm(forms.ModelForm):
  """Your preferences (core.views.PreferencesView): the interface language,
  and who you count as family - they see what you mark visible to
  'family'. One-directional: adding someone doesn't make you theirs.
  Every other active account is offered; those linked to your relatives in
  the tree come first (in_tree)."""
  class Meta:
    from .models import Preferences
    model = Preferences
    fields = ['language', 'family']
    labels = {'language': _("language"), 'family': _("family")}
    help_texts = {
      'language': _("Empty: the site's language (English). The Dutch translation of this site is still to come - for now Dutch changes dates and standard texts only."),
      'family': _("They see what you mark visible to 'family'. It works one way: adding someone doesn't make you their family."),
    }
    widgets = {'family': forms.CheckboxSelectMultiple}

  def __init__(self, *args, user=None, **kwargs):
    super().__init__(*args, **kwargs)
    from django.contrib.auth import get_user_model
    from .preferences import account_name, accounts_in_tree
    self.in_tree = accounts_in_tree(user)
    accounts = list(get_user_model().objects.filter(is_active=True).exclude(pk=user.pk).select_related('person'))
    # Your relatives' accounts first, then everyone by name.
    accounts.sort(key=lambda account: (account.pk not in self.in_tree, account_name(account).casefold()))
    field = self.fields['family']
    field.queryset = field.queryset.filter(pk__in=[account.pk for account in accounts])
    names = {account.pk: account_name(account) for account in accounts}
    field.choices = [(account.pk, names[account.pk]) for account in accounts]
    self.fields['language'].choices = [('', _("site default"))] + [c for c in self.fields['language'].choices if c[0]]
