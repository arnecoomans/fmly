from re import template
from django.views import generic
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormView
from django.shortcuts import redirect
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.template.defaultfilters import slugify

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from archive.models import Comment, Image, Person

# Renamed CommentsView to CommentListView
class CommentListView(generic.ListView):
  model = Comment
  template_name = 'archive/comments/list.html'
  paginate_by = settings.PAGINATE

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['page_scope'] = 'Reacties op foto\'s'
    context['page_description'] = 'Om een reactie te plaatsen, open de foto en plaats je reactie.'
    return context
  
  def get_queryset(self):      
    queryset = Comment.objects.filter(is_deleted=False).order_by('-date_modified')
    return queryset

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
    messages.add_message(self.request, messages.SUCCESS, f"Reactie toegevoegd aan \"{form.instance.image.title}\"")
    return super().form_valid(form)

class EditCommentView(PermissionRequiredMixin, UpdateView):
  permission_required = 'archive.change_comment'
  model = Comment
  fields = ['content']
  template_name = 'comment/comment_form.html'

class CommentDeleteView(PermissionRequiredMixin, generic.DetailView):
  permission_required = 'archive.change_comment'
  model = Comment
  
  def get_comment_preview(self, comment):
    comment = comment.content.split(' ')
    if len(comment) > 6:
      comment = comment[:6]
      comment.append('...')
    return ' '.join(comment)
    
  def get(self, request, *args, **kwargs):
    comment = Comment.objects.get(pk=self.kwargs['pk'])
    if self.request.user.is_staff or self.request.user == comment.user:
      comment.is_deleted = True
      messages.add_message(self.request, messages.SUCCESS, f"Reactie \"{ self.get_comment_preview(comment) }\" op \"{comment.image.title}\" verwijderd. <a href=\"{reverse('archive:undelete-comment', args=[comment.id])}\">Ongedaan maken</a>.")
    else:
      messages.add_message(self.request, messages.ERROR, f"Reactie \"{ self.get_comment_preview(comment) }\" op \"{comment.image.title}\" kan niet worden verwijderd. Is het wel jouw reactie?")
    comment.save()
    return redirect('archive:image', comment.image.id, slugify(comment.image.title))

class CommentUnDeleteView(PermissionRequiredMixin, generic.DetailView):
  permission_required = 'archive.change_comment'
  model = Comment
  
  def get_comment_preview(self, comment):
    comment = comment.content.split(' ')
    if len(comment) > 6:
      comment = comment[:6]
      comment.append('...')
    return ' '.join(comment)
    
  def get(self, request, *args, **kwargs):
    comment = Comment.objects.get(pk=self.kwargs['pk'])
    if self.request.user.is_staff or self.request.user == comment.user:
      comment.is_deleted = False
      messages.add_message(self.request, messages.SUCCESS, f"Reactie \"{ self.get_comment_preview(comment) }\" op \"{comment.image.title}\" hersteld.")
    else:
      messages.add_message(self.request, messages.ERROR, f"Reactie \"{ self.get_comment_preview(comment) }\" op \"{comment.image.title}\" kan niet worden hersteld. Is het wel jouw reactie?")
    comment.save()
    return redirect('archive:image', comment.image.id, slugify(comment.image.title))


# # Renamed MyCommentList to CommentListByUserView
# class CommentListByUserView(generic.ListView):
#   model = Comment
#   context_object_name = 'comments'
#   paginate_by = 24
#   template_name = 'comment/comment_list.html'

#   def get_context_data(self, **kwargs):
#     context = super().get_context_data(**kwargs)
#     context['page_scope'] = 'Mijn reacties'
#     return context

#   def get_queryset(self):
#     # If a username is supplied, use username as search key
#     if 'username' in  self.kwargs:
#       person = get_object_or_404(Person, related_user__username=self.kwargs['username'])
#       user = person.related_user if person else None
#     # If no username is supplied, assume current logged in user
#     else:
#       user = self.request.user
#     return Comment.objects.filter(user=user).order_by('-date_modified')
