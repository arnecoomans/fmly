from django.db import migrations


def create_initial_categories(apps, schema_editor):
  Category = apps.get_model('archive', 'Category')
  User = apps.get_model('auth', 'User')

  # Try to fetch user with ID 1
  try:
    default_user = User.objects.get(pk=1)
  except User.DoesNotExist:
    default_user = None

  # Base categories to create
  categories = [
    "Photo",
    "Document",
    "News-article",
    "Advertisement",
    "Artwork",
    "Uncategorized",
  ]

  created = {}

  # Create base categories
  for name in categories:
    obj, _ = Category.objects.get_or_create(
      name=name,
      defaults={
        "slug": name.lower().replace(" ", "-"),
        "status": "p",
        "user": default_user,
      },
    )
    created[name] = obj

  # Create Portrait under Photo
  photo = created.get("Photo")
  if photo:
    Category.objects.get_or_create(
      name="Portrait",
      defaults={
        "slug": "portrait",
        "parent": photo,
        "status": "p",
        "user": default_user,
      },
    )


def reverse_initial_categories(apps, schema_editor):
  """Remove the seeded categories. Safe to reverse."""
  Category = apps.get_model('archive', 'Category')

  names = [
    "Photo",
    "Document",
    "News-article",
    "Advertisement",
    "Artwork",
    "Uncategorized",
    "Portrait",
  ]

  Category.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

  dependencies = [
    ('archive', '0079_category'),
  ]

  operations = [
    migrations.RunPython(
      create_initial_categories,
      reverse_initial_categories,
    ),
  ]