from django.contrib import admin
from django.template.defaultfilters import slugify
from django.contrib import messages
from django.utils.translation import gettext as _

from cmnsd.admin import ReadOnlyAdmin

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

def get_location(name, request):
  # Find location by full name
  if Location.objects.filter(name__icontains=name).exists():
    location = Location.objects.filter(name__icontains=name).first()
    return location
  else:
    L = name.split(' ')[0].replace(',', '').strip()
    # Try to find location by first word
    try:
      location = Location.objects.filter(name__icontains=L).first()
      return location
    except Location.DoesNotExist:
      location = Location.objects.get_or_create(name=name, slug=slugify(name)[:64], user=request.user)[0]
      return location
@admin.action(description="migrate dates to events")
def migrate_dates(modeladmin, request, queryset):
  for person in queryset:
    # Create a new event for date of birth
    if person.year_of_birth:
      event = Event.objects.get_or_create(
        type = 'birth',
        year = person.year_of_birth,
        month = person.month_of_birth,
        day = person.day_of_birth,
        user = request.user,
      )[0]
      event.people.add(person)
      if person.place_of_birth:
        location = get_location(person.place_of_birth, request)
        if location:
          event.locations.add(location)
      event.save()
    # Create a new event for date of death
    if person.year_of_death:
      event = Event.objects.get_or_create(
        type = 'death',
        year = person.year_of_death,
        month = person.month_of_death,
        day = person.day_of_death,
        user = request.user,
      )[0]
      event.people.add(person)
      if person.place_of_death:
        location = get_location(person.place_of_death, request)
        if location:
          event.locations.add(location)
      event.save()
  messages.add_message(request, messages.SUCCESS, f"{ _('Succesfully migrated dates to events for selected people.') }")

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
class CommentAdmin(ReadOnlyAdmin):
  list_display = ['user', 'image', 'status', 'content']
  list_filter = ['image']

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
      item.visibility_frontpage = False if item.visibility_frontpage else True
      item.save()
      messages.add_message(request, messages.SUCCESS,
                           f"{ _('Succesfully marked items as') } { _('visible') if item.visibility_frontpage else _('invisible') }: { item.title }")

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


  list_display = ['id', 'slug', 'category', 'getSize', 'visibility_frontpage', 'year']
  list_display_links =['slug',]
  search_fields = ['title', 'description']
  exclude = []
  empty_value_display = '---'
  actions = [toggle_show, softdelete, softundelete, setSlugFromTitle, reset_thumbnail, resetSize,  ]
  list_filter = ['tag', 'visibility_frontpage', 'people']
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
  @admin.action(description='Purge given name')
  def purge_given_name(modeladmin, request, queryset):
    queryset.update(given_name='')
    messages.add_message(request, messages.SUCCESS, f"{ _('Succesfully marked items as') } { _('not deleted') }.")

  list_display = ['first_names', 'given_name', 'last_name', 'nickname', 'slug']
  prepopulated_fields = {'slug': ('first_names', 'last_name',), 
                         }
  list_filter = ['last_name', 'images']
  inlines = [FamilyRelationsInline,]
  actions = [toggleGender, purge_given_name, migrate_dates]

  def get_changeform_initial_data(self, request):
    get_data = super(PersonAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data


class TagAdmin(admin.ModelAdmin):
  prepopulated_fields = {'slug': ('name',)}
  list_display = ['name', 'slug']

class CategoryAdmin(admin.ModelAdmin):
  prepopulated_fields = {'slug': ('name',)}
  list_display = ['name', 'parent', 'slug']

class LocationAdmin(admin.ModelAdmin):
  prepopulated_fields = {'slug': ('name',)}
  list_display = ['name', 'parent', 'slug']

class EventAdmin(admin.ModelAdmin):
  list_display = ('id','display_str', 'type',)

  def get_changeform_initial_data(self, request):
    get_data = super(EventAdmin, self).get_changeform_initial_data(request)
    get_data['user'] = request.user.pk
    return get_data

  def display_str(self, obj):
    return str(obj)
  
  list_filter = ['type',]
  search_fields = ['title', 'description']
  sortable_by = ['id', 'type', 'year']

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
admin.site.register(Category, CategoryAdmin)
admin.site.register(Location, LocationAdmin)
admin.site.register(Event, EventAdmin)