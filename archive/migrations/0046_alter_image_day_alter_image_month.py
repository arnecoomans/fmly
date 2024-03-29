# Generated by Django 4.1 on 2022-12-12 20:32

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0045_image_date_modified'),
    ]

    operations = [
        migrations.AlterField(
            model_name='image',
            name='day',
            field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MaxValueValidator(31), django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AlterField(
            model_name='image',
            name='month',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, 'januari'), (2, 'februari'), (3, 'maart'), (4, 'april'), (5, 'mei'), (6, 'juni'), (7, 'juli'), (8, 'augustus'), (9, 'september'), (10, 'oktober'), (11, 'november'), (12, 'december')], null=True),
        ),
    ]
