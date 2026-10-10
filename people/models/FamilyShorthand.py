from django.db import models

from .PersonRelations import PersonRelation


class FamilyShorthand(models.Model):
  """
  Family relation access shortcuts for Person - kept in its own file so a
  growing list of "what can a Person answer" (see also EventShorthand)
  doesn't turn Person.py into one unmanageable file.

  Each of these returns a plain list (not a QuerySet), so the shape is
  consistent regardless of which path below is taken.

  When Person.objects.with_relations() prefetched relations_from and
  relations_to, these build the result from that cache in Python - zero
  extra queries. Otherwise they fall back to a direct DB query (still just
  one query each) - correct either way, just cheaper when prefetched.
  get_siblings() is the exception: shared parents can't come from self's
  own prefetch (that cache only covers relations self is directly part
  of), so it always costs one extra query for "who else has these
  parents", whether or not the parent lookup itself was served from cache.

  All four are sorted by birth date (ascending, blanks last) via
  _sort_by_birth() - one consistent rule instead of a different one per
  relation type (e.g. gender for parents, "relationship started" for
  partners - the latter isn't even data this project stores). Letting real
  birth order surface a pattern (parents usually list male-then-female,
  since historically the husband was often older) is more honest than
  hard-coding that as a rule - and an exception is then a genuinely
  interesting fact about that couple, not something sorting hides.
  """

  class Meta:
    abstract = True

  def _relations_prefetched(self):
    cache = getattr(self, '_prefetched_objects_cache', {})
    return 'relations_from' in cache and 'relations_to' in cache

  @staticmethod
  def _attach_lifespan(people):
    """Batch-fetch birth AND death events for the given people in one
    query (not one per person, per kind), and cache the result directly on
    each instance as _prefetched_birth/_prefetched_death. EventShorthand's
    birth/death properties check for these first, so this benefits ANY
    later .birth/.death access on these instances - a lifespan display in
    _person_row.html, not just the sort key below."""
    people = list(people)
    if not people:
      return people
    from events.models import Event
    events = Event.objects.current().filter(
      people__in=people, kind__in=(Event.Kind.BIRTH, Event.Kind.DEATH),
    ).order_by('year', 'month', 'day').prefetch_related('people', 'places')   # places: the lifespan in a row
    birth_by_pk, death_by_pk = {}, {}
    for event in events:
      target = birth_by_pk if event.kind == Event.Kind.BIRTH else death_by_pk
      for person in event.people.all():
        # .order_by() above means the first Event seen per person per kind
        # is already their earliest recorded one - matches the ordering
        # EventShorthand.birth/.death's plain .first() would give too.
        if person.pk not in target:
          target[person.pk] = event
    for person in people:
      person._prefetched_birth = birth_by_pk.get(person.pk)
      person._prefetched_death = death_by_pk.get(person.pk)
    return people

  @staticmethod
  def _attach_portraits(people):
    """Batch-fetch each person's primary portrait (content.Portrait with
    is_primary) with its Content, in one query, and cache the link on the
    instance as _primary_portrait_link - read by Person.primary_portrait_link,
    so a list of rows doesn't query once per avatar. Whether THIS viewer may see
    the photo is decided at render time (content_tags.visible_portrait)."""
    people = list(people)
    if not people:
      return people
    from content.models import Portrait
    links = Portrait.objects.filter(person__in=people, is_primary=True).select_related('content')
    by_person = {link.person_id: link for link in links}
    for person in people:
      person._primary_portrait_link = by_person.get(person.pk)
    return people

  @staticmethod
  def _drop_deleted(people):
    """Deleted people (status x) disappear from every relationship list,
    for everyone - applied in the flat parent/child getters and in
    _sort_by_birth(), which all other lists build on. A deleted parent
    thereby also drops out of siblings' "with ..." captions and children's
    co-parent grouping (the child falls into "not recorded"). Concept and
    revoked people are kept here: whether THIS viewer may see them is a
    render-time decision (_person_row.html, status_visible_to)."""
    return [person for person in people if person.status != person.Status.DELETED]

  def _sort_by_birth(self, people):
    """Sort people by birth date, ascending, blanks last. Also attaches
    death (see _attach_lifespan()) since anything getting sorted here is
    about to be displayed in a relationship row, which needs lifespan on
    both ends - not just the birth year this sort itself needs."""
    people = self._attach_portraits(self._attach_lifespan(self._drop_deleted(people)))

    def sort_key(person):
      birth = person._prefetched_birth
      if not birth or not birth.year:
        return (1, 0, 0, 0)
      return (0, birth.year, birth.month or 0, birth.day or 0)

    return sorted(people, key=sort_key)

  def _get_children_flat(self):
    # In a PARENT relation, self is person_from (the parent) and the
    # target person_to is the child. Private: get_children() (below) is the
    # only public entry point for "this person's children" now - other_parent
    # is always functional (there's no real use for an ungrouped list), so
    # this flat fetch is just the first step of building the grouped result,
    # not something callers should reach for directly.
    if self._relations_prefetched():
      return self._drop_deleted(
        r.person_to for r in self.relations_from.all()
        if r.relation_type == PersonRelation.RelationType.PARENT
      )
    child_ids = self.relations_from.filter(
      relation_type=PersonRelation.RelationType.PARENT
    ).values_list('person_to', flat=True)
    return self._drop_deleted(self.__class__.objects.filter(pk__in=child_ids))

  def _get_parents_flat(self):
    # Mirror of _get_children_flat(): self is person_to (the child), the
    # source person_from is the parent. Private and unsorted for the same
    # reason - get_siblings() and Person.other_parent() only need to know
    # *who* the parents are, not in what order, and calling the sorted
    # get_parents() from inside a per-child loop (other_parent() is called
    # once per child in get_children()'s grouping) would re-run
    # _sort_by_birth()'s batch query once per child instead of once total.
    if self._relations_prefetched():
      return self._drop_deleted(
        r.person_from for r in self.relations_to.all()
        if r.relation_type == PersonRelation.RelationType.PARENT
      )
    parent_ids = self.relations_to.filter(
      relation_type=PersonRelation.RelationType.PARENT
    ).values_list('person_from', flat=True)
    return self._drop_deleted(self.__class__.objects.filter(pk__in=parent_ids))

  def get_parents(self):
    return self._sort_by_birth(self._get_parents_flat())

  def get_partners(self):
    # PARTNER rows are canonically ordered by pk (see PersonRelation.save()),
    # not by which side is "self" - so self can be person_from or person_to
    # depending on the other person's pk. Both directions must be checked.
    if self._relations_prefetched():
      partners = [
        r.person_to for r in self.relations_from.all()
        if r.relation_type == PersonRelation.RelationType.PARTNER
      ]
      partners += [
        r.person_from for r in self.relations_to.all()
        if r.relation_type == PersonRelation.RelationType.PARTNER
      ]
    else:
      from_ids = self.relations_from.filter(
        relation_type=PersonRelation.RelationType.PARTNER
      ).values_list('person_to', flat=True)
      to_ids = self.relations_to.filter(
        relation_type=PersonRelation.RelationType.PARTNER
      ).values_list('person_from', flat=True)
      # list(from_ids) + list(to_ids) would evaluate both querysets in Python
      # first (2 extra round trips) before the final filter; union() keeps
      # the whole thing as one query with the ids combined in SQL.
      partners = list(self.__class__.objects.filter(pk__in=from_ids.union(to_ids)))
    return self._sort_by_birth(partners)

  def get_siblings(self):
    """This person's siblings, each flagged full vs half by comparing
    parent sets - not stored, computed the same way the plain list always
    was (see the class docstring's "why get_siblings() is the exception"
    note); this just keeps the comparison instead of throwing it away.
    Structure: [{'person': Person, 'is_half': bool, 'shared_parent':
    Person or None}, ...]. 'is_half' is True when the sibling shares only
    some of this person's recorded parents, not all of them.
    'shared_parent' names the one parent in common for a half-sibling
    (None for a full sibling, or when this person has only one parent
    recorded - see below); the template puts it in the row's meta line
    (CSS_BRIEFING.md section 2), never in the role pill itself, which
    stays a fixed short word ("Sibling" / "Half-sibling") - a person's
    full name doesn't belong in a pill sized for one word.
    When this person has only one parent recorded, every sibling
    necessarily shares that one parent and comes back as a full
    "Sibling" - there's no way to know about a second, unrecorded parent
    from here, the same limit Person.other_parent() has for children.
    Unlike get_parents()/get_partners(), this doesn't return plain Person
    objects - see get_children()'s docstring for why an enriched
    structure beats a flat list once "which parent(s)" matters for
    display.
    """
    my_parent_ids = {p.pk for p in self._get_parents_flat()}
    if not my_parent_ids:
      return []
    sibling_ids = PersonRelation.objects.filter(
      relation_type=PersonRelation.RelationType.PARENT,
      person_from__in=my_parent_ids,
    ).exclude(person_to=self).values_list('person_to', flat=True)
    siblings = list(self.__class__.objects.filter(pk__in=sibling_ids).distinct())
    # Re-fetch with_relations() so each sibling's _get_parents_flat() call
    # below (needed to tell full from half) uses the prefetch cache
    # instead of costing 2 queries per sibling - same fix get_children()
    # applies for other_parent(), same reason. Re-sort after the re-fetch,
    # same order-loss caveat get_children() notes for filter(pk__in=...).
    siblings = self.__class__.objects.with_relations().filter(pk__in=[s.pk for s in siblings])
    siblings = self._sort_by_birth(siblings)

    results = []
    for sibling in siblings:
      shared = [p for p in sibling._get_parents_flat() if p.pk in my_parent_ids]
      is_half = len(shared) < len(my_parent_ids)
      results.append({
        'person': sibling,
        'is_half': is_half,
        'shared_parent': shared[0] if is_half and len(shared) == 1 else None,
      })
    return results

  def get_children(self):
    """This person's children, grouped by other_parent (see Person.other_parent()),
    ordered to match get_partners() - one heading per co-parent instead of
    a caption repeated on every child row (CSS_BRIEFING.md section 2).
    Structure: [{'parent': Person or None, 'children': [Person, ...]}, ...] -
    'parent' is None for the trailing "not recorded" group, if any.

    Unlike get_parents()/get_partners()/get_siblings(), this returns groups,
    not a flat list - an ungrouped children list has no real use of its own
    (other_parent is always the functional thing you want when displaying
    children), so there's no separate flat get_children() to keep in sync.

    Lives on the model (not computed in a view) so the person_detail
    template - and, eventually, the cmnsd API rendering the same template -
    can call this from `person` alone, with no view-specific context setup
    required.
    """
    children = self._get_children_flat()
    # Re-fetch with_relations() so each child's other_parent() call (which
    # calls get_parents() internally) uses the prefetch cache instead of
    # costing 2 queries per child - same fix as PersonManager.optimized()
    # exists for.
    children = self.__class__.objects.with_relations().filter(pk__in=[c.pk for c in children])
    # Sort here, after the re-fetch above - filter(pk__in=...) doesn't
    # preserve the input list's order, so sorting _get_children_flat()'s
    # result first would just get scrambled by the re-fetch. Sorting once
    # before grouping means each group's children list comes out already
    # in birth order too, since the grouping loop below just appends in
    # whatever order it iterates `children`.
    children = self._sort_by_birth(children)

    groups_by_key = {}
    for child in children:
      other = child.other_parent(self)
      key = other.pk if other else None
      if key not in groups_by_key:
        groups_by_key[key] = {'parent': other, 'children': []}
      groups_by_key[key]['children'].append(child)

    partners = self.get_partners()
    children_groups = []
    seen_keys = set()
    for partner in partners:
      if partner.pk in groups_by_key:
        children_groups.append(groups_by_key[partner.pk])
        seen_keys.add(partner.pk)
    for key, group in groups_by_key.items():
      # An other_parent who was never a recorded partner (shouldn't happen
      # in today's data - every co-parent pair got an explicit Partner
      # relation - but a future import gap could reintroduce it). Still
      # gets its own named group, just after the known partners.
      if key is not None and key not in seen_keys:
        children_groups.append(group)
        seen_keys.add(key)
    if None in groups_by_key:
      children_groups.append(groups_by_key[None])
    return children_groups
