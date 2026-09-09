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
    claim_incident,
    create_incident,
    resolve_incident,
    start_incident,
    update_incident_description,
    update_incident_priority,
)


class IncidentServicesTestCase(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Équipe Test")
        self.member = User.objects.create_user(username="alice")
        self.other_member = User.objects.create_user(username="bob")
        self.outsider = User.objects.create_user(username="carol")
        TeamMembership.objects.create(team=self.team, user=self.member)
        TeamMembership.objects.create(team=self.team, user=self.other_member)

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

    def test_both_project_and_team_is_rejected(self):
        with self.assertRaises(IncidentValidationError):
            create_incident(actor=self.member, project=self.collab_project, team=self.team, title="Panne réseau")

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

        resolve_incident(actor=self.other_member, incident=incident)

        self.assertEqual(incident.status, "resolu")

    def test_outsider_cannot_resolve(self):
        incident = self.make_incident(status="en_cours")

        with self.assertRaises(IncidentPermissionError):
            resolve_incident(actor=self.outsider, incident=incident)

    def test_cannot_resolve_from_wrong_status(self):
        incident = self.make_incident(status="signale")

        with self.assertRaises(IncidentValidationError):
            resolve_incident(actor=self.member, incident=incident)


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
