"""
Content.people gets a role (issue #471): the link table it always had
(content_content_people) becomes the ContentPerson model - in Django's
state only, the table and its 548 rows stay as they are - and then gains
the role column, empty for every existing link (unknown, not a guess).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0005_remove_bookcontent_author'),
        ('people', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='ContentPerson',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('content', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='person_links', to='content.content')),
                        ('person', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='content_links', to='people.person')),
                    ],
                    options={
                        'db_table': 'content_content_people',
                        'unique_together': {('content', 'person')},
                    },
                ),
                migrations.AlterField(
                    model_name='content',
                    name='people',
                    field=models.ManyToManyField(blank=True, related_name='content', through='content.ContentPerson', to='people.person'),
                ),
            ],
            database_operations=[],
        ),
        migrations.AddField(
            model_name='contentperson',
            name='role',
            field=models.CharField(blank=True, choices=[('subject', 'subject'), ('creator', 'creator'), ('addressee', 'addressee'), ('depicted', 'depicted'), ('possibly_depicted', 'possibly depicted'), ('owner', 'owner')], default='', max_length=20),
        ),
    ]
