"""
Making a photo someone's portrait, from the photo's page (edit mode) - the
logic behind Content.set_portrait. Cropping it is done on the person's page
(people.forms.PersonPortraitForm).

The photo becomes the person's primary portrait (content.Portrait,
is_primary - at most one per person; a former one stays as a portrait, not
primary). Any person the editor may see - someone not yet linked to the
photo is linked to it too: a portrait is a photo of them. A new portrait
starts uncropped (the whole photo, centred); one they had before keeps its
crop. Needs the change permission on both the photo and the person; logged
on both.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from cmnsd.edit.log import log_change
from cmnsd.edit.mode import require_can_edit
from cmnsd.models.access import filter_accessible

from .models import Portrait


def set_portrait(content, token, request):
  from people.models import Person
  require_can_edit(content, request)
  if not (content.file and content.media_type == 'image'):
    raise ValidationError(_("Only a photo can be a portrait."))
  person = filter_accessible(Person.objects.all(), request).filter(token=token or '').first()
  if person is None:
    raise ValidationError(_("That person wasn't found."))
  require_can_edit(person, request)
  with transaction.atomic():
    Portrait.objects.filter(person=person, is_primary=True).exclude(content=content).update(is_primary=False)
    portrait, _created = Portrait.objects.get_or_create(person=person, content=content)
    portrait.is_primary = True
    portrait.full_clean()
    portrait.save()
    content.people.add(person)
  log_change(request, person, f"Portrait: {content}")
  log_change(request, content, f"Portrait of {person}")
  messages.success(request, _("This photo is now the portrait of %(name)s - crop it on their page.") % {'name': person})
  return {'relation': 'portrait', 'object': person}


def portrait_candidates(person, request):
  """The images this person's portrait can be chosen from on their page
  (the crop dialog's strip, people.forms.PersonPortraitForm): the current
  portrait first, then the images they're tagged in, then earlier
  portraits - only images this viewer may see. Any other photo is made a
  portrait from its own page (set_portrait)."""
  from django.db.models import Q
  from .models import Content
  items = list(
    Content.objects.visible_to(request)
    .filter(Q(people=person) | Q(portrait_links__person=person)).exclude(file='')
    .distinct().order_by('year', 'month', 'day', 'pk')
  )
  images = [item for item in items if item.media_type == 'image']
  current = person.primary_portrait_link
  current_id = current.content_id if current else None
  tagged = set(Content.objects.filter(pk__in=[i.pk for i in images], people=person).values_list('pk', flat=True))
  return sorted(images, key=lambda item: (item.pk != current_id, item.pk not in tagged))
