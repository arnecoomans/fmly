# Generated by Django 5.1 on 2024-10-26 15:06

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0077_alter_comment_unique_together'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='comment',
            options={'ordering': ['-date_created']},
        ),
    ]
