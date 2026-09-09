from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import BudgetLine


class BudgetLineSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    created_by = UserSerializer(read_only=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = BudgetLine
        fields = [
            "id",
            "project",
            "category",
            "category_display",
            "label",
            "quantity",
            "unit_price",
            "amount",
            "created_at",
            "created_by",
        ]


class BudgetLineCreateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=BudgetLine.CATEGORY_CHOICES)
    label = serializers.CharField(max_length=200)
    quantity = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)


class BudgetSummarySerializer(serializers.Serializer):
    """Une ligne de `GET /api/v1/budgeting/summary/` (voir
    docs/modeles-et-api.md) — pas un `ModelSerializer` : `apps.budgeting` ne
    doit pas exposer `ProjectSerializer` en entier (permissions/membres/notes
    non pertinents ici), juste de quoi identifier le projet et ses totaux."""

    project_id = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    opex_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    capex_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    def get_project_id(self, obj):
        return str(obj["project"].id)

    def get_project_name(self, obj):
        return obj["project"].name
