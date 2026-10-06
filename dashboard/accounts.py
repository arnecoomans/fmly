"""
Accounts (/dashboard/accounts/, dashboard.views.AccountsView), for staff who
may change users: accounts waiting for approval - registered while
CMNSD_REGISTRATION_REQUIRES_APPROVAL: inactive, never signed in - to
approve or decline; and every active account with when it last signed in
and last did something (an edit, a comment, an upload, a note).
"""

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Max


def may_manage_accounts(user):
  return bool(user and user.is_authenticated and user.is_staff and user.has_perm('auth.change_user'))


def waiting():
  """Accounts waiting for approval: inactive and never signed in - one that
  was switched off later has signed in before, and isn't waiting."""
  return get_user_model().objects.filter(is_active=False, last_login__isnull=True).order_by('-date_joined')


def approve(user):
  """Active - and in the default groups (REGISTER_DEFAULT_GROUPS), which
  registration already gave it; added again if they went missing."""
  if not (user.is_active is False and user.last_login is None):
    return False
  user.is_active = True
  user.save(update_fields=['is_active'])
  for name in getattr(settings, 'REGISTER_DEFAULT_GROUPS', []):
    group = Group.objects.filter(name=name).first()
    if group:
      user.groups.add(group)
  return True


def decline(user):
  """Delete an account that's still waiting - never anyone who signed in:
  they may have history; switch those off in the admin instead."""
  if not (user.is_active is False and user.last_login is None):
    return False
  user.delete()
  return True


def activity():
  """[account] - every active account, most recently active first, each
  with .last_activity (when) and .last_activity_kind (edit / comment /
  upload / note) - the latest of the four - next to its last_login."""
  from content.models import Content
  from core.models import Comment
  from notes.models import Note
  sources = (
    ('edit', LogEntry.objects.values('user').annotate(at=Max('action_time'))),
    ('comment', Comment.objects.values('user').annotate(at=Max('date_created'))),
    ('upload', Content.objects.values('user').annotate(at=Max('date_created'))),
    ('note', Note.objects.values('user').annotate(at=Max('date_created'))),
  )
  latest = {}
  for kind, rows in sources:
    for row in rows:
      if row['user'] and row['at'] and (row['user'] not in latest or row['at'] > latest[row['user']][0]):
        latest[row['user']] = (row['at'], kind)
  accounts = list(get_user_model().objects.filter(is_active=True).select_related('person').prefetch_related('groups'))
  for account in accounts:
    account.last_activity, account.last_activity_kind = latest.get(account.pk, (None, ''))
  moments = lambda a: max([m for m in (a.last_login, a.last_activity) if m] or [None], key=lambda m: m.timestamp() if m else 0)
  return sorted(accounts, key=lambda a: (moments(a) is None, -(moments(a).timestamp() if moments(a) else 0)))
