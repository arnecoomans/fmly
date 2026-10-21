from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from events.models import Event
from people.models import Person, PersonRelation
from places.models import Place


class GedcomExportTests(TestCase):
  """manage.py gedcom_export <token> --depth N (people/gedcom.py, #463)."""

  def setUp(self):
    self.user = get_user_model().objects.create(username='ged')
    self.user.save()
    self.abraham = self.person('Abraham', 'Coomans', 'm', biography='Zie [Maria](person:abc) en [bron](https://example.org/x).')
    self.maria = self.person('Maria', 'Kienjet', 'f')
    self.son = self.person('Pieter', 'Coomans', 'm')
    self.living = self.person('Levend', 'Coomans', 'f')
    self.secret = self.person('Geheim', 'Coomans', 'm', private=True)
    self.grandchild = self.person('Kleinkind', 'Coomans', 'm')
    PersonRelation.objects.create(person_from=self.abraham, person_to=self.maria, relation_type='partner')
    for child in (self.son, self.living, self.secret):
      PersonRelation.objects.create(person_from=self.abraham, person_to=child, relation_type='parent')
      PersonRelation.objects.create(person_from=self.maria, person_to=child, relation_type='parent')
    PersonRelation.objects.create(person_from=self.son, person_to=self.grandchild, relation_type='parent')
    java = Place.objects.create(name='Java', user=self.user)
    soerabaja = Place.objects.create(name='Soerabaja', parent=java, user=self.user)
    self.event('birth', [self.abraham], year=1841, month=5, day=29)
    self.event('death', [self.abraham], year=1897, date_qualifier='circa', places=[soerabaja])
    self.event('marriage', [self.abraham, self.maria], year=1864)
    for person in (self.maria, self.son, self.grandchild):
      self.event('death', [person], year=1900)

  def person(self, given, last, gender, **fields):
    return Person.objects.create(given_name=given, last_name=last, gender=gender, user=self.user, status='p', visibility='c', **fields)

  def event(self, kind, people, places=(), **fields):
    event = Event.objects.create(kind=kind, user=self.user, **fields)
    event.people.set(people)
    event.places.set(places)
    return event

  def export(self, *args):
    out = StringIO()
    call_command('gedcom_export', *args, stdout=out)
    return out.getvalue()

  def test_depth_0_the_person_alone(self):
    text = self.export(self.abraham.token)
    self.assertTrue(text.startswith('0 HEAD') and text.endswith('0 TRLR\n'))
    self.assertEqual(text.count(' INDI\n'), 1)
    self.assertNotIn(' FAM\n', text)
    self.assertIn('1 NAME Abraham /Coomans/', text)
    self.assertIn('2 DATE 29 MAY 1841', text)
    self.assertIn('2 DATE ABT 1897\n2 PLAC Soerabaja, Java', text)          # partial date, place with its parent
    self.assertIn('1 NOTE Zie Maria en bron (https://example.org/x).', text)  # mentions and links as text

  def test_depth_1_family_group(self):
    text = self.export(self.abraham.token, '--depth=1')
    self.assertEqual(text.count(' INDI\n'), 4)                                # Abraham, Maria, Pieter, Levend - not the private son
    self.assertNotIn('Geheim', text)
    self.assertIn('1 NAME L… C…', text)                                       # no death: initials only
    self.assertNotIn('Kleinkind', text)
    family = text[text.index(' FAM\n'):]
    self.assertIn('1 HUSB', family)
    self.assertIn('1 WIFE', family)
    self.assertIn('2 DATE 1864', family)
    self.assertEqual(family.count('1 CHIL'), 2)

  def test_depth_2_grandchildren(self):
    text = self.export(self.abraham.token, '--depth=2')
    self.assertIn('Kleinkind', text)
    self.assertEqual(text.count(' FAM\n'), 2)                                 # Pieter alone with his child: a family of one parent

  def test_long_lines_and_errors(self):
    self.abraham.biography = 'woord ' * 100
    self.abraham.save()
    text = self.export(self.abraham.token)
    self.assertTrue(all(len(line) <= 255 for line in text.splitlines()))
    self.assertIn('2 CONC', text)
    with self.assertRaises(CommandError):
      self.export('nope')
    with self.assertRaises(CommandError):
      self.export(self.abraham.token, '--depth=-1')
