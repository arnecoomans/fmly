# Generated by Django 4.1.4 on 2023-02-02 12:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datepicker', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='option',
            name='event_end',
            field=models.DateTimeField(),
        ),
    ]
