# Generated by Django 4.0.1 on 2022-01-22 18:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0006_rename_documents'),
    ]

    operations = [
        migrations.RenameField(
            model_name='comment',
            old_name='document',
            new_name='image',
        ),
        migrations.AlterField(
            model_name='image',
            name='people',
            field=models.ManyToManyField(blank=True, help_text='Tag people that are on the photo', related_name='images', to='archive.Person'),
        ),
        migrations.AlterField(
            model_name='image',
            name='tag',
            field=models.ManyToManyField(blank=True, related_name='images', to='archive.Tag'),
        ),
    ]
