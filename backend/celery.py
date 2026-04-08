from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Postavite podrazumevane postavke Django projekta za Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('backend')

# Koristite postavke iz Django settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatski otkrivajte zadatke u svim aplikacijama koje su registrovane u Django settings
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
