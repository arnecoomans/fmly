# Generated by Django 4.2.4 on 2023-12-24 10:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0072_image_family'),
    ]

    operations = [
        migrations.AddField(
            model_name='preference',
            name='favorites',
            field=models.ManyToManyField(null=True, related_name='favorites', to='archive.image'),
        ),
    ]
