# Generated by Django 4.0.1 on 2022-01-19 11:12

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('slug', models.SlugField(unique=True)),
            ],
            options={
                'ordering': ['title'],
            },
        ),
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(blank=True, max_length=255)),
                ('middle_name', models.CharField(blank=True, max_length=255)),
                ('last_name', models.CharField(blank=True, max_length=255)),
                ('nickname', models.CharField(blank=True, max_length=255)),
                ('slug', models.CharField(max_length=255, unique=True)),
                ('place_of_birth', models.CharField(blank=True, max_length=255)),
                ('place_of_death', models.CharField(blank=True, max_length=255)),
                ('date_of_birth', models.DateField(blank=True, null=True)),
                ('year_of_birth', models.PositiveSmallIntegerField(blank=True, help_text='Is automatically filled when date is supplied', null=True)),
                ('date_of_death', models.DateField(blank=True, null=True)),
                ('year_of_death', models.PositiveSmallIntegerField(blank=True, help_text='Is automatically filled when date is supplied', null=True)),
                ('bio', models.TextField(blank=True, help_text='Markdown supported')),
                ('related_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='related_person', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('last_name', 'first_name'),
            },
        ),
        migrations.CreateModel(
            name='Note',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, max_length=255)),
                ('content', models.TextField(blank=True, help_text='Markdown Supported')),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('people', models.ManyToManyField(blank=True, related_name='notes', to='archive.Person')),
                ('tag', models.ManyToManyField(blank=True, related_name='notes', to='archive.Tag')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='FamilyRelations',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('down', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='relation_up', to='archive.person')),
                ('up', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='relation_down', to='archive.person')),
            ],
        ),
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.ImageField(upload_to='')),
                ('thumbnail', models.CharField(blank=True, max_length=2000, null=True)),
                ('title', models.CharField(max_length=255)),
                ('show_in_index', models.BooleanField(default=True)),
                ('description', models.TextField(blank=True, help_text='Markdown supported')),
                ('document_source', models.CharField(blank=True, help_text='Link or textual description of source', max_length=255)),
                ('attachment', models.FileField(blank=True, help_text='Possible to attach file to an image. Use for pdf, doc, excel, etc.', null=True, upload_to='files')),
                ('year', models.PositiveSmallIntegerField(blank=True, help_text='Is automatically filled when date is supplied', null=True)),
                ('date', models.DateField(blank=True, help_text='Format: year-month-date, for example 1981-08-11', null=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('images', models.ManyToManyField(blank=True, help_text='Link another image to this one to create an image set', to='archive.Document')),
                ('people', models.ManyToManyField(blank=True, help_text='Tag people that are on the photo', related_name='documents', to='archive.Person')),
                ('tag', models.ManyToManyField(blank=True, related_name='documents', to='archive.Tag')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('content', models.TextField(help_text='Markdown supported')),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='archive.document')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
