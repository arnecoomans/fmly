"""
Star signs - for the superstitious (Preferences.superstitious): a badge on
a person's page next to their visibility, from an exact birth date. Just
for fun; the signs by their usual (tropical) dates.
"""

from django.utils.translation import gettext_lazy as _

# (first month, first day, symbol, name) - in calendar order from Aquarius;
# Capricorn wraps around the new year. ︎: the symbol as text, not as
# an emoji.
SIGNS = (
  (1, 20, '♒︎', _("Aquarius")),
  (2, 19, '♓︎', _("Pisces")),
  (3, 21, '♈︎', _("Aries")),
  (4, 20, '♉︎', _("Taurus")),
  (5, 21, '♊︎', _("Gemini")),
  (6, 21, '♋︎', _("Cancer")),
  (7, 23, '♌︎', _("Leo")),
  (8, 23, '♍︎', _("Virgo")),
  (9, 23, '♎︎', _("Libra")),
  (10, 23, '♏︎', _("Scorpio")),
  (11, 22, '♐︎', _("Sagittarius")),
  (12, 22, '♑︎', _("Capricorn")),
)


def star_sign(month, day):
  """{'symbol', 'name'} for a day of the year."""
  symbol, name = SIGNS[-1][2:]   # Capricorn, from the turn of the year
  for first_month, first_day, sign_symbol, sign_name in SIGNS:
    if (month, day) >= (first_month, first_day):
      symbol, name = sign_symbol, sign_name
  return {'symbol': symbol, 'name': name}


def person_star_sign(person):
  """Their sign - only from an exact birth date with day and month: a date
  that's ca., before or after, or a year alone, can't tell."""
  birth = person.birth
  if not (birth and birth.month and birth.day and birth.is_exact_date()):
    return None
  return star_sign(birth.month, birth.day)
