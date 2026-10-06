from django.urls import path

from . import views

app_name = 'content'

urlpatterns = [
  path('', views.ContentListView.as_view(), name='list'),
  # Adding content: the dropzone, its per-file upload, the drafts' inbox -
  # before the token URLs ('new', 'inbox' are never tokens: those are
  # 10+ characters).
  path('new/', views.UploadView.as_view(), name='upload'),
  path('new/upload/', views.content_upload, name='upload_file'),
  path('inbox/', views.InboxView.as_view(), name='inbox'),
  path('inbox/group/', views.inbox_group, name='inbox_group'),
  # File URLs first: at the same position as the slug below, and never
  # shadowed by it (Content.reserved_slugs keeps slugs off these words).
  path('<str:token>/file/', views.content_file, name='file'),
  path('<str:token>/thumb/<slug:preset>/', views.content_thumbnail, name='thumbnail'),
  path('<str:token>/portrait/<str:person_token>/', views.portrait_thumbnail, name='portrait'),
  path('<str:token>/transcribe/', views.TranscribeView.as_view(), name='transcribe'),
  path('<str:token>/transcribe/guess/', views.transcribe_guess, name='transcribe_guess'),
  # The page: the token finds the item, the slug is for reading. A
  # token-only or outdated-slug URL redirects to the current one - so
  # every link ever made to an item keeps working.
  path('<str:token>/<slug:slug>/', views.ContentDetailView.as_view(), name='detail'),
  path('<str:token>/', views.ContentDetailView.as_view(), name='detail_by_token'),
]
