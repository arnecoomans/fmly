from django.db import models
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.urls import reverse_lazy, reverse
from math import floor
from django.utils.translation import gettext_lazy as _


class Person(models.Model):
  ''' Model: Person
      People are:
      - tagged on an image
      - related to another person
  '''
  first_names         = models.CharField(max_length=255, blank=True, verbose_name='Voornamen', help_text='Alle voornamen, inclusief roepnaam')
  given_name          = models.CharField(max_length=255, blank=True, verbose_name='Roepnaam', help_text='Indien afwijkend van eerste voornaam')
  last_name           = models.CharField(max_length=255, blank=True, verbose_name='Achternaam', help_text='Achternaam bij geboorte')
  married_name        = models.CharField(max_length=255, blank=True, verbose_name='Getrouwde Achternaam', help_text='Achternaam van echtgeno(o)t(e)')

  nickname            = models.CharField(max_length=255, blank=True, verbose_name='Bijnaam')
  email               = models.EmailField(blank=True, help_text='Dit veld is alleen zichtbaar voor jou en voor de site-beheerder(s). Vul je e-mailadres in zodat we je een wachtwoord-reset email kunnen sturen als je niet langer kan inloggen.')
  slug                = models.CharField(max_length=255, unique=True)
  
  # Gender (required for family tree)
  GENDERS             = [('m', _('male')), ('f', _('female')), ('x', _('not stored'))]
  gender              = models.CharField(max_length=1, choices=GENDERS, default='x')
  
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
  private             = models.BooleanField(default=False, help_text="Private Mode limits the information being shared")
  related_user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='related_person')
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  date_modified       = models.DateTimeField(auto_now=True)
  date_created        = models.DateTimeField(auto_now_add=True)
  

  # Model configuration for JSON API
  allow_read_attribute = 'Authenticated'  # Allow authenticated users to read attributes via JSON requests
  allow_suggest_attribute = 'Authenticated'  # Allow authenticated users to suggest attributes via JSON requests
  allow_set_attribute = 'Staff'  # Allow staff users to set attributes via JSON requests
  allow_create_attribute = False # Disallow creating new objects via JSON requests by setting to False
  searchable_fields = ['first_names', 'given_name', 'last_name', 'married_name', 'nickname', 'place_of_birth', 'place_of_death', 'bio']

  allow_read_attribute = 'Authenticated'  # Allow authenticated users to read attributes via JSON requests
  allow_suggest_attribute = 'Authenticated'  # Allow authenticated users to suggest attributes via JSON requests
  allow_set_attribute = 'Staff'  # Allow staff users to set attributes via JSON requests
  allow_create_attribute = True # Disallow creating new objects via JSON requests by setting to False
  
  class Meta:
    ordering = ('first_names', 'last_name')
    verbose_name = 'person'
    verbose_name_plural = 'people'

  def __str__(self):
    ''' Return the name of the person with year of birth and death '''
    name = self.full_name()
    if len(self.get_lifespan()) > 0:
      name += f" ({ self.get_lifespan() })"
    return name

  def name(self):
    return ' '.join([self.first_names, self.last_name])

  def full_name(self):
    if self.private:
      return ' '.join([self.first_names, self.last_name]).strip()
    else:
      value = self.first_names
      if self.given_name:
        value += f" ({ self.given_name})"
      if self.married_name:
        value += f" { self.married_name } - { self.last_name }"
      else:
        value += f" { self.last_name }"
      return value.strip()
    

  def century(self):
    if self.year_of_birth:
      return floor(self.year_of_birth/100)*100
  def decade(self):
    if self.year_of_birth:
      return floor(self.year_of_birth/10)*10
  
  def get_lifespan(self):
    lifespan = ''
    if self.year_of_birth:
      lifespan += str(self.year_of_birth)
    if self.year_of_death or self.moment_of_death_unconfirmed:
      lifespan += ' - '
    if self.year_of_death:
      lifespan += str(self.year_of_death)
    return lifespan

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
  def get_parents(self, person=None):
    if not person:
      person = self
    if person.relation_up:
      parents = []
      for parent in person.relation_up.filter(type='parent').order_by('up__year_of_birth'):
        parents.append(parent.up)
      return parents
  def get_father(self):
    if self.relation_up:
      for parent in self.relation_up.filter(type='parent', up__gender='m').order_by('up__year_of_birth'):
        return parent.up
  def get_mother(self):
    if self.relation_up:
      for parent in self.relation_up.filter(type='parent', up__gender='f').order_by('up__year_of_birth'):
        return parent.up
  
  ''' get_children()
      Childern have a simple relation
      down is child of parent up
  '''
  def get_children(self, person=None):
    if not person:
      person = self
    if person.relation_down:
      children = []
      for child in person.relation_down.filter(type='parent').order_by('down__year_of_birth'):
        children.append(child.down)
      return children
  
  ''' get_partners()
      partners have a two-sided relation
      a is partner of b, or b is partner of a
  '''
  def get_partners(self, person=None):
    if not person:
      person = self
    if person.relation_down:
      partners = []
      ''' Partner is the other parent of a child '''
      for child in self.get_children():
        for parent in self.get_parents(child):
          if parent not in partners and parent != person:
            partners.append(parent)
      ''' Partner is also found by relation type=partner '''
      for partner in person.relation_up.filter(type='partner'):
        if partner.up not in partners:
          partners.append(partner.up)
      for partner in person.relation_down.filter(type='partner'):
        if partner.down not in partners:
          partners.append(partner.down)
      return partners

  ''' get_siblings
      siblings have a two-hop relation:
      for each parent, fetch children
  '''
  def get_siblings(self, person=None):
    if not person:
      person = self
    if person.relation_up:
      siblings = []
      for parent in self.get_parents():
        for child in self.get_children(parent):
          if child not in siblings and child != person:
            siblings.append(child)
      return siblings

  ''' Absulute URL
      should return URL with both name and slug
  '''
  def get_absolute_url(self):
    return reverse_lazy('archive:person', kwargs={'pk':self.id, 'name': self.slug})
  

  ''' Processing at save
  '''
  def save(self, *args, **kwargs):
    # ''' First name:
    #     If no first name is given, but given names are mentioned, assume first given name is first-name.
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
    if self.related_user and self.first_names:
      self.related_user.first_names = self.first_names
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

