# Install FMLY on a brand new environment

## Requirements
This instruction assumes you have a Linux environment with Nginx and Supervisor. 
In the examples, Ubuntu is used.

## Create location for application
This instruction assumes you want to host your files from /data/www. However, this may
change according to your setup and personal preferences.

> mkdir -p /data/www/fmly.com
> cd /data/www/fmly.com

## Virtual Environment
Set up a virtual environment using Python3's venv. The virtual environment is a 
closed off segment where changes in the Python environment are contained. This means
that installed modules only are available within this virtual environment.
This ensures you can upgrade environments per environment.

> $ python3 -m venv ~/.venv/fmly

This creates the required files for your virtual environment in your homedirectory. 
Alternatively, you can choose any location to store your virtual environment in.

To activate this virtual environment, launch
> $ source ~/.venv/fmly/bin/activate

The command line will now start with the name of your virtual environment:
> (fmly) $

From now on, the python version is set to the version in your virtual environment. So you
no longer have to use 'python3' but can use the 'python' command. 

In this documentation, you will notice sometimes the virtual environment is mentioned before the
command, and other times it is not. Whenever it is mentioned, make sure you are in the virtual
environment. When it is not mentioned, the virtual environment is not required for this step, but
you do not need to deactivate it to proceed.

## Install modules within your virtual environment
Install the Python dependancies within the virtual environment,

> (fmly) $ python -m pip install django gunicorn markdown pillow django-sendfile2

A per-module explenation of what to install:
- django: the Django framework (https://www.djangoproject.com/)
- gunicorn: A Python WSGI HTTP server (https://gunicorn.org/)
- markdown: support for Markdown text to html (https://python-markdown.github.io/)
- pillow: Python Image Library, used to create thumbnails and get image information (https://pillow.readthedocs.io/en/stable/)
- django-sendfile2: Used for serving attachments after user verification (https://pypi.org/project/django-sendfile2/)

## Install FMLY codebase
> $ git clone https://github.com/arnecoomans/fmly.git .

## Create settings file
## Execute Database Migrations
Create the database and database structure based on de Migrations. 
> (fmly) $ python manage.py migrate
This should trigger a lot of migrations creating the proper database structure.

## Create a superuser in the Django application
Use the manage.py script to create a user that has access to the site, admin and starts off with 
all user rights. You will need this user to access and set up the site.

> (fmly) $ python manage.py createsuperuser
Enter your preferred username (avoid 'admin') and a safe password.

## (Optional): test using runserver
> (fmly) $ python manage.py check

## Set up Gunicorn script
In .documentation/examples you will find an example gunicorn script. Copy this script to ./gunicorn
and correct the example values to your actual values. Then make the script executable.

> $ cp documentation/examples/example_gunicorn gunicorn/gunicorn
> $ chmod +x gunicorn/gunicorn

## Set up Supervisor conf file
In .documentation/examples you will find an example supervisor configuration script. Copy this
script to the supervisor conf-directory as root and correct the example values to your actual values.

> $ sudo cp documentation/examples/example_supervisor.conf /etc/supervisor/conf.d/fmly.conf
> $ sudo supervisorctl reread
> $ sudo supervisorctl reload
> $ sudo supervisorctl start fmly

## Set up Nginx host

## Use Let's Encrypt for HTTPS-Certificate

## Update Django
## Update Fmly
