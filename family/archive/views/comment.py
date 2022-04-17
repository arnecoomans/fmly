from re import template
from django.views import generic
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormView
from django.shortcuts import get_object_or_404

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from archive.models import Comment, Image, Person

# Renamed CommentsView to CommentListView
class CommentListView(generic.ListView):
  model = Comment
  context_object_name = 'comments'
  template_name = 'comment/comment_list.html'
  paginate_by = 12

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['page_scope'] = 'Reacties op foto\'s'
    context['page_description'] = 'Om een reactie te plaatsen, open de foto en plaats je reactie.'
    return context
  
  def get_queryset(self):      
    return Comment.objects.order_by('-date_modified')


# Renamed CommentView to AddCommentView
class AddCommentView(PermissionRequiredMixin, CreateView):
  permission_required = 'archive.add_comment'
  model = Comment
  fields = ['content']

  def form_valid(self, form):
    # Set user to logged in user
    form.instance.user = self.request.user
    # Set image to image from URL
    form.instance.image = Image.objects.get(pk=self.kwargs['pk'])
    return super().form_valid(form)

class EditCommentView(PermissionRequiredMixin, UpdateView):
  permission_required = 'archive.change_comment'
  model = Comment
  fields = ['content']
  template_name = 'comment/comment_form.html'

# Renamed MyCommentList to CommentListByUserView
class CommentListByUserView(generic.ListView):
  model = Comment
  context_object_name = 'comments'
  paginate_by = 24
  template_name = 'comment/comment_list.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['page_scope'] = 'Mijn reacties'
    return context

  def get_queryset(self):
    # If a username is supplied, use username as search key
    if 'username' in  self.kwargs:
      person = get_object_or_404(Person, related_user__username=self.kwargs['username'])
      user = person.related_user if person else None
    # If no username is supplied, assume current logged in user
    else:
      user = self.request.user
    return Comment.objects.filter(user=user).order_by('-date_modified')
