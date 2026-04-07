"""
Family relations service for the Person model.

Derives family members (parents, children, siblings, partners) from a Person
instance. When the person was fetched via Person.objects.optimized() the
relation_down / relation_up relations are already prefetched — this service
uses those to build the family in Python (zero extra queries). When they are
not prefetched, it falls back to the annotated DB query.
"""

from django.db.models import (
  Exists, OuterRef, Case, When, Value, CharField,
  Subquery, IntegerField, F, BooleanField, Prefetch, Q,
)

from archive.models.Event import Event


def _build_from_prefetch(person):
  """
  Build family list from prefetched relation_down / relation_up.

  FamilyRelations fields:
    up   FK → related_name='relation_down'  (person is the up/parent/partner side)
    down FK → related_name='relation_up'    (person is the down/child side)

  So:
    person.relation_down → rels where person is 'up' → person is parent or explicit partner
    person.relation_up   → rels where person is 'down' → person is child or explicit partner
  """
  family = []
  seen_pks = set()

  # person.relation_down: person is 'up'
  # type=parent → person is the parent, rel.down is the child
  # type=partner → person is one side of partnership, rel.down is the partner
  for rel in person.relation_down.all():
    if rel.type == 'parent':
      child = rel.down
      if child.pk not in seen_pks:
        child.relation_type = 'child'
        child.relation_id = rel.pk
        family.append(child)
        seen_pks.add(child.pk)
    elif rel.type == 'partner':
      partner = rel.down
      if partner.pk not in seen_pks:
        partner.relation_type = 'partner'
        partner.relation_id = rel.pk
        family.append(partner)
        seen_pks.add(partner.pk)

  # person.relation_up: person is 'down'
  # type=parent → rel.up is the parent of person
  # type=partner → rel.up is the partner of person
  for rel in person.relation_up.all():
    if rel.type == 'parent':
      parent = rel.up
      if parent.pk not in seen_pks:
        parent.relation_type = 'parent'
        parent.relation_id = rel.pk
        family.append(parent)
        seen_pks.add(parent.pk)
    elif rel.type == 'partner':
      partner = rel.up
      if partner.pk not in seen_pks:
        partner.relation_type = 'partner'
        partner.relation_id = rel.pk
        family.append(partner)
        seen_pks.add(partner.pk)

  from archive.models.person import FamilyRelations

  # Siblings: persons who share a parent with person
  # Collect parent PKs from the prefetch, then find their other children
  parent_pks = {rel.up_id for rel in person.relation_up.all() if rel.type == 'parent'}
  if parent_pks:
    sibling_rels = FamilyRelations.objects.filter(
      type='parent', up_id__in=parent_pks
    ).exclude(down_id=person.pk).select_related('down').prefetch_related(
      Prefetch('down__events', queryset=Event.objects.filter(type__in=['birth', 'death']))
    )
    for rel in sibling_rels:
      sibling = rel.down
      if sibling.pk not in seen_pks:
        sibling.relation_type = 'sibling'
        sibling.relation_id = rel.pk
        family.append(sibling)
        seen_pks.add(sibling.pk)

  # Co-parents: batch-query other parents for all children so the template
  # can display "with X:" groupings without triggering get_family() per child.
  # Also derives implied partners (persons who share a child) from this data.
  children_in_family = [m for m in family if m.relation_type == 'child']
  if children_in_family:
    child_pks = [c.pk for c in children_in_family]
    co_parent_rels = FamilyRelations.objects.filter(
      type='parent', down_id__in=child_pks
    ).exclude(up_id=person.pk).select_related('up')
    co_parent_map = {}
    for rel in co_parent_rels:
      co_parent_map.setdefault(rel.down_id, []).append(rel.up)
      # Implied partner: anyone who shares a child is a partner
      co_parent = rel.up
      if co_parent.pk not in seen_pks:
        co_parent.relation_type = 'partner'
        co_parent.relation_id = rel.pk
        family.append(co_parent)
        seen_pks.add(co_parent.pk)
    for child in children_in_family:
      child.co_parents = co_parent_map.get(child.pk, [])

  return family


def _build_from_db(person):
  """
  Build family list via annotated DB query.
  Fallback when relation_up / relation_down are not prefetched.
  """
  from archive.models.person import FamilyRelations

  PersonModel = person.__class__

  parent_rel = FamilyRelations.objects.filter(
    down_id=person.pk, type='parent', up_id=OuterRef('pk'),
  )
  child_rel = FamilyRelations.objects.filter(
    up_id=person.pk, type='parent', down_id=OuterRef('pk'),
  )
  explicit_partner_rel = FamilyRelations.objects.filter(type='partner').filter(
    Q(up_id=person.pk, down_id=OuterRef('pk')) |
    Q(down_id=person.pk, up_id=OuterRef('pk'))
  )
  shared_child_partner_rel = FamilyRelations.objects.filter(
    type='parent',
    up_id=person.pk,
    down__relation_up__type='parent',
    down__relation_up__up_id=OuterRef('pk'),
  )
  self_parents = FamilyRelations.objects.filter(
    down_id=person.pk, type='parent',
  ).values('up_id')
  sibling_rel = FamilyRelations.objects.filter(
    type='parent',
    up_id__in=Subquery(self_parents),
    down_id=OuterRef('pk'),
  ).exclude(down_id=person.pk)

  birth_qs = (
    Event.objects
    .filter(people=OuterRef('pk'), type='birth')
    .order_by('-year', '-month', '-day')
  )

  qs = (
    PersonModel.objects
    .exclude(pk=person.pk)
    .annotate(
      _is_parent=Exists(parent_rel),
      _is_child=Exists(child_rel),
      _is_sibling=Exists(sibling_rel),
      _is_partner_explicit=Exists(explicit_partner_rel),
      _is_partner_shared=Exists(shared_child_partner_rel),
    )
    .annotate(
      _is_partner=Case(
        When(
          Q(_is_partner_explicit=True) | Q(_is_partner_shared=True),
          then=Value(True),
        ),
        default=Value(False),
        output_field=BooleanField(),
      )
    )
    .filter(
      Q(_is_parent=True) |
      Q(_is_child=True) |
      Q(_is_sibling=True) |
      Q(_is_partner=True)
    )
    .annotate(
      relation_type=Case(
        When(_is_parent=True, then=Value('parent')),
        When(_is_child=True, then=Value('child')),
        When(_is_partner=True, then=Value('partner')),
        When(_is_sibling=True, then=Value('sibling')),
        default=Value('family'),
        output_field=CharField(),
      ),
      relation_id=Case(
        When(_is_parent=True, then=Subquery(parent_rel.values('id')[:1])),
        When(_is_child=True, then=Subquery(child_rel.values('id')[:1])),
        When(_is_partner_explicit=True, then=Subquery(explicit_partner_rel.values('id')[:1])),
        When(_is_partner_shared=True, then=Subquery(shared_child_partner_rel.values('id')[:1])),
        When(_is_sibling=True, then=Subquery(sibling_rel.values('id')[:1])),
        default=Value(None),
        output_field=IntegerField(),
      ),
      birth_year=Subquery(birth_qs.values('year')[:1], output_field=IntegerField()),
      birth_month=Subquery(birth_qs.values('month')[:1], output_field=IntegerField()),
      birth_day=Subquery(birth_qs.values('day')[:1], output_field=IntegerField()),
    )
    .order_by(
      F('birth_year').asc(nulls_last=True),
      F('birth_month').asc(nulls_last=True),
      F('birth_day').asc(nulls_last=True),
    )
    .prefetch_related(
      Prefetch('events', queryset=Event.objects.filter(type__in=['birth', 'death']))
    )
  )

  result = list(qs)

  # Batch-query co-parents for children so the template can group them
  # without calling get_family() on each child.
  children = [m for m in result if m.relation_type == 'child']
  if children:
    child_pks = [c.pk for c in children]
    co_parent_rels = FamilyRelations.objects.filter(
      type='parent', down_id__in=child_pks
    ).exclude(up_id=person.pk).select_related('up')
    co_parent_map = {}
    for rel in co_parent_rels:
      co_parent_map.setdefault(rel.down_id, []).append(rel.up)
    for child in children:
      child.co_parents = co_parent_map.get(child.pk, [])

  return result


def get_family(person):
  """
  Returns a list of all family members with a `relation_type` attribute.
  Uses prefetch cache when available, falls back to DB query.
  """
  if not hasattr(person, '_family_list'):
    prefetch_cache = getattr(person, '_prefetched_objects_cache', {})
    if 'relation_up' in prefetch_cache and 'relation_down' in prefetch_cache:
      person._family_list = _build_from_prefetch(person)
    else:
      person._family_list = _build_from_db(person)
  return person._family_list


def get_parents(person):
  return [p for p in get_family(person) if p.relation_type == 'parent']


def get_children(person):
  return [p for p in get_family(person) if p.relation_type == 'child']


def get_partners(person):
  return [p for p in get_family(person) if p.relation_type == 'partner']


def get_siblings(person):
  return [p for p in get_family(person) if p.relation_type == 'sibling']
