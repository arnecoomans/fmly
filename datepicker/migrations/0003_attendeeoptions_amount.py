# Generated by Django 4.1.4 on 2023-02-02 12:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datepicker', '0002_alter_option_event_end'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendeeoptions',
            name='amount',
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
