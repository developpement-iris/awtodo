from django.test import TestCase

from apps.accounts.models import Organisation, User
from apps.dashboards.models import DashboardWidget


class DashboardWidgetManagerTests(TestCase):
    """Régression du gotcha StatusLifecycleModel (voir apps/common/models.py)
    — sans `default_manager_name`/`base_manager_name` explicites sur
    `DashboardWidget.Meta`, un widget "removed" resterait visible via
    `.objects` ou invisible via les relations inverses sur `owner`."""

    def setUp(self):
        self.org = Organisation.objects.create(name="Org Dash")
        self.user = User.objects.create_user(username="dash-owner", organisation=self.org)

    def test_removed_widget_hidden_from_default_manager_visible_in_all_objects(self):
        active = DashboardWidget.objects.create(
            owner=self.user, scope="global", widget_type="defaut", metric_key="task_hours_total"
        )
        removed = DashboardWidget.objects.create(
            owner=self.user, scope="global", widget_type="defaut", metric_key="task_hours_total", status="removed"
        )

        self.assertEqual(list(DashboardWidget.objects.all()), [active])
        self.assertEqual(set(DashboardWidget.all_objects.all()), {active, removed})
        # Relation inverse (`user.dashboard_widgets.all()`) doit elle aussi
        # voir l'historique complet (default_manager_name).
        self.assertEqual(set(self.user.dashboard_widgets.all()), {active, removed})
