# Generated by Django 4.1 on 2022-12-17 06:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0052_rename_upload_is_hidden_preference_show_new_uploads'),
    ]

    operations = [
        migrations.AlterField(
            model_name='preference',
            name='show_new_uploads',
            field=models.BooleanField(default=True),
        ),
    ]
