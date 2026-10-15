from django.db import migrations


def merge(apps, schema_editor):
  """Title and own label (kind_freetext) become one field, title: the
  longest of the two wins - in practice they held the same text."""
  Event = apps.get_model('events', 'Event')
  for event in Event.objects.exclude(kind_freetext=''):
    if len(event.kind_freetext) > len(event.title):
      Event.objects.filter(pk=event.pk).update(title=event.kind_freetext)


class Migration(migrations.Migration):

  dependencies = [
    ('events', '0004_event_kind_residence'),
  ]

  operations = [
    migrations.RunPython(merge, migrations.RunPython.noop),
    migrations.RemoveField(model_name='event', name='kind_freetext'),
  ]
