from django.views.generic import DetailView, ListView, TemplateView
from django.views.generic.edit import CreateView, UpdateView
from django.shortcuts import redirect
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.utils.translation import gettext as _

from django.contrib.auth.mixins import PermissionRequiredMixin

from archive.models import Comment, Image

from cmnsd.views.cmnsd_filter import FilterMixin

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
class CommentListView(FilterMixin, ListView):
  model = Comment
  template_name = 'archive/comments/list.html'

  # paginate_by = settings.PAGINATE

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'comments'
    context['page_scope'] = f"{ _('Comments on photos') }."
    context['page_description'] = f"{ _('To add a comment, first open the photo') }."
    return context
  
  def get_queryset(self):
    queryset = Comment.objects.all()
    queryset = self.filter(queryset, self.request)
    queryset = queryset.order_by('-date_modified').distinct()
    return queryset