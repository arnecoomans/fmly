from django.core.management.base import BaseCommand, CommandError

from people.gedcom import export
from people.models import Person


class Command(BaseCommand):
  help = (
    "GEDCOM 5.5.1 of one person (people/gedcom.py, issue #463), to the console. "
    "--depth N adds their partners and children, N levels down: 1 = their family "
    "group, 2 = also the children's partners and the grandchildren. Living people "
    "as initials; private people and outsiders left out."
  )

  def add_arguments(self, parser):
    parser.add_argument('token', help="The person's token (from their address: /person/<token>/...)")
    parser.add_argument('--depth', type=int, default=0, help="Levels of partners and children (default 0: the person alone)")

  def handle(self, token, depth, **options):
    if depth < 0:
      raise CommandError("--depth can't be negative.")
    person = Person.objects.filter(token=token).first()
    if person is None:
      raise CommandError(f"No person with token {token}.")
    self.stdout.write(export(person, depth), ending='')
