from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import Team, TeamMembership, User
from apps.projects.models import Project, ProjectMembership
from apps.incidents.models import Incident
from apps.incidents.services import (
    IncidentPermissionError,
    IncidentValidationError,
    add_comment,
    archive_incident,
    assign_incident_to_project,
    cancel_incident,
    claim_incident,
    create_incident,
    get_global_incident_stats,
    get_project_incident_insights,
    reassign_incident_team,
    resolve_incident,
    start_incident,
    update_incident_priority,
    update_incident_description,
)


class IncidentServicesTestCase(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Équipe Test")
        self.member = User.objects.create_user(username="alice")
        self.other_member = User.objects.create_user(username="bob")
        self.outsider = User.objects.create_user(username="carol")
        TeamMembership.objects.create(team=self.team, user=self.member)
        TeamMembership.objects.create(team=self.team, user=self.other_member)

        self.other_team = Team.objects.create(name="Autre équipe")
        self.other_team_member = User.objects.create_user(username="erwan")
        TeamMembership.objects.create(team=self.other_team, user=self.other_team_member)

        self.collab_project = Project.objects.create(
            name="Projet collab", project_type="collaboratif", team=self.team
        )

        self.solo_owner = User.objects.create_user(username="dave")
        self.individual_project = Project.objects.create(name="Projet solo", project_type="individuel")
        ProjectMembership.objects.create(project=self.individual_project, user=self.solo_owner, role="chef_de_projet")

    def make_incident(self, project=None, status="signale"):
        return Incident.objects.create(
            project=project or self.collab_project, title="Erreur 500 en prod", status=status
        )


class CreateIncidentTests(IncidentServicesTestCase):
    def test_group_member_creates_incident(self):
        incident = create_incident(actor=self.member, project=self.collab_project, title="Erreur 500")

        self.assertEqual(incident.status, "signale")

    def test_outsider_cannot_create_incident(self):
        with self.assertRaises(IncidentPermissionError):
            create_incident(actor=self.outsider, project=self.collab_project, title="Erreur 500")

    def test_individual_project_falls_back_to_project_membership(self):
        incident = create_incident(actor=self.solo_owner, project=self.individual_project, title="Bug")

        self.assertEqual(incident.status, "signale")

    def test_non_member_of_individual_project_cannot_create(self):
        with self.assertRaises(IncidentPermissionError):
            create_incident(actor=self.outsider, project=self.individual_project, title="Bug")

    def test_system_call_without_actor_bypasses_group_check(self):
        incident = create_incident(project=self.collab_project, title="Ticket automatique", actor=None)

        self.assertEqual(incident.status, "signale")


class CreateIncidentTeamOnlyTests(IncidentServicesTestCase):
    def test_group_member_creates_team_only_incident(self):
        incident = create_incident(actor=self.member, team=self.team, title="Panne réseau")

        self.assertIsNone(incident.project)
        self.assertEqual(incident.team, self.team)
        self.assertEqual(incident.status, "signale")

    def test_outsider_cannot_create_team_only_incident(self):
        with self.assertRaises(IncidentPermissionError):
            create_incident(actor=self.outsider, team=self.team, title="Panne réseau")

    def test_both_project_and_team_provided_ignores_team(self):
        # Les deux peuvent être légitimement connus à la création (ex.
        # l'outil de ticketing connaît le projet et son groupe) — `team` est
        # alors redondant avec `Project.team` et silencieusement ignoré,
        # pas une erreur (session du 2026-09-25).
        incident = create_incident(
            actor=self.member, project=self.collab_project, team=self.team, title="Panne réseau"
        )

        self.assertEqual(incident.project, self.collab_project)
        self.assertIsNone(incident.team)

    def test_team_ignored_even_if_it_differs_from_the_project_team(self):
        # Comportement volontairement choisi côté "ignorer", pas "valider la
        # cohérence" — même un groupe qui ne correspond pas à celui du
        # projet est simplement écarté, pas une erreur.
        other_team = Team.objects.create(name="Groupe non lié")
        TeamMembership.objects.create(team=other_team, user=self.member)

        incident = create_incident(
            actor=self.member, project=self.collab_project, team=other_team, title="Panne réseau"
        )

        self.assertEqual(incident.project, self.collab_project)
        self.assertIsNone(incident.team)

    def test_neither_project_nor_team_is_rejected(self):
        with self.assertRaises(IncidentValidationError):
            create_incident(actor=self.member, title="Panne réseau")

    def test_system_call_with_team_only_bypasses_group_check(self):
        incident = create_incident(team=self.team, title="Ticket automatique", actor=None)

        self.assertIsNone(incident.project)
        self.assertEqual(incident.team, self.team)


class AssignIncidentToProjectTests(IncidentServicesTestCase):
    def make_team_only_incident(self, status="signale"):
        return Incident.objects.create(team=self.team, title="Panne réseau", status=status)

    def test_team_member_assigns_to_project_they_belong_to(self):
        incident = self.make_team_only_incident()

        assign_incident_to_project(actor=self.member, incident=incident, project=self.collab_project)

        incident.refresh_from_db()
        self.assertEqual(incident.project, self.collab_project)
        self.assertIsNone(incident.team)

    def test_team_member_cannot_assign_to_project_they_dont_belong_to(self):
        incident = self.make_team_only_incident()

        with self.assertRaises(IncidentPermissionError):
            assign_incident_to_project(actor=self.member, incident=incident, project=self.individual_project)

    def test_non_member_of_source_team_cannot_assign(self):
        incident = self.make_team_only_incident()

        with self.assertRaises(IncidentPermissionError):
            assign_incident_to_project(actor=self.outsider, incident=incident, project=self.collab_project)

    def test_cannot_assign_incident_that_already_has_a_project(self):
        incident = self.make_incident()

        with self.assertRaises(IncidentValidationError):
            assign_incident_to_project(actor=self.member, incident=incident, project=self.individual_project)


class ReassignIncidentTeamTests(IncidentServicesTestCase):
    def make_team_only_incident(self, status="signale"):
        return Incident.objects.create(team=self.team, title="Panne réseau", status=status)

    def test_source_team_member_reassigns_to_another_team(self):
        incident = self.make_team_only_incident()
        # Doit aussi être membre de l'équipe de destination (même garde que
        # `assign_incident_to_project`) — `self.member` n'appartient qu'à
        # `self.team` par défaut.
        TeamMembership.objects.create(team=self.other_team, user=self.member)

        reassign_incident_team(actor=self.member, incident=incident, team=self.other_team)

        incident.refresh_from_db()
        self.assertEqual(incident.team, self.other_team)
        self.assertIsNone(incident.project)

    def test_non_member_of_source_team_cannot_reassign(self):
        incident = self.make_team_only_incident()

        with self.assertRaises(IncidentPermissionError):
            reassign_incident_team(actor=self.outsider, incident=incident, team=self.other_team)

    def test_cannot_reassign_to_a_team_actor_does_not_belong_to(self):
        incident = self.make_team_only_incident()

        with self.assertRaises(IncidentPermissionError):
            reassign_incident_team(actor=self.member, incident=incident, team=Team.objects.create(name="Équipe fermée"))

    def test_cannot_reassign_incident_already_attached_to_a_project(self):
        incident = self.make_incident()

        with self.assertRaises(IncidentValidationError):
            reassign_incident_team(actor=self.member, incident=incident, team=self.other_team)


class StartIncidentTests(IncidentServicesTestCase):
    def test_any_group_member_can_start(self):
        incident = self.make_incident(status="signale")

        start_incident(actor=self.other_member, incident=incident)

        self.assertEqual(incident.status, "en_cours")

    def test_outsider_cannot_start(self):
        incident = self.make_incident(status="signale")

        with self.assertRaises(IncidentPermissionError):
            start_incident(actor=self.outsider, incident=incident)

    def test_cannot_start_from_wrong_status(self):
        incident = self.make_incident(status="en_cours")

        with self.assertRaises(IncidentValidationError):
            start_incident(actor=self.member, incident=incident)


class ResolveIncidentTests(IncidentServicesTestCase):
    def test_any_group_member_can_resolve(self):
        incident = self.make_incident(status="en_cours")

        resolve_incident(
            actor=self.other_member, incident=incident, resolution_comment="Corrigé.", time_spent="2"
        )

        self.assertEqual(incident.status, "resolu")
        self.assertEqual(incident.resolution_comment, "Corrigé.")
        self.assertEqual(incident.time_spent, Decimal("2"))

    def test_outsider_cannot_resolve(self):
        incident = self.make_incident(status="en_cours")

        with self.assertRaises(IncidentPermissionError):
            resolve_incident(
                actor=self.outsider, incident=incident, resolution_comment="Corrigé.", time_spent="1"
            )

    def test_cannot_resolve_from_wrong_status(self):
        incident = self.make_incident(status="signale")

        with self.assertRaises(IncidentValidationError):
            resolve_incident(
                actor=self.member, incident=incident, resolution_comment="Corrigé.", time_spent="1"
            )

    def test_resolution_comment_is_required(self):
        incident = self.make_incident(status="en_cours")

        with self.assertRaises(IncidentValidationError):
            resolve_incident(actor=self.member, incident=incident, resolution_comment="   ", time_spent="1")

    def test_time_spent_is_required(self):
        incident = self.make_incident(status="en_cours")

        with self.assertRaises(IncidentValidationError):
            resolve_incident(
                actor=self.member, incident=incident, resolution_comment="Corrigé.", time_spent=None
            )

    def test_time_spent_must_be_positive(self):
        incident = self.make_incident(status="en_cours")

        with self.assertRaises(IncidentValidationError):
            resolve_incident(
                actor=self.member, incident=incident, resolution_comment="Corrigé.", time_spent="0"
            )


class ArchiveIncidentTests(IncidentServicesTestCase):
    def test_any_group_member_can_archive(self):
        incident = self.make_incident(status="resolu")

        archive_incident(actor=self.other_member, incident=incident)

        self.assertEqual(incident.status, "archive")

    def test_outsider_cannot_archive(self):
        incident = self.make_incident(status="resolu")

        with self.assertRaises(IncidentPermissionError):
            archive_incident(actor=self.outsider, incident=incident)

    def test_cannot_archive_from_wrong_status(self):
        incident = self.make_incident(status="signale")

        with self.assertRaises(IncidentValidationError):
            archive_incident(actor=self.member, incident=incident)


class CancelIncidentTests(IncidentServicesTestCase):
    def test_group_member_cancels_with_reason(self):
        incident = self.make_incident(status="en_cours")

        cancel_incident(actor=self.other_member, incident=incident, cancellation_reason="Doublon")

        self.assertEqual(incident.status, "annule")
        self.assertEqual(incident.cancellation_reason, "Doublon")

    def test_cancel_requires_reason(self):
        incident = self.make_incident(status="signale")

        with self.assertRaises(IncidentValidationError):
            cancel_incident(actor=self.member, incident=incident, cancellation_reason="")

    def test_outsider_cannot_cancel(self):
        incident = self.make_incident(status="signale")

        with self.assertRaises(IncidentPermissionError):
            cancel_incident(actor=self.outsider, incident=incident, cancellation_reason="Non merci")

    def test_cannot_cancel_resolved_incident(self):
        incident = self.make_incident(status="resolu")

        with self.assertRaises(IncidentValidationError):
            cancel_incident(actor=self.member, incident=incident, cancellation_reason="Trop tard")


class AddCommentTests(IncidentServicesTestCase):
    def test_group_member_can_comment(self):
        incident = self.make_incident()

        comment = add_comment(actor=self.other_member, incident=incident, content="Ça repart en prod ?")

        self.assertEqual(comment.author, self.other_member)
        self.assertEqual(comment.incident, incident)
        self.assertEqual(incident.comments.count(), 1)

    def test_outsider_cannot_comment(self):
        incident = self.make_incident()

        with self.assertRaises(IncidentPermissionError):
            add_comment(actor=self.outsider, incident=incident, content="Je regarde")

    def test_empty_comment_is_rejected(self):
        incident = self.make_incident()

        with self.assertRaises(IncidentValidationError):
            add_comment(actor=self.member, incident=incident, content="   ")


class UpdateIncidentDescriptionTests(IncidentServicesTestCase):
    def test_group_member_updates_description(self):
        incident = self.make_incident()

        update_incident_description(actor=self.member, incident=incident, description="Nouvelle description")

        self.assertEqual(incident.description, "Nouvelle description")

    def test_update_trims_whitespace(self):
        incident = self.make_incident()

        update_incident_description(actor=self.member, incident=incident, description="  avec espaces  ")

        self.assertEqual(incident.description, "avec espaces")

    def test_empty_description_is_allowed(self):
        incident = self.make_incident()

        update_incident_description(actor=self.member, incident=incident, description="")

        self.assertEqual(incident.description, "")

    def test_outsider_cannot_update_description(self):
        incident = self.make_incident()

        with self.assertRaises(IncidentPermissionError):
            update_incident_description(actor=self.outsider, incident=incident, description="Nouvelle description")


class ClaimIncidentTests(IncidentServicesTestCase):
    def test_group_member_claims_incident(self):
        incident = self.make_incident()

        claim_incident(actor=self.member, incident=incident)

        self.assertEqual(incident.assigned_to, self.member)

    def test_claiming_again_reassigns_to_new_claimant(self):
        incident = self.make_incident()
        claim_incident(actor=self.member, incident=incident)

        claim_incident(actor=self.other_member, incident=incident)

        self.assertEqual(incident.assigned_to, self.other_member)

    def test_outsider_cannot_claim(self):
        incident = self.make_incident()

        with self.assertRaises(IncidentPermissionError):
            claim_incident(actor=self.outsider, incident=incident)


class UpdateIncidentPriorityTests(IncidentServicesTestCase):
    def test_assignee_can_change_priority(self):
        incident = self.make_incident()
        claim_incident(actor=self.member, incident=incident)

        update_incident_priority(actor=self.member, incident=incident, priority="critique")

        self.assertEqual(incident.priority, "critique")

    def test_group_member_who_is_not_assignee_or_admin_cannot_change_priority(self):
        incident = self.make_incident()
        claim_incident(actor=self.member, incident=incident)

        with self.assertRaises(IncidentPermissionError):
            update_incident_priority(actor=self.other_member, incident=incident, priority="critique")

    def test_team_creator_can_change_priority_without_being_assigned(self):
        admin = User.objects.create_user(username="team-creator")
        self.team.created_by = admin
        self.team.save(update_fields=["created_by"])
        TeamMembership.objects.create(team=self.team, user=admin)
        incident = self.make_incident()
        claim_incident(actor=self.member, incident=incident)

        update_incident_priority(actor=admin, incident=incident, priority="critique")

        self.assertEqual(incident.priority, "critique")

    def test_platform_admin_can_change_priority_without_being_assigned(self):
        platform_admin = User.objects.create_user(username="platform-admin", is_platform_admin=True)
        incident = self.make_incident()
        claim_incident(actor=self.member, incident=incident)

        update_incident_priority(actor=platform_admin, incident=incident, priority="basse")

        self.assertEqual(incident.priority, "basse")

    def test_outsider_cannot_change_priority(self):
        incident = self.make_incident()

        with self.assertRaises(IncidentPermissionError):
            update_incident_priority(actor=self.outsider, incident=incident, priority="critique")

    def test_individual_project_manager_can_change_priority_without_being_assigned(self):
        incident = create_incident(actor=self.solo_owner, project=self.individual_project, title="Bug")

        update_incident_priority(actor=self.solo_owner, incident=incident, priority="critique")

        self.assertEqual(incident.priority, "critique")

    def test_individual_project_non_manager_member_cannot_change_priority(self):
        other_member = User.objects.create_user(username="solo-other")
        ProjectMembership.objects.create(project=self.individual_project, user=other_member, role="membre")
        incident = create_incident(actor=self.solo_owner, project=self.individual_project, title="Bug")

        with self.assertRaises(IncidentPermissionError):
            update_incident_priority(actor=other_member, incident=incident, priority="critique")


class IncidentInsightsServiceTests(TestCase):
    """Nouvelles fonctions de stats (session du 2026-10-01, module
    Dashboard) — cette app n'avait jusque-là aucune agrégation."""

    def setUp(self):
        self.team = Team.objects.create(name="Équipe Insights")
        self.manager = User.objects.create_user(username="insights-inc-manager")
        self.member = User.objects.create_user(username="insights-inc-member")
        self.outsider = User.objects.create_user(username="insights-inc-outsider")
        TeamMembership.objects.create(team=self.team, user=self.manager)
        TeamMembership.objects.create(team=self.team, user=self.member)
        self.project = Project.objects.create(
            name="Projet Insights Incidents", project_type="collaboratif", team=self.team
        )
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def test_empty_project_has_no_mttr_and_no_division_crash(self):
        insights = get_project_incident_insights(actor=self.manager, project=self.project)
        self.assertIsNone(insights["mttr_hours"])
        self.assertIsNone(insights["cancellation_rate"])
        self.assertEqual(insights["open_count"], 0)

    def test_mttr_averages_time_spent_on_resolved_only(self):
        a = create_incident(actor=self.manager, project=self.project, title="A")
        start_incident(actor=self.manager, incident=a)
        resolve_incident(actor=self.manager, incident=a, resolution_comment="fait", time_spent="2.0")

        b = create_incident(actor=self.manager, project=self.project, title="B")
        start_incident(actor=self.manager, incident=b)
        resolve_incident(actor=self.manager, incident=b, resolution_comment="fait", time_spent="4.0")

        # Toujours signalé, ne doit pas entrer dans le calcul du MTTR.
        create_incident(actor=self.manager, project=self.project, title="C")

        insights = get_project_incident_insights(actor=self.manager, project=self.project)
        self.assertEqual(insights["mttr_hours"], 3.0)
        self.assertEqual(insights["resolved_count"], 2)
        # "résolu" fait partie de `Incident.ACTIVE_STATUSES` (pas encore
        # archivé/annulé) — les 2 résolus + le signalé comptent comme
        # "ouverts" au sens de ce champ.
        self.assertEqual(insights["open_count"], 3)

    def test_cancellation_rate(self):
        cancelled = create_incident(actor=self.manager, project=self.project, title="Annulé")
        cancel_incident(actor=self.manager, incident=cancelled, cancellation_reason="doublon")
        create_incident(actor=self.manager, project=self.project, title="Toujours ouvert")

        insights = get_project_incident_insights(actor=self.manager, project=self.project)
        self.assertAlmostEqual(insights["cancellation_rate"], 0.5)

    def test_plain_member_can_view_project_insights(self):
        insights = get_project_incident_insights(actor=self.member, project=self.project)
        self.assertIn("mttr_hours", insights)

    def test_outsider_cannot_view_project_insights(self):
        with self.assertRaises(IncidentPermissionError):
            get_project_incident_insights(actor=self.outsider, project=self.project)

    def test_global_stats_scoped_to_contributor_projects(self):
        create_incident(actor=self.manager, project=self.project, title="Dans le scope")

        other_team = Team.objects.create(name="Autre équipe insights")
        other_manager = User.objects.create_user(username="insights-inc-other-manager")
        TeamMembership.objects.create(team=other_team, user=other_manager)
        other_project = Project.objects.create(
            name="Autre projet insights", project_type="collaboratif", team=other_team
        )
        ProjectMembership.objects.create(project=other_project, user=other_manager, role="chef_de_projet")
        create_incident(actor=other_manager, project=other_project, title="Hors scope")

        stats = get_global_incident_stats(actor=self.manager)
        self.assertEqual(stats["open_count"], 1)
