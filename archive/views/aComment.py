
from django.views.generic import DetailView, ListView, TemplateView
from django.template.loader import render_to_string
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db.utils import IntegrityError
from django.conf import settings

from archive.models import Image
from archive.models.comment import Comment

''' List comments by date added newest first 
    This view returns a list of comments sorted by date added.
    When a specific image is mentioned in the URL, only comments for that image are returned.
    When a specific user is mentioned in the URL, only comments by that user are returned.
    When no filters are mentioned, all comments are returned.
    @Todo: Add pagination
'''
class aListComments(ListView):
  model = Comment

  def get(self, request, *args, **kwargs):
    response = {
      'error': False,
      'message': '',
      'object': {},
      'payload': [],
    }
    ''' Show thumbnail in comments should be se to
        False when comments are rendered for a specific object
        else True
    '''
    show_thumbnail = True
    ''' Validate that user is logged in '''
    if not self.request.user.is_authenticated:
      response['error'] = True
      response['message'] = _('you need to be logged in to view comments').capitalize()
      return JsonResponse(response)
    ''' Validate object if object is mentioned in URL '''
    object = self.getObject()
    if object == False:
      ''' Object is mentioned in URL but not found '''
      return JsonResponse({
        'error': True,
        'message': _('object not found').capitalize(),
      })
    elif object:
      ''' Add object details to response '''
      response['object'] = {
        'id': object.id,
        'title': object.title,
        'slug': object.slug,
        'url': object.get_absolute_url(),
        'comment_count': object.count_comments(),
      }
      show_thumbnail = False
    ''' Render comments 
        Add all rendered comments to payload
    '''
    comments = self.getComments(object)
    if comments == False:
      return JsonResponse({
        'error': True,
        'message': _('comments cannot be loaded').capitalize(),
      })
    if object and object.count_comments() > 0:
      response['payload'].append(render_to_string('archive/partial/commentcounter.html', {'image': object, }))
    for comment in comments:
      response['payload'].append(render_to_string('archive/partial/comment.html', {'comment': comment, 'show_thumbnail': show_thumbnail, 'user':self.request.user }))
    ''' Return response '''
    return JsonResponse(response)
  
  ''' Fetch object information
      Returns the object if id and slug are mentioned in URL
      Returns False if object is mentioned in URL but not found
      Returns None if object is not mentioned in URL
  '''
  def getObject(self):
    try:
      object = Image.objects.get(pk=self.kwargs['pk'], slug=self.kwargs['slug'])
    except KeyError:
      object = None
    except Image.DoesNotExist:
      object = False
    return object
  
  ''' Fetch comments
      Returns all not-deleted comments
      Filters comments by object if object is mentioned in URL
      Filters comments by user if user is mentioned in URL query parameter
  '''
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
      try:
        user = User.objects.get(username__iexact=self.request.GET.get('user'))
        comments = comments.filter(user=user)
      except User.DoesNotExist:
        return False
    ''' Order comments by date_modified '''
    order = 'date_modified' if self.request.GET.get('o', False) == '-' else '-date_modified'
    ''' Return comments '''
    comments = comments.order_by(order).distinct()
    return comments
  
''' Fetch comment form 
    This view returns a rendered comment form for the image to inject
    into the image detail page via ajax request
'''
class aFetchCommentForm(TemplateView):
  
  def get(self, *args, **kwargs):
    response = {
      'error': False,
      'message': '',
      'payload': render_to_string('archive/partial/commentform.html', {'image': Image.objects.get(pk=self.kwargs['pk'], slug=self.kwargs['slug'])}),
    }
    ''' Validate that user is logged in '''
    return JsonResponse(response)


''' Post comment
    This view allows users to post comments to images via ajax request.
'''
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
    if not self.request.user.has_perm('archive.add_comment'):
      response['error'] = True
      response['message'] = _('you are not allowed to comment').capitalize()
      return JsonResponse
    ''' Validate object '''
    try:
      object = Image.objects.get(pk=self.kwargs['pk'], slug=self.kwargs['slug'])
    except Image.DoesNotExist:
      response['error'] = True
      response['message'] = _('object not found').capitalize()
      return JsonResponse(response)
    ''' Validate comment - cannot be empty '''
    comment = self.request.POST.get('comment', False)
    if not comment:
      response['error'] = True
      response['message'] = _('comment cannot be empty').capitalize()
      return JsonResponse(response)
    comment = comment.strip()
    ''' Comments should have a minimum length in characters, so exclude space from check '''
    if len(comment.replace(' ', '')) < getattr(settings, 'MIN_COMMENT_LENGTH', 5):
      response['error'] = True
      response['message'] = _('comment is too short').capitalize()
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