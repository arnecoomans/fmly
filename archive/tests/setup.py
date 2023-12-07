from archive.models.comment import Comment
from archive.models.image import Image, Group, Attachment
from archive.models.note import Note
from archive.models.person import Person, FamilyRelations
from archive.models.tag import Tag

from django.contrib.auth.models import User


class setUp:
  def setUp(self):
    ''' Create users '''
    admin_user            = User.objects.create_superuser('admin-user', 'django.admin@cmns.nl', 'safe-password')   
    image_user            = User.objects.create(username='upload-user')
    comment_user          = User.objects.create(username='comment-user')
    tag_user              = User.objects.create(username='tag-user')

    ''' Add People 
        Adds a family with a father, a mother and two children
    '''
    person_father         = Person.objects.create(first_name='father', user=admin_user)
    person_mother         = Person.objects.create(first_name='mother', user=admin_user)
    person_first_child    = Person.objects.create(first_name='child', user=admin_user)
    person_second_child   = Person.objects.create(first_name='second child', user=admin_user)
    FamilyRelations.objects.create(up=person_father, down=person_mother, type='partner')
    FamilyRelations.objects.create(up=person_father, down=person_first_child, type='parent')
    FamilyRelations.objects.create(up=person_mother, down=person_first_child, type='parent')
    FamilyRelations.objects.create(up=person_father, down=person_second_child, type='parent')
    FamilyRelations.objects.create(up=person_mother, down=person_second_child, type='parent')

    ''' Add Tags '''
    tag_one               = Tag.objects.create(title='tag one', slug='tag-one', user=tag_user)
    tag_two               = Tag.objects.create(title='tag two', slug='tag-two', user=tag_user)
    
    ''' Grouping '''
    group                 = Group.objects.create(title='default group', user=admin_user)

    ''' Create Image '''
    image = Image.objects.create(slug='test-image-one',
                                 title='This is a test-image',
                                 user=image_user,
                                 )
    image.people.add(person_father, person_mother)
    image.tag.add(tag_one, tag_two)
    image.groups.add(group)
    
    Comment.objects.create(content='this is a comment on an image', image=image, user=comment_user)