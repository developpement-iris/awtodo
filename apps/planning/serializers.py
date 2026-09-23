from rest_framework import serializers

from apps.accounts.models import User
from apps.incidents.models import Incident
from apps.tasks.models import Task

from .models import ProjectPlanningEntry


class _AtLeastOneFieldSerializer(serializers.Serializer):
    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Aucun champ à mettre à jour.")
        return attrs


class EventCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    location = serializers.CharField(required=False, allow_blank=True, default="")
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    all_day = serializers.BooleanField(required=False, default=False)
    recurrence_rule = serializers.CharField(required=False, allow_blank=True, default="")
    # Participants ajoutés dès la création (session du 2026-09-23) — évite
    # l'aller-retour "créer, ré-ouvrir, ajouter un participant". Optionnel,
    # réutilise `add_participant` un par un côté service : mêmes règles
    # (l'organisateur ne peut pas s'ajouter lui-même), même synchro Outlook
    # par participant (un participant invité dès la création déclenche
    # exactement le même signal `event_participant_invited` qu'un ajouté
    # après coup).
    participant_ids = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(queryset=User.objects.all()),
        required=False,
        default=list,
    )


class EventUpdateSerializer(_AtLeastOneFieldSerializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True)
    start = serializers.DateTimeField(required=False)
    end = serializers.DateTimeField(required=False)
    all_day = serializers.BooleanField(required=False)
    recurrence_rule = serializers.CharField(required=False, allow_blank=True)


class ParticipantAddSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())


class RespondSerializer(serializers.Serializer):
    response = serializers.ChoiceField(choices=["accepte", "refuse"])


class BlockCreateSerializer(serializers.Serializer):
    task = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(), required=False, allow_null=True
    )
    incident = serializers.PrimaryKeyRelatedField(
        queryset=Incident.objects.all(), required=False, allow_null=True
    )
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()


class BlockUpdateSerializer(_AtLeastOneFieldSerializer):
    start = serializers.DateTimeField(required=False)
    end = serializers.DateTimeField(required=False)


class ProjectEntryCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    kind = serializers.ChoiceField(choices=ProjectPlanningEntry.KIND_CHOICES, required=False, default="autre")
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    all_day = serializers.BooleanField(required=False, default=False)
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    recurrence_rule = serializers.CharField(required=False, allow_blank=True, default="")


class ProjectEntryUpdateSerializer(_AtLeastOneFieldSerializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    kind = serializers.ChoiceField(choices=ProjectPlanningEntry.KIND_CHOICES, required=False)
    start = serializers.DateTimeField(required=False)
    end = serializers.DateTimeField(required=False)
    all_day = serializers.BooleanField(required=False)
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    recurrence_rule = serializers.CharField(required=False, allow_blank=True)


class ShareCreateSerializer(serializers.Serializer):
    grantee = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    can_manage_work_hours = serializers.BooleanField(required=False, default=False)


class SharePermissionsUpdateSerializer(serializers.Serializer):
    can_manage_work_hours = serializers.BooleanField()


class WorkingHoursDayInputSerializer(serializers.Serializer):
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    enabled = serializers.BooleanField(required=False, default=True)
    start = serializers.TimeField()
    end = serializers.TimeField()


class WorkingHoursUpdateSerializer(serializers.Serializer):
    days = WorkingHoursDayInputSerializer(many=True)
    # Utilisateur ciblé (délégation) et semaine (exception) — voir
    # `apps.planning.services.update_working_hours`. `user` absent = soi-même.
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    week_start = serializers.DateField(required=False)
