from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Organisation, Team, TeamMembership, User


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 1
    autocomplete_fields = ("user",)


class TeamAdmin(admin.ModelAdmin):
    inlines = [TeamMembershipInline]
    list_display = ("name", "organisation", "status", "created_by")


admin.site.register(User, UserAdmin)
admin.site.register(Team, TeamAdmin)
admin.site.register(Organisation)
admin.site.register(TeamMembership)
