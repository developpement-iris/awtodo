from django.contrib import admin

from .models import DocEntry, DocPage, DocSpace, PendingDocEntry

admin.site.register([DocSpace, DocPage, DocEntry, PendingDocEntry])
