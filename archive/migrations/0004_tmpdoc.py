# Generated by Django 4.0.1 on 2022-01-22 10:20

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('archive', '0003_alter_person_slug'),
    ]

    operations = [
        migrations.CreateModel(
            name='TmpDoc',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.ImageField(upload_to='')),
                ('title', models.CharField(max_length=255)),
                ('show_in_index', models.BooleanField(default=True)),
                ('year', models.PositiveSmallIntegerField(blank=True, help_text='Is automatically filled when date is supplied', null=True)),
                ('date', models.DateField(blank=True, help_text='Format: year-month-date, for example 1981-08-11', null=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
