from django.contrib import admin
from django.template.defaultfilters import slugify

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
@admin.action(description='Softundelete')
def softundelete(modeladmin, request, queryset):
  queryset.update(is_deleted=False)
@admin.action(description='Set slug from file')
def setSlug(modeladmin, request, queryset):
  for attachment in queryset:
    attachment.slug = slugify(str(attachment.file).replace('files/', '')[:64])
    attachment.save()
@admin.action(description='Set image dates from date field')
def fixDate(modeladmin, request, queryset):
  for object in queryset:
    object.fixdate()
@admin.action(description='Set slug from title')
def setSlugFromTitle(modeladmin, request, queryset):
  for object in queryset:
    object.slug = None
    object.save()
@admin.action(description='Set gender Female')
def setGenderFemale(modeladmin, request, queryset):
  queryset.update(gender='f')
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
  list_filter = ['last_name', 'images']
  inlines = [FamilyRelationsInline,]
  actions=[fixDate, setGenderFemale]
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
  list_display = ['get_indexed_name', 'slug', 'show_in_index', 'year']
  search_fields = ['title', 'description']
  exclude = ['thumbnail']
  empty_value_display = '---'
  actions = [reset_thumbnail, show, hide, softdelete, resetDimensions, resetOrientation, resetSize, setSlugFromTitle ]
  list_filter = ['tag', 'show_in_index', 'people']
  def get_changeform_initial_data(self, request):
    get_data = super(ImageAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data

class AttachmentAdmin(admin.ModelAdmin):
  list_display = ['description', 'is_deleted']
  prepopulated_fields = {'slug': ('file',)}
  def get_changeform_initial_data(self, request):
    get_data = super(AttachmentAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data
  actions = [setSlug, softdelete, softundelete]

class NoteAdmin(admin.ModelAdmin):
  def get_changeform_initial_data(self, request):
    get_data = super(NoteAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data

class CommentAdmin(admin.ModelAdmin):
  list_display = ['user', 'image', 'is_deleted', 'content']
  list_filter = ['image']
  actions = [softdelete, softundelete]
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
admin.site.register(Attachment, AttachmentAdmin)
admin.site.register(Group, GroupAdmin)
admin.site.register(Preference)
admin.site.register(Tree)
#admin.site.register(TmpDoc)