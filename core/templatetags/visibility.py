from django import template

register = template.Library()


@register.filter
def visible_to(obj, user):
  """{% if person|visible_to:request.user %} - wraps VisibilityMixin.is_visible_to()
  so templates can call it with an argument (a bare {% if %} can't pass
  one). Tolerates user=None (anonymous, or a future API render with no
  full request) the same way is_visible_to() already does."""
  return obj.is_visible_to(user)


@register.filter
def status_visible_to(obj, user):
  """{% if person|status_visible_to:request.user %} - wraps
  StatusMixin.is_status_visible_to(): published for everyone, concept for
  its creator and staff, revoked for staff, deleted for no one. Objects
  without a status pass."""
  check = getattr(obj, 'is_status_visible_to', None)
  return check(user) if check else True


@register.filter
def obfuscate_name(name):
  """First letter of each word kept, the rest replaced by a single '…' -
  not the real remaining letters or their count, so word length isn't
  leaked either. Used when visible_to() says no: still shows the shape of
  a name (word count, initials) without revealing who it actually is.

  A word starting with punctuation - "(Bert)" in "Albert (Bert) Coomans" -
  has nothing to reveal a letter for: word[0] would be "(", not an actual
  initial, so the word is dropped entirely rather than keeping the
  punctuation as if it meant something."""
  words = [word for word in name.split(' ') if word]
  return ' '.join(f"{word[0]}…" for word in words if word[0].isalpha())
