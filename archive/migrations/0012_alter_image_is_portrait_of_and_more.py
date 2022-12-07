# Generated by Django 4.0.1 on 2022-01-25 08:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0011_alter_comment_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='image',
            name='is_portrait_of',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='portrait', to='archive.person'),
        ),
        migrations.AlterField(
            model_name='person',
            name='date_of_birth',
            field=models.DateField(blank=True, help_text='Format: year-month-date, for example 1981-08-11', null=True),
        ),
        migrations.AlterField(
            model_name='person',
            name='date_of_death',
            field=models.DateField(blank=True, help_text='Format: year-month-date, for example 1981-08-11', null=True),
        ),
    ]
