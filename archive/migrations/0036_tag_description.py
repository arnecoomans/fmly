# Generated by Django 4.1 on 2022-12-09 18:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0035_attachment_size'),
    ]

    operations = [
        migrations.AddField(
            model_name='tag',
            name='description',
            field=models.TextField(blank=True, help_text='Write down why this tag is relevant. Markdown supported'),
        ),
    ]
