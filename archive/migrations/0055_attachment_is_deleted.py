# Generated by Django 4.1 on 2022-12-22 19:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0054_alter_person_options_rename_tag_note_tags_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='attachment',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
    ]
