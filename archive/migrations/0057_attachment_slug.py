# Generated by Django 4.1 on 2022-12-23 21:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0056_rename_desciption_attachment_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='attachment',
            name='slug',
            field=models.CharField(default='slug', max_length=255),
            preserve_default=False,
        ),
    ]
