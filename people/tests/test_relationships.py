from django.contrib.auth import get_user_model
from django.test import TestCase

from people.models import Person, PersonRelation

PARENT = PersonRelation.RelationType.PARENT
PARTNER = PersonRelation.RelationType.PARTNER


class RelationshipStatusTests(TestCase):
  """Deleted relatives disappear for everyone; concept relatives show only
  to their creator and staff, marked as not published."""

  def setUp(self):
    User = get_user_model()
    self.creator = User.objects.create(username='creator')
    self.member = User.objects.create(username='member')
    self.staff = User.objects.create(username='staff', is_staff=True)
    self.child = self.person('Child')
    self.father = self.person('Father')
    self.mother = self.person('Mother')
    self.half_brother = self.person('Halfbrother')
    for parent in (self.father, self.mother):
      PersonRelation.objects.create(person_from=parent, person_to=self.child, relation_type=PARENT)
    PersonRelation.objects.create(person_from=self.father, person_to=self.mother, relation_type=PARTNER)
    PersonRelation.objects.create(person_from=self.mother, person_to=self.half_brother, relation_type=PARENT)

  def person(self, name, status='p'):
    return Person.objects.create(given_name=name, user=self.creator, status=status, visibility='c')

  def set_status(self, person, status):
    Person.objects.filter(pk=person.pk).update(status=status)

  def fresh(self, person):
    return Person.objects.get(pk=person.pk)

  def test_deleted_parent_disappears_everywhere(self):
    self.set_status(self.mother, 'x')
    self.assertEqual(self.fresh(self.child).get_parents(), [self.father])
    # The half-brother was related only through the deleted mother.
    self.assertEqual(self.fresh(self.child).get_siblings(), [])
    # Father's child now has no recorded co-parent instead of a deleted one.
    groups = self.fresh(self.father).get_children()
    self.assertEqual([(g['parent'], g['children']) for g in groups], [(None, [self.child])])

  def test_deleted_child_disappears(self):
    self.set_status(self.child, 'x')
    self.assertEqual(self.fresh(self.father).get_children(), [])

  def page(self, user, person):
    self.client.force_login(user)
    return self.client.get(person.get_absolute_url()).content.decode()

  def test_concept_relative_only_for_creator_and_staff_and_marked(self):
    self.set_status(self.mother, 'c')
    self.assertNotIn('Mother', self.page(self.member, self.child))
    for user in (self.creator, self.staff):
      html = self.page(user, self.child)
      self.assertIn('Mother', html)
      self.assertIn('person-row--needs-attention', html)
      self.assertIn('not published', html)

  def test_concept_person_page_is_marked_for_creator(self):
    self.set_status(self.mother, 'c')
    self.assertIn('not published', self.page(self.creator, self.fresh(self.mother)))

  def test_concept_coparent_not_named_in_children_heading(self):
    self.set_status(self.mother, 'c')
    html = self.page(self.member, self.father)
    self.assertIn('Child', html)
    self.assertNotIn('Mother', html)
    self.assertIn('Mother', self.page(self.creator, self.father))
