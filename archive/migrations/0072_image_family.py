# Generated by Django 4.2.4 on 2023-12-14 08:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0071_rename_show_in_index_image_visibility_frontpage_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='image',
            name='family',
            field=models.CharField(blank=True, help_text='Add image to family collection if no family member can be tagged', max_length=64, null=True),
        ),
    ]
