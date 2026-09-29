from django.contrib import admin

from .models import CommunicationChannel, CommunicationDelivery, CommunicationMessage, O365Connection


@admin.register(O365Connection)
class O365ConnectionAdmin(admin.ModelAdmin):
    list_display = ("organisation", "is_enabled", "is_configured")
    exclude = ("client_secret",)


@admin.register(CommunicationChannel)
class CommunicationChannelAdmin(admin.ModelAdmin):
    list_display = ("label", "teams_channel_name", "project", "notify_incident_created", "status")
    list_filter = ("status", "notify_incident_created")


@admin.register(CommunicationMessage)
class CommunicationMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "project", "trigger", "status", "created_by", "created_at")
    list_filter = ("trigger", "status")


@admin.register(CommunicationDelivery)
class CommunicationDeliveryAdmin(admin.ModelAdmin):
    list_display = ("message", "channel", "status", "responded_at")
    list_filter = ("status",)
