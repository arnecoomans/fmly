from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView
 
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect, get_object_or_404
from django.template.defaultfilters import slugify
from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages
from django.utils.translation import gettext as _
from django.db.models import Prefetch
 
from pathlib import Path

from archive.models import Book, Collection, CollectionItem, Attachment

class BookListView(PermissionRequiredMixin, ListView):
  model = Book
  template_name = 'archive/book/book_list.html'
  context_object_name = 'books'
  permission_required = 'archive.view_book'

class BookDetailView(PermissionRequiredMixin, DetailView):
  model = Book
  template_name = 'archive/book/book_detail.html'
  context_object_name = 'book'
  permission_required = 'archive.view_book'

class BookCollectionListView(PermissionRequiredMixin, ListView):
  model = Collection
  template_name = 'archive/book/book_collection_list.html'
  context_object_name = 'collections'
  permission_required = 'archive.view_book'

class BookCollectionDetailView(PermissionRequiredMixin, DetailView):
  model = Collection
  template_name = 'archive/book/book_list.html'
  context_object_name = 'collection'
  permission_required = 'archive.view_book'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['books'] = Book.objects.filter(
      collection_items__collection=self.object
    ).prefetch_related(
      Prefetch(
        'collection_items',
        queryset=CollectionItem.objects.filter(collection=self.object),
        to_attr='collection_item'
      )
    )
    return context

class BookCreateView(PermissionRequiredMixin, CreateView):
  model = Book
  template_name = 'archive/book/book_form.html'
  fields = ['title', 'author', 'year', 'publisher', 'isbn', 'description', 'cover', 'tags', 'people', 'attachments']
  permission_required = 'archive.add_book'
 
  def form_valid(self, form):
    messages.success(self.request, _('Book added.'))
    return super().form_valid(form)
 
  def get_success_url(self):
    return reverse('archive:book_detail', kwargs={'pk': self.object.pk})
 
 
class BookUpdateView(PermissionRequiredMixin, UpdateView):
  model = Book
  template_name = 'archive/book/book_form.html'
  fields = ['title', 'author', 'year', 'publisher', 'isbn', 'description', 'cover', 'tags', 'people', 'attachments']
  context_object_name = 'book'
  permission_required = 'archive.change_book'
 
  def form_valid(self, form):
    messages.success(self.request, _('Book updated.'))
    return super().form_valid(form)
 
  def get_success_url(self):
    return reverse('archive:book_detail', kwargs={'pk': self.object.pk})
 
 
class BookCollectionCreateView(PermissionRequiredMixin, CreateView):
  model = Collection
  template_name = 'archive/book/book_collection_form.html'
  fields = ['name', 'description', 'user', 'people', 'tags']
  permission_required = 'archive.add_collection'
 
  def form_valid(self, form):
    if not form.instance.slug:
      form.instance.slug = slugify(form.instance.name)
    messages.success(self.request, _('Collection created.'))
    return super().form_valid(form)
 
  def get_success_url(self):
    return reverse('archive:book-collection-detail', kwargs={'slug': self.object.slug})
 
 
class BookCollectionUpdateView(PermissionRequiredMixin, UpdateView):
  model = Collection
  template_name = 'archive/book/book_collection_form.html'
  context_object_name = 'collection'
  fields = ['name', 'description', 'user', 'people', 'tags']
  permission_required = 'archive.change_collection'
 
  def form_valid(self, form):
    messages.success(self.request, _('Collection updated.'))
    return super().form_valid(form)
 
  def get_success_url(self):
    return reverse('archive:book-collection-detail', kwargs={'slug': self.object.slug})
 
 
class CollectionItemCreateView(PermissionRequiredMixin, CreateView):
  '''Add an existing Book to a Collection (URL carries the collection slug).'''
  model = CollectionItem
  template_name = 'archive/book/collection_item_form.html'
  fields = ['book', 'read_on', 'notes', 'tags']
  permission_required = 'archive.add_collectionitem'
 
  def dispatch(self, request, *args, **kwargs):
    self.collection = get_object_or_404(Collection, slug=kwargs['slug'])
    return super().dispatch(request, *args, **kwargs)
 
  def get_form(self, form_class=None):
    form = super().get_form(form_class)
    # keep the picker limited to books not already in this collection
    form.fields['book'].queryset = Book.objects.exclude(collection_items__collection=self.collection)
    return form
 
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['collection'] = self.collection
    return context
 
  def form_valid(self, form):
    form.instance.collection = self.collection
    messages.success(self.request, _('Book added to collection.'))
    return super().form_valid(form)
 
  def get_success_url(self):
    return reverse('archive:book-collection-detail', kwargs={'slug': self.collection.slug})
 
 
class CollectionItemUpdateView(PermissionRequiredMixin, UpdateView):
  model = CollectionItem
  template_name = 'archive/book/collection_item_form.html'
  context_object_name = 'item'
  fields = ['read_on', 'notes', 'tags']
  permission_required = 'archive.change_collectionitem'
 
  def form_valid(self, form):
    messages.success(self.request, _('Collection item updated.'))
    return super().form_valid(form)
 
  def get_success_url(self):
    return reverse('archive:book-collection-detail', kwargs={'slug': self.object.collection.slug})