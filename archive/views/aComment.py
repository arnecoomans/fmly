
from django.views.generic.list import ListView
from django.template.loader import render_to_string

from django.utils.translation import gettext as _
from django.contrib.auth.models import User
from django.http import JsonResponse

# from .snippets.a_helper import aHelper
# from .snippets.filter_class import FilterClass

from archive.models import Image
from archive.models.comment import Comment

class aListComments(ListView):
  model = Comment

  def get(self, request, *args, **kwargs):
    response = {
      'error': False,
      'message': '',
      'object': {},
      'payload': [],
    }
    ''' Validate that user is logged in '''
    if not self.request.user.is_authenticated:
      response['error'] = True
      response['message'] = _('you need to be logged in to view comments').capitalize()
      return JsonResponse(response)
    ''' Validate object '''
    object = self.getObject()
    if object == False:
      return JsonResponse({
        'error': True,
        'message': _('object not found').capitalize(),
      })
    elif object:
      response['object'] = {
        'id': object.id,
        'title': object.title,
        'slug': object.slug,
        'url': object.get_absolute_url(),
      }
    for comment in self.getComments(object):
      response['payload'].append(render_to_string('archive/partial/comment.html', {'comment': comment}))
    return JsonResponse(response)
  
  def getObject(self):
    try:
      object = Image.objects.get(pk=self.kwargs['pk'], slug=self.kwargs['slug'])
    except KeyError:
      object = None
    except Image.DoesNotExist:
      object = False
    return object
  
  def getComments(self, object):
    ''' Fetch all not deleted comments '''
    comments = Comment.objects.all().exclude(is_deleted=True)
    ''' Process filters: ger comments for object '''
    if 'pk' in self.kwargs and 'slug' in self.kwargs:
      comments = comments.filter(image=self.getObject())
    ''' Process filters: get comments for user '''
    if self.request.GET.get('user', False):
      comments = comments.filter(user=User.objects.get(username=self.request.GET.get('user')))
    ''' Order comments by date_modified '''
    order = 'date_modified' if self.request.GET.get('o', False) == '-' else '-date_modified'
    ''' Return comments '''
    comments = comments.order_by(order).distinct()
    return comments
  

