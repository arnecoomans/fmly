from django.urls import path

from . import views
#from core.views import SignUpView

app_name = 'archive'
urlpatterns = [
  # Images
  path('', views.RecentImageListView.as_view(), name='home'),
  path('image/<int:pk>/', views.ImageRedirectView.as_view(), name='image-redirect'),
  path('image/<int:pk>/comment/', views.AddCommentView.as_view(), name='comment'),
  path('image/<int:pk>/edit/', views.EditImageView.as_view(), name='image-edit'),
  path('image/<int:pk>/attach/', views.AddAttachmentToImageView.as_view(), name='image-add-attachment'),
  path('image/<int:pk>/<name>/', views.ImageView.as_view(), name='image'),
  
  # Special Image views
  path('year/<year>/', views.ImageYearRedirectView.as_view(), {'columns': ('year')}, name='images-by-year'),
  path('decade/<decade>/', views.ImageDecadeListView.as_view(), {'columns': ('decade')}, name='images-by-decade'),
  
  # User actions and views
  path('mijn/afbeeldingen/', views.ImageListByUserView.as_view(), name='my-images'),
  path('mijn/bio/', views.PersonUserView.as_view(), name='my-bio'),
  path('mijn/comments/', views.CommentListByUserView.as_view(), name='my-comments'),
  path('<username>/afbeeldingen/', views.ImageListByUserView.as_view(), {'columns': ('username')}, name='images-of-user'),
  path('<username>/bio/', views.PersonUserView.as_view(), {'columns': ('username')}, name='bio-of-user'),
  path('<username>/comments/', views.CommentListByUserView.as_view(), {'columns': ('username')}, name='bio-of-user'),

  # People
  path('people/', views.PersonListView.as_view(), name='people'),
  #path('people/all/', views.PersonAllListView.as_view(), name='all-people'),
  #path('people/list/', views.PersonListView.as_view(), name='person-list'),
  path('person/<int:pk>/', views.PersonRedirectView.as_view(), name='person-short'),
  path('person/<int:pk>/edit', views.EditPersonView.as_view(), name='person-edit'),
  path('person/<int:pk>/<name>/', views.PersonView.as_view(), name='person'),
    
  # Tags 
  path('tags/', views.TagListView.as_view(), name='tags'),
  path('tag/<slug>/', views.ImagesByTagListView.as_view(), name='tag'),
    
  # Notes
  path('note/', views.NotesListView.as_view(), name='notes'),
  path('note/<int:pk>/edit/', views.EditNoteView.as_view(), name='note-edit'),
  path('note/<int:pk>/', views.NoteView.as_view(), name='note'),
  path('note/<int:pk>/<title>/', views.NoteView.as_view(), name='note-with-name'),

  # Comments
  path('comments/', views.CommentListView.as_view(), name='comments'),
  path('comments/<int:pk>/edit/', views.EditCommentView.as_view(), name='edit-comment'),

  # Adding and removing
  path('add/image/', views.AddImageView.as_view(), name='add-photo'),
  path('add/images/', views.AddImagesView.as_view(), name='add-photos'),
  path('add/person/', views.AddPersonView.as_view(), name='add-person'),
  path('add/note/', views.AddNoteView.as_view(), name='add-note'),
  path('add/tag/', views.AddTagView.as_view(), name='add-tag'),
  
  # Accounts
  path("sign-up", views.SignUpView.as_view(), name='signup'),

  # Special views
  path('preview/', views.RecentImageListPreView.as_view(), name='preview'),
]
