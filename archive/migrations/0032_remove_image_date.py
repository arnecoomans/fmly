# Generated by Django 4.1 on 2022-12-08 11:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0031_image_day_image_month_alter_image_year'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='image',
            name='date',
        ),
    ]
