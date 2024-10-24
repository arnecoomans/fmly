
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView
from django.shortcuts import redirect, reverse
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.models import User
from django.conf import settings
from django.http import JsonResponse
from django.utils.html import strip_tags
import markdown

# from .snippets.a_helper import aHelper
# from .snippets.filter_class import FilterClass

from archive.models import Image
from archive.models.comment import Comment

md = markdown.Markdown(extensions=["fenced_code"])


class aListComments(ListView):
  model = Comment

  def get(self, request, *args, **kwargs):
    response = {
      'error': False,
      'object': {},
      'data': {
        'comments': []
      }
    }
    ''' Validate that user is logged in '''
    if not self.request.user.is_authenticated:
      response['error'] = True
      response['message'] = _('You need to be logged in to view comments')
      return JsonResponse(response)
    ''' Validate object '''
    object = self.getObject()
    if object == False:
      return JsonResponse({
        'error': True,
        'message': _('Object not found')
      })
    elif object:
      response['object'] = {
        'id': object.id,
        'title': object.title,
        'slug': object.slug,
        'url': object.get_absolute_url(),
      }
    for comment in self.getComments(object):
      rendered_content = "<li class=\"bi bi-chat-right-text\"><div class=\"comment\">" + \
                            f"<h4>{ comment.user.get_full_name() if comment.user.get_full_name() else comment.user }</h4>" + \
                            md.convert(strip_tags(comment.content))
      rendered_content += "</div></li>"
      response['data']['comments'].append({
        'id': comment.id, 
        'content': md.convert(strip_tags(comment.content)),
        'actions': {},
        'user': {
          'id': comment.user.id,
          'username': comment.user.username,
          'displayname': comment.user.get_full_name() if comment.user.get_full_name() else comment.user.username,
        },
        'date_created': comment.date_created,
      })
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
  

