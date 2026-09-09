from django.contrib import admin

from .models import Incident, IncidentComment

admin.site.register(Incident)
admin.site.register(IncidentComment)
