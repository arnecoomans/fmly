# Generated by Django 5.1 on 2024-10-25 14:19

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0075_alter_preference_favorites'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='comment',
            unique_together={('image', 'content')},
        ),
    ]