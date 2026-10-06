from django import template

register = template.Library()

# Decorative, meaningless rotation - for content-kind placeholder tones
# (.content-card__thumb--*), not for Person avatars. Deterministic (not
# random) so a given record's tint stays stable across page loads, per
# CSS_BRIEFING.md's open item.
_CONTENT_TONES = ('sage', 'dusk', 'warm')

# Meaningful, gender-based avatar tone (specs.css "person avatar tones by
# gender"): dusk is reused as-is for male (already blue-ish); warm/sage
# are content-kind-only and must never be returned here - a green "sage"
# avatar next to a green "sage" content thumbnail would wrongly suggest
# they mean the same thing. Plain gender codes, not Person.Gender, so this
# stays dependency-free of the people app (core is shared/cross-cutting).
_GENDER_TONES = {
  'm': 'dusk',
  'f': 'blossom',
  'o': 'stone',
  'x': 'stone',
}


@register.filter
def content_tone(pk):
  if not pk:
    return _CONTENT_TONES[0]
  return _CONTENT_TONES[int(pk) % len(_CONTENT_TONES)]


@register.filter
def avatar_tone(person):
  return _GENDER_TONES.get(getattr(person, 'gender', None), 'stone')
