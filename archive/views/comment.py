from django.views import generic
from django.views.generic.edit import CreateView, UpdateView
from django.shortcuts import redirect
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.template.defaultfilters import slugify

from django.contrib.auth.mixins import PermissionRequiredMixin

from archive.models import Comment, Image

''' Shared View Functions'''

''' Comment Change is Allowed:
    Returns true if user is comment.user or user is staff.
'''
def change_is_allowed(user, comment):
  ''' Only allow action from Comment User or Staff'''
  if user.is_staff or user == comment.user:
    return True
  return False

''' Comment preview
    Returns the first six words of the comment, followed by three dots if the comment has been cut off.
'''
def get_comment_preview(comment):
  comment = comment.content.split(' ')
  if len(comment) > 7:
    comment = comment[:6]
    comment.append('...')
  return ' '.join(comment)

''' List comments by date added newest first '''
class CommentListView(generic.ListView):
  model = Comment
  template_name = 'archive/comments/list.html'
  paginate_by = settings.PAGINATE

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'comments'
    context['page_scope'] = 'Reacties op foto\'s'
    context['page_description'] = 'Om een reactie te plaatsen, open de foto en plaats je reactie.'
    return context
  
  def get_queryset(self):
    queryset = Comment.objects.all()
    ''' Remove deleted_comments '''
    queryset = queryset.filter(is_deleted=False)
    ''' Filter comments by user '''
    if self.request.GET.get('user'):
      queryset = queryset.filter(user__username=self.request.GET.get('user'))
    ''' Free text search 
        Search Comment text, image title or user
    '''
    if self.request.GET.get('search'):
      search_text = self.request.GET.get('search').lower()
      queryset = queryset.filter(content__icontains=search_text) | \
                 queryset.filter(image__title__icontains=search_text) | \
                 queryset.filter(user__username__icontains=search_text) | \
                 queryset.filter(user__first_name__icontains=search_text) | \
                 queryset.filter(user__last_name__icontains=search_text)
    '''  and add ordering'''
    queryset = queryset.order_by('-date_modified')
    return queryset

''' Add Comment '''
class AddCommentView(PermissionRequiredMixin, CreateView):
  permission_required = 'archive.add_comment'
  model = Comment
  fields = ['content']

  def form_valid(self, form):
    ''' Force comment user to be logged in user '''
    form.instance.user = self.request.user
    ''' Link Image Instance to comment '''
    form.instance.image = Image.objects.get(pk=self.kwargs['pk'])
    messages.add_message(self.request, messages.SUCCESS, f"Reactie toegevoegd aan \"{form.instance.image.title}\"")
    return super().form_valid(form)

''' Edit Comment '''
class CommentEditView(PermissionRequiredMixin, UpdateView):
  permission_required = 'archive.change_comment'
  template_name = 'archive/comments/edit.html'
  model = Comment
  fields = ['content']

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'comments'
    return context

  def form_valid(self, form):
    ''' Fetch stored comment to track differences '''
    comment = Comment.objects.get(pk=self.kwargs['pk'])
    ''' Check if comment is being edited by comment's user. If not, 
        produce an errormessage '''
    if self.request.user != comment.user:
      form.instance.user = comment.user
      messages.add_message(self.request, messages.WARNING, f"Reactie op \"{form.instance.image.title}\" kan niet worden bewerkt: de gebruiker kan niet worden aan")
      return False
    ''' Only store comment if changes have been made. If not, keep orignial modified_data '''
    if len(form.changed_data) > 0:
      messages.add_message(self.request, messages.SUCCESS, f"Wijzigingen opgeslagen.")
      return super().form_valid(form)
    else:
      messages.add_message(self.request, messages.WARNING, f"Geen wijzigingen opgegeven.")
      return redirect(reverse('archive:image', args=[form.instance.image.id, slugify(form.instance.image.title)]))


''' Delete Comment '''
class CommentDeleteView(PermissionRequiredMixin, generic.DetailView):
  permission_required = 'archive.change_comment'
  model = Comment
    
  def get(self, request, *args, **kwargs):
    comment = Comment.objects.get(pk=self.kwargs['pk'])
    ''' Only allow action from Comment User or Staff'''
    if change_is_allowed(self.request.user, comment):
      ''' Mark comment as deleted '''
      comment.is_deleted = True
      messages.add_message(self.request, messages.SUCCESS, f"Reactie \"{ get_comment_preview(comment) }\" op \"{comment.image.title}\" verwijderd. <a href=\"{reverse('archive:undelete-comment', args=[comment.id])}\">Ongedaan maken</a>.")
    else:
      ''' Share errormessage that the comment cannot be modified '''
      messages.add_message(self.request, messages.ERROR, f"Reactie \"{ get_comment_preview(comment) }\" op \"{comment.image.title}\" kan niet worden verwijderd. Is het wel jouw reactie?")
    comment.save()
    ''' Redirect to image, also listing comments '''
    return redirect('archive:image', comment.image.id, slugify(comment.image.title))

''' Comment Undelete
    When deleting a comment, the undo-option is available. 
'''
class CommentUnDeleteView(PermissionRequiredMixin, generic.DetailView):
  permission_required = 'archive.change_comment'
  model = Comment
  
  def get(self, request, *args, **kwargs):
    comment = Comment.objects.get(pk=self.kwargs['pk'])
    ''' Only allow action from Comment User or Staff'''
    if change_is_allowed(self.request.user, comment):
      ''' Mark comment as restored'''
      comment.is_deleted = False
      messages.add_message(self.request, messages.SUCCESS, f"Reactie \"{ get_comment_preview(comment) }\" op \"{comment.image.title}\" hersteld.")
    else:
      ''' Share errormessage that the comment cannot be modified '''
      messages.add_message(self.request, messages.ERROR, f"Reactie \"{ get_comment_preview(comment) }\" op \"{comment.image.title}\" kan niet worden hersteld. Is het wel jouw reactie?")
    comment.save()
    return redirect('archive:image', comment.image.id, slugify(comment.image.title))