from django.views.generic import View
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from django.template.loader import render_to_string

from django.db.models import QuerySet

class JsonHelper(View):
  def __init__(self):
    self.response = {}
    self.messages = []
    self.object = None
    self.status = 200
  
  def get(self, request, *args, **kwargs):
    ''' Set Scope '''
    self.scope = self.request.resolver_match.url_name.replace('json-get-attribute-of-', '')
    ''' Fetch Object '''
    self.object = self.get_object()
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
  

  def get_query_element(self, key):
    if key in self.kwargs:
      return self.kwargs[key]
    elif self.request.GET.get(key, False):
      return self.request.GET.get(key)
    elif self.request.POST.get(key, False):
      return self.request.POST.get(key)
    else:
      return False
    

  def add_message(self, type, message):
    if type == 'error':
      type = 'danger'
      self.status = 400
    self.messages.append({'type': type, 'message': message})

  def get_attribute(self):
    attribute = self.get_query_element('attribute')
    ''' Attribute Aliasses '''
    if attribute == 'person':
      attribute = 'people'
    ''' Check if the attribute is set '''
    if not attribute:
      self.add_message('error', 'Attribute not found')
      return False
    ''' Protected Attributes '''
    if attribute in ['slug', 'source', 'thumbnail', 'is_deleted']:
      self.add_message('error', f'Attribute { attribute } not allowed')
      return False
    ''' Verify Object has the Attribute '''
    if not hasattr(self.object, attribute):
      self.add_message('error', f'Attribute { attribute } not found')
      return False
    return attribute
  
  ''' PAYLOAD HANDLING '''
  def add_payload(self, value):
    payload = []
    if isinstance(value, QuerySet):
      for item in value:
        payload.append(self.get_rendered_payload(item))
    elif isinstance(value, str):
      payload.append(self.get_rendered_payload(value))
    else:
      payload.append(self.get_rendered_payload(value))
    if self.request.user.is_staff:
      self.response['value'] = str(value)
      self.response['type'] = str(type(value))
    self.payload = payload

  def get_rendered_payload(self, value):
    try:
      return render_to_string('partial/' + self.scope + '/' + self.attribute + '.html', { self.attribute: value })
    except Exception as e:
      ''' Exception Handling'''
      if self.attribute == 'people':
        return render_to_string('partial/' + self.scope + '/person.html', { 'person': value })
      ''' Logging'''
      if self.request.user.is_staff:
        self.add_message('warning', 'Could not render ' + self.attribute + ' for ' + str(value) + ': ' + str(e))
      ''' Fall back to string representation letting the model define the representation '''
      return str(value)

  def return_response(self):
    self.response['__meta'] = {
      'url': self.request.path,
      'resolver': self.request.resolver_match.url_name,
      'user': self.request.user.username if self.request.user.is_authenticated else False,
      'scope': self.scope
    }
    self.response['status'] = self.status
    self.response['messages'] = self.messages
    ''' Add object to response '''
    if hasattr(self, 'object') and self.object:
      self.response['object'] = {
        'id': self.object.pk,
        'name': str(self.object),
        'slug': self.object.slug,
        'url': self.object.get_absolute_url(),
      }
      if hasattr(self, 'attribute') and self.attribute:
        self.response['object']['attribute'] = self.attribute
    ''' Add payload to response '''
    if hasattr(self, 'payload') and self.payload:
      self.response['payload'] = self.payload
    return JsonResponse(self.response, status=self.status)