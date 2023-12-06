# CMNS FMLY
Fmly is an annotated photodump, used to create some structure in a vast set of historic family-documents such as photos, news-articles and other snippets of data.

https://github.com/arnecoomans/fmly/
Twitter: @arnecoomans
Mastodon: [@Arnecoomans@Mastodon.Social](https://mastodon.social/@ArneCoomans)

## Features

### Images
Upload images and share with your family. Tag people related to the images, use tags to describe the image and use groups to group images that are alike. Add attachments with more details. Comment.

### User rights
Assign user rights to view people, tags, comments or notes. If something cannot be accessed, the references to that object are also hidden.
User rights are best stored in groups. At least two groups are recommended: read-only and write-access.

### People
An image can be tagged with displayed people. This adds some relevant context to a image, and it is easy to find other images with this person.
Parents can be linked, so the family relations and family tree can be built two ways, one generation up and down when viewing a person.

### Dating
When a date is known for an image, this information makes it easy to find other images around the same time period. Decades are used.

## Installation
Fmly is developed for a linux-environment.

In the home-directory of the project, install the required python modules.
First, activate a virtual environment
'''
python -m venv ~/.venv/fmly
source ~/.venv/fmly/bin/activate

'''
$ python -m pip install -r requirements.txt
'''

Clone the git project to this location
'''
$ git clone https://github.com/arnecoomans/fmly.git .
'''

Create a settings.py file in /family
[@todo add settings template]


Apply database migrations
'''
$ python manage.py migrate
'''

Collect static files
'''
$ python manage.py collectstatic
yes
'''

[@todo setup vhost]
[@todo setup LetsEncrypt]
[@todo setup gunicorn]
[@todo setup supervisor]
