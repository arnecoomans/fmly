from django.urls import path

from . import views
from cmnsdjango import views as cmnsviews
#from core.views import SignUpView

app_name = 'archive'
urlpatterns = [
  # Images
  path('', views.ImageListView.as_view(), name='home'),
  path('object/<int:pk>/', views.ImageRedirectView.as_view(), name='image-redirect'),
  # path('object/<int:pk>/comment/', views.AddCommentView.as_view(), name='comment'),
  path('object/<int:pk>/edit/', views.EditImageView.as_view(), name='image-edit'),
  path('object/new/', views.AddImageView.as_view(), name='add-image'),
  path('object/<str:slug>/', views.ImageView.as_view(), name='image'),
  path('object/<str:slug>/love/', views.ToggleFavoriteImage.as_view(), name='love-image'),
  path('object/<int:pk>:<str:slug>/regeneratethumbnail/', views.RegenerateThumbnailView.as_view(), name='regenerate-thumbnail'),
  # Special Image views
  path('objects/<int:decade>/', views.ImageListView.as_view(), {'columns': ('decade')}, name='images-by-decade'),
  path('objects/by:<str:user>/', views.ImageListView.as_view(), {'columns': ('user')}, name='image-by-uploader'),
  path('objects/<str:tag>/', views.ImageListView.as_view(), {'columns': ('tag')}, name='image-with-tag'),
  path('objects/a/comments/', views.aListComments.as_view(), name='acomments'),
  path('objects/', views.ImageListView.as_view(), name='images'),

  # People
  path('people/', views.PersonListView.as_view(), name='people'),
  path('person/<int:pk>/', views.PersonRedirectView.as_view(), name='person-short'),
  path('person/<int:pk>/edit/', views.EditPersonView.as_view(), name='person-edit'),
  path('person/<int:pk>/<name>/', views.PersonView.as_view(), name='person'),
  path('person/new/', views.AddPersonView.as_view(), name='add-person'),
  path('person/add/', views.AddPerson.as_view(), name='new-add-person'),
  # Portrait
  path('person/<int:subject>/portrait:<int:removed_image>/delete/', views.RemovePortraitView.as_view(), name='remove-portrait'),
  # Relationships
  path('person/<int:subject>/<str:type>:<int:removed_person>/delete/', views.PersonRemoveRelationView.as_view(), {'columns': ('up', 'relation', 'down')}, name='remove-relationship'),
  path('person/add-relation/', views.PersonAddRelationView.as_view(), name='add-relationship'),
  # Tree
  path('tree/<int:pk>/', views.TreeView.as_view(), name="tree"),
  # Add Image
  path('person/<int:subject_id>:<str:subject_slug>/add-image/', views.AddImageView.as_view(), name='add-person-image'),
  
  # Tags 
  path('tags/', views.TagListView.as_view(), name='tags'),
  path('tag/new/', views.AddTagView.as_view(), name='add-tag'),
  path('tag/<str:slug>/', views.EditTagView.as_view(), name='edit-tag'),

  # Notes
  path('notes/', views.NotesListView.as_view(), name='notes'),
  path('note/<int:pk>/edit/', views.EditNoteView.as_view(), name='note-edit'),
  path('note/<int:pk>/', views.NoteView.as_view(), name='note'),
  path('note/<int:pk>/<title>/', views.NoteView.as_view(), name='note-with-name'),
  path('note/new/', views.AddNoteView.as_view(), name='add-note'),

  # Comments
  path('comments/', views.CommentListView.as_view(), name='comments'),
  path('comments/a/list', views.aListComments.as_view(), name='acomments'),
  path('comment/<int:pk>/edit/', views.CommentEditView.as_view(), name='edit-comment'),
  path('comment/<int:pk>/delete/', views.CommentDeleteView.as_view(), name='delete-comment'),
  path('comment/<int:pk>/undelete/', views.CommentUnDeleteView.as_view(), name='undelete-comment'),
  
  # Attachments
  path('attachments/', views.AttachmentListView.as_view(), name='attachments'),
  path('attachment/new/', views.AttachmentAddView.as_view(), name='add-attachment'),
  path('attachments/<str:user>/', views.AttachmentListView.as_view(), name='user-attachments'),
  path('attachment/<str:slug>/delete/', views.AttachmentDeleteView.as_view(), name='delete-attachment'),
  path('attachment/<str:slug>/edit/', views.AttachmentEditView.as_view(), name='edit-attachment'),
  path('attachment/<str:slug>/create-image/', views.CreateImageFromAttachmentView.as_view(), name='create-image-from-attachment'),
  path('attachment/<str:slug>/', views.AttachmentStreamView.as_view(), name='attachment'),
  
  # Accounts
  path('settings/', views.PreferencesView.as_view(), name='settings'),
  path("sign-up/", views.SignUpView.as_view(), name='signup'),

  # JSON
  # JSON GET Attributes
  path('json/<str:model>/<int:pk>:<str:slug>/attribute/<str:field>/', cmnsviews.JsonGetAttributes.as_view(), name='json-get-attributes-by-pk-slug'),
  path('json/<str:model>/<str:slug>/attribute/<str:field>/', cmnsviews.JsonGetAttributes.as_view(), name='json-get-attributes'),
  # JSON GET Suggestions
  path('json/<str:model>/<int:pk>:<str:slug>/suggest/<str:field>/', cmnsviews.JsonGetSuggestions.as_view(), name='json-get-suggestions-by-pk-slug'),
  path('json/<str:model>/<str:slug>/suggest/<str:field>/', cmnsviews.JsonGetSuggestions.as_view(), name='json-get-suggestions'),
  # JSON SET Attributes
  path('json/<str:model>/<int:pk>:<str:slug>/set/<str:field>/', cmnsviews.JsonSetAttribute.as_view(), name='json-set-attribute-by-pk-slug'),
  path('json/<str:model>/<str:slug>/set/<str:field>/', cmnsviews.JsonSetAttribute.as_view(), name='json-set-attribute'),
  # JSON DEBUG
  path('json/<str:model>/<str:slug>/suggestionform/<str:field>/', cmnsviews.JsonGetSuggestionForm.as_view(), name='json-suggestion-form'),
  # path('json/person:<int:pk>:<str:slug>/attribute/<str:attribute>/', views.JsonGetAttributeOfPerson.as_view(), name='json-get-attribute-of-person'),
  path('json/object:<int:pk>:<str:slug>/comments/', views.aListComments.as_view(), name='acommentsforimage'),
  path('json/object:<int:pk>:<str:slug>/commentform/', views.aFetchCommentForm.as_view(), name='fetchcommentform'),
  path('json/object:<int:pk>:<str:slug>/postcomment/', views.aPostComment.as_view(), name='postcomment'),
  
]