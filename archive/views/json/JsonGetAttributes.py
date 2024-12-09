from django.views.generic import View
from django.http import JsonResponse

from .JsonHelper import JsonHelper
from ...models import Image, Person

class GetAttribute:
  def __init__(self, object, attribute):
    self.object = object
    self.attribute = attribute


class JsonGetAttributeOfImage(JsonHelper):
  def get_object(self):
    ''' Get the Object 
        Try to get the object by pk, if not found try to get by slug
        If the object is not found, return an error message
    '''
    try:
      object = Image.objects.get(pk=self.kwargs['pk']) if 'pk' in self.kwargs else Image.objects.get(slug=self.kwargs['slug'])
    except Image.DoesNotExist:
      self.add_message('error', 'Image not found')
      return False
    ''' If the object is deleted, return an error message '''
    if object.is_deleted:
      self.add_message('error', 'Image is deleted')
      return False
    return object
  
  

class JsonGetAttributeOfPerson(JsonHelper):
  def get_object(self):
    ''' Get the Object 
        Try to get the object by pk, if not found try to get by slug
        If the object is not found, return an error message
    '''
    try:
      object = Person.objects.get(pk=self.kwargs['pk']) if 'pk' in self.kwargs else Person.objects.get(slug=self.kwargs['slug'])
    except Person.DoesNotExist:
      self.add_message('error', 'Person not found')
      return False
    return object
  