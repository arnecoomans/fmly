# Generated by Django 4.1 on 2022-12-13 13:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0046_alter_image_day_alter_image_month'),
    ]

    operations = [
        migrations.AlterField(
            model_name='image',
            name='title',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
