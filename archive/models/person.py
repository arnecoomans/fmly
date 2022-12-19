from django.db import models
from django.urls import reverse, reverse_lazy
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator

class Person(models.Model):
  ''' Model: Person
      People are:
      - tagged on an image
      - related to another person
  '''
  first_name          = models.CharField(max_length=255, blank=True, verbose_name='Roepnaam')
  given_names         = models.CharField(max_length=255, blank=True, verbose_name='Voornamen', help_text='Alle voornamen, inclusief roepnaam')
  last_name           = models.CharField(max_length=255, blank=True, verbose_name='Achternaam', help_text='Achternaam bij geboorte')
  married_name        = models.CharField(max_length=255, blank=True, verbose_name='Getrouwde Achternaam', help_text='Achternaam van echtgeno(o)t(e)')

  nickname            = models.CharField(max_length=255, blank=True, verbose_name='Bijnaam')
  email               = models.EmailField(blank=True, help_text='Dit veld is alleen zichtbaar voor jou en voor de site-beheerder(s). Vul je e-mailadres in zodat we je een wachtwoord-reset email kunnen sturen als je niet langer kan inloggen.')
  slug                = models.CharField(max_length=255, unique=True)
  # Information
  place_of_birth      = models.CharField(max_length=255, blank=True)
  place_of_death      = models.CharField(max_length=255, blank=True)
  # Dating
  MONTHS = [(1, 'januari'), (2, 'februari'), (3, 'maart'), (4, 'april'), (5, 'mei'), (6, 'juni'), (7, 'juli'), (8, 'augustus'), (9, 'september'), (10, 'oktober'), (11, 'november'), (12, 'december')]
  date_of_birth       = models.DateField(null=True, blank=True, help_text='Format: year-month-date, for example 1981-08-11')
  year_of_birth       = models.PositiveSmallIntegerField(blank=True, null=True, help_text='Is automatically filled when date is supplied')
  month_of_birth      = models.PositiveSmallIntegerField(blank=True, null=True, help_text='', choices=MONTHS)
  day_of_birth        = models.PositiveSmallIntegerField(blank=True, null=True, help_text='', validators=[MaxValueValidator(31), MinValueValidator(1)])
  date_of_death       = models.DateField(null=True, blank=True, help_text='Format: year-month-date, for example 1981-08-11')
  year_of_death       = models.PositiveSmallIntegerField(blank=True, null=True, help_text='Is automatically filled when date is supplied')
  month_of_death      = models.PositiveSmallIntegerField(blank=True, null=True, help_text='', choices=MONTHS)
  day_of_death        = models.PositiveSmallIntegerField(blank=True, null=True, help_text='')

  moment_of_death_unconfirmed = models.BooleanField(default=False, help_text='Set True if moment of death is unknown but person has deceased.')

  # Bio
  bio                 = models.TextField(blank=True, help_text='Markdown supported')
  # Meta
  related_user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='related_person')
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  date_modified       = models.DateTimeField(auto_now=True)
  date_created        = models.DateTimeField(auto_now_add=True)
  
  class Meta:
    ordering = ('first_name', 'last_name')
    verbose_name = 'person'
    verbose_name_plural = 'people'

  def __str__(self):
    ''' Return the name of the person with year of birth and death '''
    name = self.full_name()
    if self.year_of_birth or self.year_of_death or self.moment_of_death_unconfirmed:
      name += f" ({ str(self.year_of_birth) if self.year_of_birth else ' ' }"
      if self.year_of_death or self.moment_of_death_unconfirmed:
        name += f" - { self.year_of_death if self.year_of_death else '?' }"
      name += f")"
    return name

  def name(self):
    return ' '.join([self.first_name, self.last_name])

  def full_name(self):
    call_sign = ''
    if self.first_name and  self.first_name not in self.given_names.split(' '):
      call_sign = '(' + self.first_name + ') '
    return ' '.join([call_sign, self.given_names, self.last_name, self.married_name]).strip()

  def ageatdeath(self):
    if self.date_of_birth and self.date_of_death:
      age = self.date_of_death.year - self.date_of_birth.year
      age -= ((self.date_of_birth.month, self.date_of_birth.day) <
         (self.date_of_birth.month, self.date_of_birth.day))
      return age
    elif self.year_of_birth and self.year_of_death:
      return self.year_of_death - self.year_of_birth

  ''' Family Relations
      There are two family relations stored:
      * A (up) is parent of B (down)
      * C is partner of D
      Brothers and sisters are calculated by havind a shared parent.
  '''

  ''' get_parents()
      Parents have a simple relation
      up is parent of down.
  '''
  def get_parents(self):
    if self.relation_up:
      parents = []
      for parent in self.relation_up.filter(type='parent').order_by('up__year_of_birth'):
        parents.append(parent.up)
      return parents

  ''' get_children()
      Childern have a simple relation
      down is child of parent up
  '''
  def get_children(self):
    if self.relation_down:
      children = []
      for child in self.relation_down.filter(type='parent').order_by('down__year_of_birth'):
        children.append(child.down)
      return children
  
  ''' get_partners()
      partners have a two-sided relation
      a is partner of b, or b is partner of a
  '''
  def get_partners(self):
    if self.relation_down:
      partners = []
      for child in self.relation_down.filter(type='parent'):
        for parent in child.down.relation_up.filter(type='parent'):
          if parent.up not in partners and parent.up != self:
            partners.append(parent.up)
      for partner in self.relation_up.filter(type='partner'):
        partners.append(partner.up)
      for partner in self.relation_down.filter(type='partner'):
        partners.append(partner.down)
      return partners

  ''' get_siblings
      siblings have a two-hop relation:
      for each parent, fetch children
  '''
  def get_siblings(self):
    if self.relation_up:
      siblings = []
      for parent in self.relation_up.filter(type='parent').order_by('up__year_of_birth'):
        for child in parent.up.relation_down.all():
          if child.down not in siblings and child.down != self:
            siblings.append(child.down)
      return siblings

  ''' Absulute URL
      should return URL with both name and slug
  '''
  def get_absolute_url(self):
    return reverse('archive:person', kwargs={'pk':self.id, 'name': self.slug})
  

  ''' Processing at save
  '''
  def save(self, *args, **kwargs):
    ''' First name:
        If no first name is given, but given names are mentioned, assume first given name is first-name.
    '''
    if self.given_names and not self.first_name:
      if ' ' in self.given_names:
        self.first_name = self.given_names.split()[1]
      else:
        self.first_name = self.given_names
    ''' Slug:
        Slug should always contain given names, last name and married name, but also 
        year of birth and -death.
        Make use of __str__() to get the correct fields
    '''
    self.slug = slugify(self.__str__().replace('(', '')).replace(')', '')
    ''' Related User:
        If a related user is set, copy user information to the related user
        and back
    '''
    if self.related_user and self.first_name:
      self.related_user.first_name = self.first_name
    if self.related_user and self.last_name:
      self.related_user.last_name = self.last_name
    if self.related_user and self.email:
      self.related_user.email = self.email
    if self.related_user:
      self.related_user.save()
    return super(Person, self).save(*args, **kwargs)


''' Family Relations
    Family Relations are stored by defining person A is relation of person B. Currently only relation
    parent or partner can be selected. 
    Children are calculated by fetching one's parents children
'''
class FamilyRelations(models.Model):
  RELATION_CHOICES = [
    ('parent', 'Parent'),
    ('partner', 'Partner'),
  ]
  up                  = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='relation_down')
  down                = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='relation_up')
  type                = models.CharField(choices=RELATION_CHOICES, max_length=16, default='parent')

  class Meta:
    unique_together = ('up', 'down', 'type', )

  def __str__(self):
    return str(self.up) + ' is ' + self.type + ' of ' + str(self.down)

