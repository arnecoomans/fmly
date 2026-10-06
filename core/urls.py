from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
  path('search/', views.SearchView.as_view(), name='search'),
  path('preferences/', views.PreferencesView.as_view(), name='preferences'),
  path('comments/', views.CommentListView.as_view(), name='comment_list'),
  path('tags/', views.TagListView.as_view(), name='tag_list'),
  # A tag's page: the token finds it (slugs are only unique per parent),
  # the slug is for reading; token-only / outdated slugs redirect.
  path('tags/<str:token>/<slug:slug>/', views.TagDetailView.as_view(), name='tag_detail'),
  path('tags/<str:token>/', views.TagDetailView.as_view(), name='tag_detail_by_token'),
]
