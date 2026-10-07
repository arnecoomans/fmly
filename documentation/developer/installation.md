# FMLY3 Installation instructions

FMLY3 is a Django 6 project (Python 3.14) on top of **cmnsd**, a shared app included as a git submodule. Development runs on macOS (Homebrew), production on Ubuntu (apt) behind nginx, gunicorn and supervisord.

## Install code via git

```sh
git clone --recurse-submodules https://github.com/arnecoomans/fmly.git
cd fmly
git -C cmnsd checkout fmly          # cmnsd's branch for FMLY3 (.gitmodules)
```

Already cloned without the submodule: `git submodule update --init`, then the checkout above.

### Initialize submodule and load data

1. A virtual environment and the requirements (see [PIP requirements](#pip-requirements)).
2. A `.env` in the project root (see [Configuration](configuration.md)).
3. The database:

   ```sh
   .venv/bin/python manage.py migrate
   ```

4. Data - one of:
   - **A copy of the live archive**, for development: `pato.sh` from cmnsd copies its database and files to your machine (`cmnsd/documentation/resources.md`).
   - **An empty archive:**

     ```sh
     .venv/bin/python manage.py createsuperuser
     .venv/bin/python manage.py prepare_release        # the "Loose end" tag, the groups Visitors and Editors
     .venv/bin/python manage.py create_default_pages   # the cookie statement, English and Dutch
     ```

## Install requirements

### System requirements

- **Python 3.14**
- **Tesseract** - OCR for transcripts ("Read the image with OCR" on the transcribe page). It runs on the server itself, so images never leave it. Optional: without it the button shows, disabled, with "not installed on this server", and becomes available by itself once installed.

  **macOS (development):**

  ```sh
  brew install tesseract tesseract-lang     # all ~160 languages, a few hundred MB
  ```

  **Ubuntu (production)** - only the archive's languages:

  ```sh
  sudo apt update
  sudo apt install tesseract-ocr tesseract-ocr-osd \
    tesseract-ocr-nld tesseract-ocr-eng tesseract-ocr-ind tesseract-ocr-msa \
    tesseract-ocr-jav tesseract-ocr-deu tesseract-ocr-fra tesseract-ocr-por \
    tesseract-ocr-lat tesseract-ocr-jpn tesseract-ocr-chi-sim tesseract-ocr-chi-tra
  ```

  The list follows `content/languages.py` (the language of documents and transcripts):

  | Archive | Tesseract | Ubuntu package |
  |---|---|---|
  | Dutch (`nl`) | `nld` | `tesseract-ocr-nld` |
  | English (`en`) | `eng` | `tesseract-ocr-eng` (comes with `tesseract-ocr`) |
  | Indonesian (`id`) | `ind` | `tesseract-ocr-ind` |
  | Malay (`ms`) | `msa` | `tesseract-ocr-msa` |
  | Javanese (`jv`) | `jav` | `tesseract-ocr-jav` |
  | German (`de`) | `deu` | `tesseract-ocr-deu` |
  | French (`fr`) | `fra` | `tesseract-ocr-fra` |
  | Portuguese (`pt`) | `por` | `tesseract-ocr-por` |
  | Latin (`la`) | `lat` | `tesseract-ocr-lat` |
  | Japanese (`ja`) | `jpn` | `tesseract-ocr-jpn` |
  | Chinese (`zh`) | `chi_sim`, `chi_tra` | `tesseract-ocr-chi-sim`, `tesseract-ocr-chi-tra` |

  `tesseract-ocr-osd` detects a page's orientation and script (a photo taken sideways). A language added to `content/languages.py` needs its package here too. Ubuntu ships tesseract 4.1 (22.04) or 5.3 (24.04); both work. A newer 5.x on an older Ubuntu: `ppa:alex-p/tesseract-ocr5` (optional).

### PIP requirements

```sh
python3.14 -m venv .venv
.venv/bin/pip install -r requirements.txt     # includes cmnsd/requirements.txt and pytesseract
```

## Next

1. [Configuration](configuration.md) - the `.env` settings
2. [Web hosting](webhosting.md) - gunicorn, supervisord and nginx
3. [Deploying](deploying.md) - `update.sh` for every update, and the checks
