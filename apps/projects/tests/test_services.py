from django.test import TestCase

from apps.accounts.models import Team, TeamMembership, User
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import (
    ProjectPermissionError,
    ProjectValidationError,
    contributor_projects,
    create_project,
    get_project_permissions,
    get_spec_sections,
    is_project_contributor,
    is_project_member,
    update_project_notepad,
    update_spec_section,
)


class CreateProjectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice")
        self.outsider = User.objects.create_user(username="bob")
        self.team = Team.objects.create(name="Équipe Test")
        TeamMembership.objects.create(team=self.team, user=self.user)

    def test_individual_project_makes_creator_chef_de_projet(self):
        project = create_project(actor=self.user, name="Projet solo", project_type="individuel")

        membership = ProjectMembership.objects.get(project=project, user=self.user)
        self.assertEqual(membership.role, "chef_de_projet")
        self.assertIsNone(project.team)

    def test_collaborative_project_with_valid_team(self):
        project = create_project(
            actor=self.user, name="Projet collab", project_type="collaboratif", team=self.team
        )

        self.assertEqual(project.team, self.team)
        membership = ProjectMembership.objects.get(project=project, user=self.user)
        self.assertEqual(membership.role, "chef_de_projet")

    def test_collaborative_project_without_team_is_rejected(self):
        with self.assertRaises(ProjectValidationError):
            create_project(actor=self.user, name="Projet collab", project_type="collaboratif")

    def test_collaborative_project_with_foreign_team_is_rejected(self):
        with self.assertRaises(ProjectPermissionError):
            create_project(
                actor=self.outsider, name="Projet collab", project_type="collaboratif", team=self.team
            )

    def test_individual_project_with_team_is_rejected(self):
        with self.assertRaises(ProjectValidationError):
            create_project(actor=self.user, name="Projet solo", project_type="individuel", team=self.team)

    def test_unauthenticated_actor_is_rejected(self):
        with self.assertRaises(ProjectPermissionError):
            create_project(actor=None, name="Projet solo", project_type="individuel")

    def test_already_in_production_project_has_no_deadline(self):
        project = create_project(
            actor=self.user, name="Outil déjà live", project_type="individuel", already_in_production=True
        )

        self.assertTrue(project.already_in_production)
        self.assertIsNone(project.deadline)

    def test_already_in_production_with_deadline_is_rejected(self):
        with self.assertRaises(ProjectValidationError):
            create_project(
                actor=self.user,
                name="Contradiction",
                project_type="individuel",
                already_in_production=True,
                deadline="2027-01-01",
            )


class ProjectLecteurRoleTests(TestCase):
    def setUp(self):
        self.chef = User.objects.create_user(username="chef-lect")
        self.reader = User.objects.create_user(username="lecteur-1")
        self.project = Project.objects.create(name="Projet observé", project_type="individuel")
        ProjectMembership.objects.create(project=self.project, user=self.chef, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.reader, role="lecteur")

    def test_lecteur_is_member_but_not_contributor(self):
        self.assertTrue(is_project_member(self.reader, self.project))
        self.assertFalse(is_project_contributor(self.reader, self.project))

    def test_lecteur_can_read_spec_sections(self):
        sections = get_spec_sections(actor=self.reader, project=self.project)
        self.assertEqual(len(sections), 12)

    def test_lecteur_cannot_edit_spec_or_notepad(self):
        with self.assertRaises(ProjectPermissionError):
            update_project_notepad(actor=self.reader, project=self.project, notepad_content="Nope")
        with self.assertRaises(ProjectPermissionError):
            update_spec_section(actor=self.reader, project=self.project, section_key="contexte", content="Nope")

    def test_lecteur_permissions_flags_are_all_false_except_none(self):
        perms = get_project_permissions(self.reader, self.project)
        self.assertFalse(perms["can_contribute"])
        self.assertFalse(perms["can_edit_spec"])
        self.assertFalse(perms["can_edit_notepad"])
        self.assertFalse(perms["can_manage_members"])

    def test_lecteur_project_not_in_contributor_projects(self):
        self.assertNotIn(self.project, contributor_projects(self.reader))
        self.assertIn(self.project, contributor_projects(self.chef))


class UpdateProjectNotepadTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(username="alice")
        self.outsider = User.objects.create_user(username="bob")
        self.project = Project.objects.create(name="Projet solo", project_type="individuel")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def test_member_updates_notepad_content(self):
        updated = update_project_notepad(actor=self.member, project=self.project, notepad_content="Idée en vrac")

        self.assertEqual(updated.notepad_content, "Idée en vrac")
        self.assertIsNotNone(updated.notepad_updated_at)

    def test_outsider_cannot_update_notepad(self):
        with self.assertRaises(ProjectPermissionError):
            update_project_notepad(actor=self.outsider, project=self.project, notepad_content="Intrusion")


class SpecSectionServiceTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(username="carole")
        self.outsider = User.objects.create_user(username="dave")
        self.project = Project.objects.create(name="Projet solo", project_type="individuel")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def test_new_project_has_all_twelve_sections_inactive(self):
        sections = get_spec_sections(actor=self.member, project=self.project)

        self.assertEqual(len(sections), 12)
        self.assertTrue(all(section["is_active"] is False for section in sections))
        self.assertTrue(all(section["content"] == "" for section in sections))

    def test_toggling_a_section_active_does_not_create_others(self):
        update_spec_section(actor=self.member, project=self.project, section_key="objectifs", is_active=True)

        sections = {s["section_key"]: s for s in get_spec_sections(actor=self.member, project=self.project)}

        self.assertTrue(sections["objectifs"]["is_active"])
        self.assertFalse(sections["contexte"]["is_active"])

    def test_unchecking_a_section_preserves_its_content(self):
        update_spec_section(
            actor=self.member, project=self.project, section_key="besoin", is_active=True, content="Le besoin."
        )
        update_spec_section(actor=self.member, project=self.project, section_key="besoin", is_active=False)

        sections = {s["section_key"]: s for s in get_spec_sections(actor=self.member, project=self.project)}

        self.assertFalse(sections["besoin"]["is_active"])
        self.assertEqual(sections["besoin"]["content"], "Le besoin.")

    def test_invalid_section_key_rejected(self):
        with self.assertRaises(ProjectValidationError):
            update_spec_section(actor=self.member, project=self.project, section_key="wrong", is_active=True)

    def test_outsider_cannot_view_sections(self):
        with self.assertRaises(ProjectPermissionError):
            get_spec_sections(actor=self.outsider, project=self.project)

    def test_outsider_cannot_update_section(self):
        with self.assertRaises(ProjectPermissionError):
            update_spec_section(actor=self.outsider, project=self.project, section_key="contexte", is_active=True)
