"""
The importers keep the old site's pks (update_or_create(pk=...)). A
database with id sequences - PostgreSQL - doesn't move a sequence past an
id that was inserted explicitly: the next row created without a pk (a
root tag, a dateless death's event, a person added on the site later) gets
id 1 and collides with an imported row ("duplicate key value violates
unique constraint ..._pkey"). SQLite has no sequences - it takes the
highest id plus one - so this never shows there, and on SQLite
sequence_reset_sql() returns nothing.

reset_sequences() sets each sequence to the highest id in its table: the
same "next free pk" SQLite gives. Every import command calls it at its end,
so a command run on its own leaves the database ready too; one that
creates rows without a pk in between (import_content_tags' root tags)
calls it for that model first.
"""

from django.apps import apps
from django.core.management.color import no_style
from django.db import connection


def reset_sequences(*models):
  """Move the id sequences of `models` - all installed models when none are
  given - past their highest id. Nothing to do on SQLite."""
  models = models or apps.get_models()
  statements = connection.ops.sequence_reset_sql(no_style(), models)
  if statements:
    with connection.cursor() as cursor:
      for sql in statements:
        cursor.execute(sql)
