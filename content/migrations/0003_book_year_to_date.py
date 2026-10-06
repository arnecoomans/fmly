from django.db import migrations


def year_to_date(apps, schema_editor):
  """A book's publication_year becomes its date (Content.year), where the
  date is still empty - a date already filled in by hand is kept. The
  field itself goes in the next migration: data and schema changes in
  separate migrations, as PostgreSQL may refuse to alter a table in the
  transaction that just updated rows."""
  BookContent = apps.get_model('content', 'BookContent')
  Content = apps.get_model('content', 'Content')
  for detail in BookContent.objects.exclude(publication_year=None).select_related('content'):
    Content.objects.filter(pk=detail.content_id, year=None).update(year=detail.publication_year)


class Migration(migrations.Migration):

  dependencies = [
    ('content', '0002_initial'),
  ]

  operations = [
    migrations.RunPython(year_to_date, migrations.RunPython.noop),
  ]
