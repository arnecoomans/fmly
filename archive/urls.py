from django.urls import path

from . import views
#from core.views import SignUpView

app_name = 'archive'
urlpatterns = [
  # Images
  path('', views.ImageListView.as_view(), name='home'),
  path('object/<int:pk>/', views.ImageRedirectView.as_view(), name='image-redirect'),
  path('object/<int:pk>/comment/', views.AddCommentView.as_view(), name='comment'),
  #path('object/<int:pk>/edit/', views.EditImageView.as_view(), name='image-edit'),
  #path('object/<int:pk>/attach/', views.AddAttachmentToImageView.as_view(), name='image-add-attachment'),
  path('object/<int:pk>/<name>/', views.ImageView.as_view(), name='image'),
  
  # Special Image views
  path('objects/<int:decade>/', views.ImageListView.as_view(), {'columns': ('decade')}, name='images-by-decade'),
  path('objects/<str:tag>', views.ImageListView.as_view(), {'columns': ('tag')}, name='image-with-tag'),
  path('objects/by/<str:user>', views.ImageListView.as_view(), {'columns': ('user')}, name='image-by-uploader'),


  # People
  path('people/', views.PersonListView.as_view(), name='people'),
  path('person/<int:pk>/', views.PersonRedirectView.as_view(), name='person-short'),
  path('person/<int:pk>/edit', views.EditPersonView.as_view(), name='person-edit'),
  path('person/<int:pk>/<name>/', views.PersonView.as_view(), name='person'),
  path('person/add', views.AddPersonView.as_view(), name='add-person'),
  
  # Relationships
  path('person/<int:subject>/<str:type>:<int:removed_person>/delete/', views.PersonRemoveRelationView.as_view(), {'columns': ('up', 'relation', 'down')}, name='remove-relationship'),
  path('person/add-relation/', views.PersonAddRelationView.as_view(), name='add-relationship'),
  # Tags 
  path('tags/', views.TagListView.as_view(), name='list-tags'),
  #path('tag/<slug>/', views.ImagesByTagListView.as_view(), name='tag'),
    
  # Notes
  path('note/', views.NotesListView.as_view(), name='notes'),
  path('note/<int:pk>/edit/', views.EditNoteView.as_view(), name='note-edit'),
  path('note/<int:pk>/', views.NoteView.as_view(), name='note'),
  path('note/<int:pk>/<title>/', views.NoteView.as_view(), name='note-with-name'),
  path('note/new/', views.AddNoteView.as_view(), name='add-note'),

  # Comments
  path('comments/', views.CommentListView.as_view(), name='comments'),
  path('comment/<int:pk>/delete/', views.CommentDeleteView.as_view(), name='delete-comment'),
  path('comment/<int:pk>/undelete/', views.CommentUnDeleteView.as_view(), name='undelete-comment'),
  
  # path('comments/<int:pk>/edit/', views.EditCommentView.as_view(), name='edit-comment'),

  # Adding and removing
  # path('add/image/', views.AddImageView.as_view(), name='add-photo'),
  # path('add/images/', views.AddImagesView.as_view(), name='add-photos'),
  # path('add/person/', views.AddPersonView.as_view(), name='add-person'),
  # path('add/note/', views.AddNoteView.as_view(), name='add-note'),
  # path('add/tag/', views.AddTagView.as_view(), name='add-tag'),
  
  # Accounts
  path("sign-up", views.SignUpView.as_view(), name='signup'),

  # Special views
  #path('preview/', views.RecentImageListPreView.as_view(), name='preview'),
]
