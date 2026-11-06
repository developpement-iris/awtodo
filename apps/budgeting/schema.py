from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.common.schema import no_body

from .serializers import BudgetLineCreateSerializer, BudgetLineSerializer, BudgetSummarySerializer

budget_schema = extend_schema_view(
    lines=[
        extend_schema(methods=["GET"], responses=BudgetLineSerializer(many=True)),
        extend_schema(methods=["POST"], request=BudgetLineCreateSerializer, responses={201: BudgetLineSerializer}),
    ],
    remove=no_body(BudgetLineSerializer),
    summary=extend_schema(responses=BudgetSummarySerializer(many=True)),
)
