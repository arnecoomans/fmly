from django.test import TestCase
from archive.models import Person, FamilyRelations
from django.contrib.auth.models import User

class PersonTestCase(TestCase):
  def setUp(self):
    # Create website user that is responsible for all the persons
    self.user = User.objects.create_user(username='creationuser', password='12345')
    # Load up a family in the test-database
    # Use fictive family as base: https://kro-ncrv.nl/katholiek/encyclopedie/t/twaalf-zonen-van-jakob

    # Father
    Person.objects.create(first_name='Jacob',    last_name='Israel', slug='jacob-israel', user=User.objects.get(username='creationuser'))
    # Wives
    Person.objects.create(first_name='Lea',      last_name='Israel', slug='lea-israel', user=User.objects.get(username='creationuser'))
    Person.objects.create(first_name='Rachel',   last_name='Israel', slug='rachel-israel', user=User.objects.get(username='creationuser'))
    # Sons
    Person.objects.create(first_name='Ruben',    last_name='Israel', slug='ruben-israel', user=User.objects.get(username='creationuser'))
    Person.objects.create(first_name='Simeon',   last_name='Israel', slug='simeon-israel', user=User.objects.get(username='creationuser'))
    Person.objects.create(first_name='Levi',     last_name='Israel', slug='levi-israel', user=User.objects.get(username='creationuser'))
    Person.objects.create(first_name='Juda',     last_name='Israel', slug='juda-israel', user=User.objects.get(username='creationuser'))
    Person.objects.create(first_name='Zebulon',  last_name='Israel', slug='zebulon-israel', user=User.objects.get(username='creationuser'))
    Person.objects.create(first_name='Issakar',  last_name='Israel', slug='issakar-israel', user=User.objects.get(username='creationuser'))
    Person.objects.create(first_name='Dan',      last_name='Israel', slug='dan-israel', user=User.objects.get(username='creationuser'))
    Person.objects.create(first_name='Gad',      last_name='Israel', slug='gad-israel', user=User.objects.get(username='creationuser'))
    Person.objects.create(first_name='Aser',     last_name='Israel', slug='aser-israel', user=User.objects.get(username='creationuser'))
    Person.objects.create(first_name='Naftali',  last_name='Israel', slug='naftali-israel', user=User.objects.get(username='creationuser'))
    Person.objects.create(first_name='Jozef',    last_name='Israel', slug='jozef-israel', user=User.objects.get(username='creationuser'))
    Person.objects.create(first_name='Benjamin', last_name='Israel', slug='benjamin-israel', user=User.objects.get(username='creationuser'))
    # Grandsons
    Person.objects.create(first_name='Efraim',   last_name='Israel', slug='efraim-israel', user=User.objects.get(username='creationuser'))
    Person.objects.create(first_name='Manasse',  last_name='Israel', slug='manasse-israel', user=User.objects.get(username='creationuser'))

    # Set family relations (not all)
    # Ruben is Jacobs son
    FamilyRelations.objects.create(up=Person.objects.get(slug='jacob-israel'), down=Person.objects.get(slug='ruben-israel'))
    # Ruben is Lea's son
    FamilyRelations.objects.create(up=Person.objects.get(slug='lea-israel'), down=Person.objects.get(slug='ruben-israel'))
    # Jozef is Jacobs son
    FamilyRelations.objects.create(up=Person.objects.get(slug='jacob-israel'), down=Person.objects.get(slug='jozef-israel'))
    # Jozef is Rachels son
    FamilyRelations.objects.create(up=Person.objects.get(slug='rachel-israel'), down=Person.objects.get(slug='jozef-israel'))
    # Jozef has two sons
    FamilyRelations.objects.create(up=Person.objects.get(slug='jozef-israel'), down=Person.objects.get(slug='efraim-israel'))
    FamilyRelations.objects.create(up=Person.objects.get(slug='jozef-israel'), down=Person.objects.get(slug='manasse-israel'))

  def test_person_relation_data(self):
    jacob = Person.objects.get(slug='jacob-israel')
    ruben = Person.objects.get(slug='ruben-israel')
    jozef = Person.objects.get(slug='jozef-israel')

    self.assertEqual(jacob.name(), 'Jacob Israel')
    # Jacob has 12 sons. 2 of them are linked
    self.assertEqual(jacob.get_children(), [Person.objects.get(slug='ruben-israel'), Person.objects.get(slug='jozef-israel')])
    # Jacob has had 4 wives. 2 of them are linked
    self.assertEqual(jacob.get_partners(), [Person.objects.get(slug='lea-israel'), Person.objects.get(slug='rachel-israel')])
    # Ruben has different mother than Jozef
    self.assertEqual(ruben.get_parents(), [Person.objects.get(slug='jacob-israel'), Person.objects.get(slug='lea-israel')])
    self.assertEqual(jozef.get_parents(), [Person.objects.get(slug='jacob-israel'), Person.objects.get(slug='rachel-israel')])
    # Jozef has 11 brothers. 1 of them is linked
    self.assertEqual(jozef.get_siblings(), [Person.objects.get(slug='ruben-israel')])
    # Jozef has 2 children
    self.assertEqual(jozef.get_children(), [Person.objects.get(slug='efraim-israel'), Person.objects.get(slug='manasse-israel')])

