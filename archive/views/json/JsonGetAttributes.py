from django.views.generic import View
from django.http import JsonResponse

from .JsonHelper import JsonHelper
from ...models import Image

class GetAttribute:
  def __init__(self, object, attribute):
    self.object = object
    self.attribute = attribute


class JsonGetAttributeOfImage(JsonHelper):
  def get(self, request, *args, **kwargs):
    ''' Get the Object 
        Try to get the object by pk, if not found try to get by slug
        If the object is not found, return an error message
    '''
    try:
      self.object = Image.objects.get(pk=kwargs['pk']) if 'pk' in kwargs else Image.objects.get(slug=kwargs['slug'])
    except Image.DoesNotExist:
      self.add_message('error', 'Image not found')
      return self.return_response()
    ''' If the object is deleted, return an error message '''
    if self.object.is_deleted:
      self.add_message('error', 'Image is deleted')
      return self.return_response
    ''' Fetch the Attribute Name
        The attribute name is the key to the value we want to retrieve
    '''
    self.attribute = self.get_attribute()
    if not self.attribute:
      return self.return_response()
    ''' Get the Value of the Attribute '''
    value = getattr(self.object, self.attribute)
    value = value.all() if hasattr(value, 'all') else value
    ''' Add the Value to the Response '''
    self.add_payload(value)
    return self.return_response()