from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership


class ProjectActiveManagerTests(TestCase):
    def test_active_manager_filters_by_status(self):
        project = Project.objects.create(name="Projet Test")

        self.assertIn(project, Project.objects.active())

        project.status = "archive"
        project.save()

        self.assertNotIn(project, Project.objects.active())
        self.assertIn(project, Project.all_objects.all())


class ProjectMembershipUniquenessTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.user = User.objects.create_user(username="alice")

    def test_duplicate_active_role_is_rejected(self):
        ProjectMembership.objects.create(project=self.project, user=self.user, role="membre")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectMembership.objects.create(project=self.project, user=self.user, role="membre")

    def test_removed_membership_does_not_block_new_active_one(self):
        first = ProjectMembership.objects.create(project=self.project, user=self.user, role="membre")
        first.status = "removed"
        first.save()

        second = ProjectMembership.objects.create(project=self.project, user=self.user, role="membre")

        self.assertIn(second, ProjectMembership.objects.active())
