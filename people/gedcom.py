"""
GEDCOM 5.5.1 export (issue #463) - what nearly every genealogy program
reads. One person, and with depth > 0 their partners and children, and so on
down: depth 1 is a family group, depth 2 adds the children's partners and
the grandchildren. The rules:

- Living people - everyone without a death event - keep their place in the
  tree, but with initials only (obfuscate_name): no dates, places or notes.
- Private people (living by definition) and outsiders are left out
  entirely, and so is anything not published (a draft, revoked, deleted).
- Events: birth and death on the person, marriage on the family - no
  descriptions. Partial dates as they are (ABT, BEF, AFT); places with
  their parents ("Soerabaja, Java, Nederlands Indië").
- A biography as a NOTE (not for the living), its mentions as their words.
- Families (FAM) from PersonRelation: one per partner pair with their
  children in common, one with a single parent for children whose other
  parent is unknown or left out.
- Record ids from tokens, so they stay the same between exports (at most
  20 characters, as 5.5.1 asks).

No request: a management command (people/management/commands/
gedcom_export.py) is staff by nature - the rules above protect people.
"""

import datetime
import re

from django.db.models import Q

MONTHS = ('JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC')
QUALIFIERS = {'circa': 'ABT ', 'before': 'BEF ', 'after': 'AFT '}
# [label](scheme:token) -> label (cmnsd/models/Mention.py MENTION_IN_TEXT, with its words).
MENTION = re.compile(r'\[((?:[^\]\\]|\\.)*)\]\([a-z]+:[A-Za-z0-9_-]+\)')
# [label](https://...) -> label (https://...): a link as text, no Markdown.
LINK = re.compile(r'\[((?:[^\]\\]|\\.)*)\]\((https?://[^)\s]+)\s*\)')
# 5.5.1: a line at most 255 characters - longer text goes on in CONC lines.
LINE = 200


def included(person):
  return person.status == 'p' and not person.private and person.family_connection != 'outsider'


def collect(root, depth=0):
  """The people to export: root, and per level of depth the partners and
  children of the level before - only those included. Returns (people by
  pk, partner pairs, child -> parents) among them."""
  from .models import Person, PersonRelation
  people = {root.pk: root} if included(root) else {}
  level = set(people)
  for _step in range(depth):
    if not level:
      break
    found = set()
    for relation in PersonRelation.objects.filter(
      Q(person_from__in=level) | Q(person_to__in=level, relation_type='partner'), relation_type__in=('parent', 'partner'),
    ):
      if relation.relation_type == 'partner':
        found |= {relation.person_from_id, relation.person_to_id}
      else:   # a parent in this level: their child
        found.add(relation.person_to_id)
    new = Person.objects.filter(pk__in=found - set(people))
    level = set()
    for person in new:
      if included(person):
        people[person.pk] = person
        level.add(person.pk)
  pairs, parents = set(), {}
  for relation in PersonRelation.objects.filter(person_from__in=people, person_to__in=people, relation_type__in=('parent', 'partner')):
    if relation.relation_type == 'partner':
      pairs.add(tuple(sorted((relation.person_from_id, relation.person_to_id))))
    else:
      parents.setdefault(relation.person_to_id, set()).add(relation.person_from_id)
  return people, pairs, parents


def export(root, depth=0):
  """The GEDCOM text for root and depth levels of partners and children."""
  from events.models import Event
  from core.templatetags.visibility import obfuscate_name
  people, pairs, parents = collect(root, depth)
  events = list(
    Event.objects.filter(people__in=people.values(), kind__in=('birth', 'death', 'marriage'), status='p')
    .distinct().prefetch_related('people', 'places__parent__parent__parent__parent')
  )
  on = {event.pk: {p.pk for p in event.people.all()} for event in events}
  died = {pk for event in events if event.kind == 'death' for pk in on[event.pk]}

  def living(person):
    return person.pk not in died

  # Families: a partner pair with their children in common; a parent alone
  # with the children whose other parent isn't here.
  families = []
  for pair in sorted(pairs):
    kids = [pk for pk, of in parents.items() if set(pair) <= of]
    marriage = next((e for e in events if e.kind == 'marriage' and set(pair) <= on[e.pk]), None)
    families.append((list(pair), kids, marriage))
  for pk, of in parents.items():
    if not any(set(pair) <= of for pair in pairs):
      for parent in sorted(of):
        group = next((f for f in families if f[0] == [parent] and f[2] is None), None)
        if group is None:
          families.append(([parent], [pk], None))
        else:
          group[1].append(pk)

  def xref(person):
    return f'@I{person.token[:19]}@'

  def fam_xref(spouses):
    return '@F' + ''.join(people[pk].token[:9] for pk in spouses)[:19] + '@'

  def birth_order(pk):
    birth = next((e for e in events if e.kind == 'birth' and pk in on[e.pk]), None)
    return (birth is None, birth.year or 0 if birth else 0, birth.month or 0 if birth else 0, birth.day or 0 if birth else 0)

  famc, fams = {}, {}
  for spouses, kids, _marriage in families:
    kids.sort(key=birth_order)
    for kid in kids:
      famc[kid] = fam_xref(spouses)
    for spouse in spouses:
      fams.setdefault(spouse, []).append(fam_xref(spouses))

  today = datetime.date.today()
  lines = [
    '0 HEAD', '1 SOUR FMLY', '2 NAME FMLY3', '1 GEDC', '2 VERS 5.5.1', '2 FORM LINEAGE-LINKED', '1 CHAR UTF-8',
    f'1 DATE {today.day} {MONTHS[today.month - 1]} {today.year}',
  ]
  for person in sorted(people.values(), key=lambda p: (p.pk != root.pk, birth_order(p.pk))):
    lines.append(f'0 {xref(person)} INDI')
    if living(person):
      lines.append(f'1 NAME {obfuscate_name(person.get_full_name())}')
    else:
      lines += _names(person)
    lines.append('1 SEX ' + {'m': 'M', 'f': 'F'}.get(person.gender, 'U'))
    if not living(person):
      for event in events:
        if event.kind in ('birth', 'death') and person.pk in on[event.pk]:
          lines += _event('BIRT' if event.kind == 'birth' else 'DEAT', event)
      if person.biography:
        lines += _note(LINK.sub(r'\1 (\2)', MENTION.sub(r'\1', person.biography)))
    if person.pk in famc:
      lines.append(f'1 FAMC {famc[person.pk]}')
    for family in fams.get(person.pk, []):
      lines.append(f'1 FAMS {family}')
  for spouses, kids, marriage in families:
    lines.append(f'0 {fam_xref(spouses)} FAM')
    for tag, pk in _spouse_tags([people[pk] for pk in spouses]):
      lines.append(f'1 {tag} {xref(people[pk])}')
    if marriage and not any(living(people[pk]) for pk in spouses):
      lines += _event('MARR', marriage)
    for kid in kids:
      lines.append(f'1 CHIL {xref(people[kid])}')
  lines.append('0 TRLR')
  return '\n'.join(lines) + '\n'


def _names(person):
  given, last = person.given_name or '', person.last_name or ''
  lines = [f'1 NAME {given} /{last}/'.replace('  ', ' ')]
  if given:
    lines.append(f'2 GIVN {given}')
  if last:
    lines.append(f'2 SURN {last}')
  if person.called_name or person.nickname:
    lines.append(f'2 NICK {person.called_name or person.nickname}')
  if person.married_name:
    lines += [f'1 NAME {given} /{person.married_name}/'.replace('  ', ' '), '2 TYPE married']
  return lines


def _date(event):
  if not event.year:
    return None
  parts = [str(event.day) if event.day else '', MONTHS[event.month - 1] if event.month else '', str(event.year)]
  return QUALIFIERS.get(event.date_qualifier, '') + ' '.join(part for part in parts if part)


def _place(event):
  place = next(iter(event.places.all()), None)
  names = []
  while place is not None:
    names.append(place.name)
    place = place.parent
  return ', '.join(names) or None


def _event(tag, event):
  lines = [f'1 {tag}']
  date, place = _date(event), _place(event)
  if date:
    lines.append(f'2 DATE {date}')
  if place:
    lines.append(f'2 PLAC {place}')
  return lines


def _note(text):
  """A NOTE: its lines as CONT, a line longer than LINE split into CONC
  pieces - never at a space, which some programs drop at a line's end."""
  lines = []
  for index, row in enumerate(text.strip().splitlines() or ['']):
    pieces = []
    while len(row) > LINE:
      cut = LINE
      while cut > 1 and (row[cut - 1] == ' ' or row[cut] == ' '):
        cut -= 1
      pieces.append(row[:cut])
      row = row[cut:]
    pieces.append(row)
    for number, piece in enumerate(pieces):
      tag = '1 NOTE' if index == 0 and number == 0 else ('2 CONT' if number == 0 else '2 CONC')
      lines.append(f'{tag} {piece}'.rstrip())
  return lines


def _spouse_tags(spouses):
  """HUSB / WIFE by gender; unknown takes the slot that's free."""
  tags, taken = [], set()
  for person in sorted(spouses, key=lambda p: p.gender not in ('m', 'f')):
    tag = {'m': 'HUSB', 'f': 'WIFE'}.get(person.gender) or ('WIFE' if 'HUSB' in taken else 'HUSB')
    taken.add(tag)
    tags.append((tag, person.pk))
  return tags
