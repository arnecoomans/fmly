"""
Edit-mode forms shared by fmly's models (cmnsd object_form blocks).
"""

from django import forms
from django.utils.translation import gettext_lazy as _


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
