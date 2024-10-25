
from django.views.generic import DetailView, ListView, TemplateView
from django.template.loader import render_to_string
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db.utils import IntegrityError

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
    show_thumbnail = False if 'pk' in self.kwargs and 'slug' in self.kwargs else True
    ''' Render comments '''
    for comment in self.getComments(object):
      response['payload'].append(render_to_string('archive/partial/comment.html', {'comment': comment, 'show_thumbnail': show_thumbnail}))
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
    ''' Process filters: get comments for object 
        If no PK or SLUG in url kwargs, return all comments
    '''
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
  
class aFetchCommentForm(TemplateView):
  # template_name = 'archive/partial/comment_form.html'
  
  def get(self, *args, **kwargs):
    response = {
      'error': False,
      'message': '',
      'payload': render_to_string('archive/partial/commentform.html', {'image': Image.objects.get(pk=self.kwargs['pk'], slug=self.kwargs['slug'])}),
    }
    ''' Validate that user is logged in '''
    return JsonResponse(response)

class aPostComment(TemplateView):
  template_name = 'archive/partial/comment.html'

  def get(self, *args, **kwargs):
    messages.add_message(self.request, messages.ERROR, _('You are not allowed to access this page directly.').capitalize())
    if 'slug' in self.kwargs:
      return redirect('archive:image', slug=self.kwargs['slug'])
    return redirect('archive:home')
     
  def post(self, *args, **kwargs):
    response = {
      'error': False,
      'message': '',
      'payload': '',
    }
    ''' Validate that user is logged in '''
    if not self.request.user.is_authenticated:
      response['error'] = True
      response['message'] = _('you need to be logged in to comment').capitalize()
      return JsonResponse(response)
    ''' Validate object '''
    try:
      object = Image.objects.get(pk=self.kwargs['pk'], slug=self.kwargs['slug'])
    except Image.DoesNotExist:
      response['error'] = True
      response['message'] = _('object not found').capitalize()
      return JsonResponse(response)
    ''' Validate comment '''
    if not self.request.POST.get('comment', False):
      response['error'] = True
      response['message'] = _('comment cannot be empty').capitalize()
      return JsonResponse(response)
    ''' Create comment '''
    try:
      comment = Comment(
        user=self.request.user,
        image=object,
        content=self.request.POST.get('comment'),
      )
      comment.save()
    except IntegrityError:
      response['error'] = True
      response['message'] = _('you have already posted this comment').capitalize()
      return JsonResponse(response)
    return JsonResponse(response)