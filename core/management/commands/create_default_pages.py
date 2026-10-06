from django.conf import settings
from django.core.management.base import BaseCommand

from cmnsd.models import Page

SITE_NAME = getattr(settings, 'SITE_NAME', 'FMLY')

# The pages the site links to (the footer: cookie-statement), each in every
# language it's written in - one row per language, the same slug (cmnsd
# Page: the visitor's language, else the site's default). What they say is
# fmly's: two cookies, nothing loaded from elsewhere, choices stored on the
# account rather than in the browser.
DEFAULT_PAGES = [
  {
    'slug': 'cookie-statement', 'language': 'en', 'title': 'Cookie statement',
    'body': f"""{SITE_NAME} is a private family archive. It uses as few cookies as it can, and none to follow you.

### The cookies

- **Session cookie** - keeps you signed in during your visit, and remembers whether edit mode is on. It ends when you sign out.
- **CSRF cookie** - protects the forms you send (a comment, an upload) against requests made from elsewhere. Required for security.

That is all. Your language, which sections you keep folded and how you sort lists are stored with your account, not in your browser. Signed out, nothing is remembered.

Besides cookies, your browser briefly keeps a message (such as "saved") while a page reloads, and forgets it right after.

### Nothing from elsewhere

All scripts, styles, icons and fonts come from {SITE_NAME} itself. Visiting the site shares nothing with other companies: no analytics, no advertising, no tracking cookies.

### Your information

What you see depends on what you may see: most of the archive is for signed-in family members, and some of it only for family or for you. You manage your name and email on your [profile](/accounts/profile/) and your language and who counts as family in your [preferences](/preferences/).

### Questions?

Ask the person who invited you to {SITE_NAME}.
""",
  },
  {
    'slug': 'cookie-statement', 'language': 'nl', 'title': 'Cookieverklaring',
    'body': f"""{SITE_NAME} is een besloten familiearchief. Het gebruikt zo min mogelijk cookies, en geen enkele om je te volgen.

### De cookies

- **Sessiecookie** - houdt je ingelogd tijdens je bezoek en onthoudt of de bewerkmodus aan staat. Verdwijnt als je uitlogt.
- **CSRF-cookie** - beschermt de formulieren die je verstuurt (een reactie, een upload) tegen verzoeken van buitenaf. Vereist voor de beveiliging.

Dat is alles. Je taal, welke onderdelen je dichtgeklapt houdt en hoe je lijsten sorteert, worden bij je account bewaard, niet in je browser. Uitgelogd wordt er niets onthouden.

Naast cookies bewaart je browser heel even een melding (zoals "opgeslagen") terwijl een pagina opnieuw laadt, en vergeet die direct daarna.

### Niets van elders

Alle scripts, opmaak, pictogrammen en lettertypen komen van {SITE_NAME} zelf. Een bezoek deelt niets met andere bedrijven: geen statistieken, geen advertenties, geen trackingcookies.

### Jouw gegevens

Wat je ziet hangt af van wat je mag zien: het meeste van het archief is voor ingelogde familieleden, en sommige dingen alleen voor familie of alleen voor jou. Je naam en e-mailadres beheer je op je [profiel](/accounts/profile/), je taal en wie als familie telt in je [voorkeuren](/preferences/).

### Vragen?

Vraag het aan degene die je voor {SITE_NAME} heeft uitgenodigd.
""",
  },
]


class Command(BaseCommand):
  help = (
    "Create the pages the site links to (the cookie statement), in each "
    "language written - only what's missing: a page edited in the admin is "
    "left alone, unless --force. Published."
  )

  def add_arguments(self, parser):
    parser.add_argument('--force', action='store_true', help="Overwrite existing pages with the default text.")

  def handle(self, *args, **options):
    created = updated = kept = 0
    for spec in DEFAULT_PAGES:
      fields = {'title': spec['title'], 'body': spec['body'], 'status': Page.Status.PUBLISHED}
      page = Page.objects.filter(slug=spec['slug'], language=spec['language']).first()
      if page is None:
        Page.objects.create(slug=spec['slug'], language=spec['language'], **fields)
        created += 1
      elif options['force']:
        for name, value in fields.items():
          setattr(page, name, value)
        page.save()
        updated += 1
      else:
        kept += 1
    self.stdout.write(self.style.SUCCESS(f"Pages: {created} created, {updated} overwritten, {kept} kept as they are."))
