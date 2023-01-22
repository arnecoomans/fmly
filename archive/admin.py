from django.contrib import admin
from django.template.defaultfilters import slugify
from django.contrib import messages
from django.utils.translation import gettext as _

from .models import *
''' Admin Actions - Used by more than one Model '''
@admin.action(description=_('Softdelete'))
def softdelete(modeladmin, request, queryset):
  queryset.update(is_deleted=True)
  messages.add_message(request, messages.SUCCESS, f"{ _('Succesfully marked items as') } { _('deleted') }.")
@admin.action(description=_('Softundelete'))
def softundelete(modeladmin, request, queryset):
  queryset.update(is_deleted=False)
  messages.add_message(request, messages.SUCCESS, f"{ _('Succesfully marked items as') } { _('not deleted') }.")

''' Attachment Model Admin '''
class AttachmentAdmin(admin.ModelAdmin):
  ''' Admin Tasks '''
  @admin.action(description=_('Set slug from filename'))
  def setSlug(modeladmin, request, queryset):
    for attachment in queryset:
      attachment.slug = slugify(str(attachment.file).replace('files/', '')[:64])
      attachment.save()
      messages.add_message(request, messages.SUCCESS, _('Succesfully set attachment slug to ') + attachment.slug)
  list_display = ['description', 'is_deleted']
  prepopulated_fields = {'slug': ('file',)}
  actions = [setSlug, softdelete, softundelete]

  def get_changeform_initial_data(self, request):
    get_data = super(AttachmentAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data


''' Comment Model Admin '''
class CommentAdmin(admin.ModelAdmin):
  list_display = ['user', 'image', 'is_deleted', 'content']
  list_filter = ['image']
  actions = [softdelete, softundelete]

  def get_changeform_initial_data(self, request):
    get_data = super(CommentAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data


''' FamilyRelations Model Admin '''
class FamilyRelationsInline(admin.TabularInline):
  model = FamilyRelations
  fk_name = 'down'


''' Group Model Admin '''
class GroupAdmin(admin.ModelAdmin):
  def get_changeform_initial_data(self, request):
    get_data = super(GroupAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data

  
''' Image Model Admin '''
class ImageAdmin(admin.ModelAdmin):
  ''' Admin Tasks '''
  @admin.action(description=_('Toggle show on index'))
  def toggle_show(modeladmin, request, queryset):
    for item in queryset:
      item.show_in_index = False if item.show_in_index else True
      item.save()
      messages.add_message(request, messages.SUCCESS, f"{ _('Succesfully marked items as') } { _('visible') if item.show_in_index else _('invisible') }: { item.title }")

  @admin.action(description='Set slug from title')
  def setSlugFromTitle(modeladmin, request, queryset):
    for object in queryset:
      object.slug = None
      object.save()
      messages.add_message(request, messages.SUCCESS, f"{ _('Succesfully set items title to') }: { object.title }")

  @admin.action(description='Reset thumbnails')
  def reset_thumbnail(modeladmin, request, queryset):
    # queryset.update(thumbnail=None)
    for object in queryset:
      object.thumbnail = None
      object.save()
  
  @admin.action(description='Reset File Size')
  def resetSize(modeladmin, request, queryset):
    for object in queryset:
      object.storeSize()


  list_display = ['id', 'slug', 'has_thumbnail', 'show_in_index', 'year']
  list_display_links =['slug',]
  search_fields = ['title', 'description']
  exclude = []
  empty_value_display = '---'
  actions = [toggle_show, softdelete, softundelete, setSlugFromTitle, reset_thumbnail, resetSize,  ]
  list_filter = ['tag', 'show_in_index', 'people']
  def get_changeform_initial_data(self, request):
    get_data = super(ImageAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data


''' Note Model Admin '''
class NoteAdmin(admin.ModelAdmin):
  def get_changeform_initial_data(self, request):
    get_data = super(NoteAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data


''' Person Model Admin '''
class PersonAdmin(admin.ModelAdmin):
  ''' Actions '''
  @admin.action(description=_('Toggle Gender'))
  def toggleGender(modeladmin, request, queryset):
    for item in queryset:
      item.gender = 'f' if item.gender == 'm' else 'm'
      item.save()
      messages.add_message(request, messages.SUCCESS, f"{ _('Succesfully marked items as') } { _(item.get_gender_display()) }: { item.full_name() }")
      
  list_display = ['first_name', 'given_names', 'last_name', 'nickname', 'slug']
  prepopulated_fields = {'slug': ('given_names', 'last_name',), 
                         'given_names': ('first_name',),}
  list_filter = ['last_name', 'images']
  inlines = [FamilyRelationsInline,]
  actions=[toggleGender]
  def get_changeform_initial_data(self, request):
    get_data = super(PersonAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data


class TagAdmin(admin.ModelAdmin):
  prepopulated_fields = {'slug': ('title',)}
  list_display = ['title', 'slug']


''' Register Admin Models '''
admin.site.register(Attachment, AttachmentAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(FamilyRelations)
admin.site.register(Group, GroupAdmin)
admin.site.register(Image, ImageAdmin)
admin.site.register(Note, NoteAdmin)
admin.site.register(Person, PersonAdmin)
admin.site.register(Preference)
admin.site.register(Tag, TagAdmin)
