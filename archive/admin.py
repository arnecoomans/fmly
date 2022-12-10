from django.contrib import admin

# Register your models here.
from .models import *
# Actions
@admin.action(description='Reset thumbnails')
def reset_thumbnail(modeladmin, request, queryset):
  queryset.update(thumbnail=None)
@admin.action(description='Show on index')
def show(modeladmin, request, queryset):
  queryset.update(show_in_index=True)
@admin.action(description='Hide on index')
def hide(modeladmin, request, queryset):
  queryset.update(show_in_index=False)
@admin.action(description='Softdelete')
def softdelete(modeladmin, request, queryset):
  queryset.update(is_deleted=True)

@admin.action(description='Set image dates from date field')
def fixDate(modeladmin, request, queryset):
  for object in queryset:
    object.fixdate()

@admin.action(description='Reset Image Dimensions')
def resetDimensions(modeladmin, request, queryset):
  for image in queryset:
    image.storeDimensions()
@admin.action(description='Reset Image Orientation')
def resetOrientation(modeladmin, request, queryset):
  for image in queryset:
    image.storeOrientation()
@admin.action(description='Reset File Size')
def resetSize(modeladmin, request, queryset):
  for object in queryset:
    object.storeSize()


class FamilyRelationsInline(admin.TabularInline):
  model = FamilyRelations
  fk_name = 'down'

class TagAdmin(admin.ModelAdmin):
  prepopulated_fields = {'slug': ('title',)}
  list_display = ['title', 'slug']

class PersonAdmin(admin.ModelAdmin):
  list_display = ['first_name', 'given_names', 'last_name', 'nickname', 'slug']
  prepopulated_fields = {'slug': ('given_names', 'last_name',), 
                         'given_names': ('first_name',),}
  list_filter = ['last_name']
  inlines = [FamilyRelationsInline,]
  actions=[fixDate]
  def get_changeform_initial_data(self, request):
    get_data = super(PersonAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data

class GroupAdmin(admin.ModelAdmin):
  def get_changeform_initial_data(self, request):
    get_data = super(GroupAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data


class ImageAdmin(admin.ModelAdmin):
  list_display = ['get_indexed_name', 'show_in_index', 'count_tags', 'count_people', 'year']
  search_fields = ['title', 'description']
  exclude = ['thumbnail']
  empty_value_display = '---'
  actions = [reset_thumbnail, show, hide, softdelete, resetDimensions, resetOrientation, resetSize ]
  list_filter = ['tag', 'show_in_index', 'people']
  def get_changeform_initial_data(self, request):
    get_data = super(ImageAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data

class AttachmentAdmin(admin.ModelAdmin):
  def get_changeform_initial_data(self, request):
    get_data = super(AttachmentAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data

class NoteAdmin(admin.ModelAdmin):
  def get_changeform_initial_data(self, request):
    get_data = super(NoteAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data

class CommentAdmin(admin.ModelAdmin):
  list_display = ['user', 'image', 'content']
  def get_changeform_initial_data(self, request):
    get_data = super(CommentAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data

class FamilyRelationsAdmin(admin.ModelAdmin):
  pass

admin.site.register(Image, ImageAdmin)
admin.site.register(Person, PersonAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(Note, NoteAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(FamilyRelations, FamilyRelationsAdmin)
admin.site.register(Attachment)
admin.site.register(Group, GroupAdmin)

#admin.site.register(TmpDoc)