from django.test import TestCase

from apps.accounts.models import User
from apps.documentation import services
from apps.documentation.models import DocSpace
from apps.documentation.services import DocsPermissionError
from apps.projects.models import Project, ProjectMembership


class PublicLinkServiceTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create(username="mgr")
        self.member = User.objects.create(username="mbr")
        self.outsider = User.objects.create(username="out")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def test_get_or_create_space_idempotent_for_member(self):
        s1 = services.get_or_create_space(actor=self.member, project=self.project)
        s2 = services.get_or_create_space(actor=self.manager, project=self.project)
        self.assertEqual(s1.pk, s2.pk)
        self.assertEqual(DocSpace.objects.count(), 1)

    def test_outsider_denied(self):
        with self.assertRaises(DocsPermissionError):
            services.get_or_create_space(actor=self.outsider, project=self.project)

    def test_enable_only_for_manager(self):
        with self.assertRaises(DocsPermissionError):
            services.enable_public_link(actor=self.member, project=self.project)
        space = services.enable_public_link(actor=self.manager, project=self.project)
        self.assertTrue(space.is_public)
        self.assertTrue(space.public_token)

    def test_rotate_changes_token(self):
        s = services.enable_public_link(actor=self.manager, project=self.project)
        old = s.public_token
        s = services.rotate_public_link(actor=self.manager, project=self.project)
        self.assertNotEqual(s.public_token, old)

    def test_revoke_clears_token(self):
        services.enable_public_link(actor=self.manager, project=self.project)
        s = services.revoke_public_link(actor=self.manager, project=self.project)
        self.assertIsNone(s.public_token)
        self.assertFalse(s.is_public)


class DocPageServiceTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create(username="mgr")
        self.member = User.objects.create(username="mbr")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def test_create_page_unique_slug(self):
        p1 = services.create_page(actor=self.manager, project=self.project, title="Prise en main")
        p2 = services.create_page(actor=self.manager, project=self.project, title="Prise en main")
        self.assertEqual(p1.slug, "prise-en-main")
        self.assertEqual(p2.slug, "prise-en-main-2")

    def test_member_cannot_create(self):
        with self.assertRaises(services.DocsPermissionError):
            services.create_page(actor=self.member, project=self.project, title="X")

    def test_publish_unpublish(self):
        p = services.create_page(actor=self.manager, project=self.project, title="X")
        self.assertEqual(p.status, "brouillon")
        p = services.publish_page(actor=self.manager, project=self.project, page_id=p.id)
        self.assertEqual(p.status, "publie")
        p = services.unpublish_page(actor=self.manager, project=self.project, page_id=p.id)
        self.assertEqual(p.status, "brouillon")

    def test_archive_reparents_children(self):
        parent = services.create_page(actor=self.manager, project=self.project, title="Parent")
        child = services.create_page(actor=self.manager, project=self.project, title="Enfant", parent_id=parent.id)
        services.archive_page(actor=self.manager, project=self.project, page_id=parent.id)
        child.refresh_from_db()
        self.assertIsNone(child.parent_id)

    def test_third_level_rejected(self):
        a = services.create_page(actor=self.manager, project=self.project, title="A")
        b = services.create_page(actor=self.manager, project=self.project, title="B", parent_id=a.id)
        with self.assertRaises(services.DocsValidationError):
            services.create_page(actor=self.manager, project=self.project, title="C", parent_id=b.id)

    def test_update_rejects_cycle(self):
        a = services.create_page(actor=self.manager, project=self.project, title="A")
        b = services.create_page(actor=self.manager, project=self.project, title="B", parent_id=a.id)
        with self.assertRaises(services.DocsValidationError):
            services.update_page(actor=self.manager, project=self.project, page_id=a.id, parent_id=b.id)


class DocEntryServiceTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create(username="mgr")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")

    def test_create_and_publish_feature(self):
        f = services.create_entry(actor=self.manager, project=self.project, kind="fonctionnalite", title="Export Excel")
        self.assertEqual(f.status, "brouillon")
        self.assertEqual(f.kind, "fonctionnalite")
        f = services.publish_entry(actor=self.manager, project=self.project, entry_id=f.id)
        self.assertEqual(f.status, "publie")

    def test_seed_from_spec_one_per_block_no_dup(self):
        from apps.projects.models import SpecSection
        SpecSection.objects.create(
            project=self.project, section_key="exigences_fonctionnelles", is_active=True,
            content="- Export Excel des tâches\n\n- Filtre par priorité multi-sélection\n",
        )
        created = services.seed_features_from_spec(actor=self.manager, project=self.project)
        self.assertEqual(len(created), 2)
        self.assertTrue(all(e.kind == "fonctionnalite" for e in created))
        self.assertEqual(services.seed_features_from_spec(actor=self.manager, project=self.project), [])

    def test_seed_empty_raises(self):
        with self.assertRaises(services.DocsValidationError):
            services.seed_features_from_spec(actor=self.manager, project=self.project)


class PendingDocEntryServiceTests(TestCase):
    def setUp(self):
        from apps.projects.models import ProjectVersion
        from apps.tasks.models import Task
        self.mgr = User.objects.create(username="mgr")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.mgr, role="chef_de_projet")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.space = services.get_or_create_space(actor=self.mgr, project=self.project)
        self.task = Task.objects.create(project=self.project, version=self.version, title="Export Excel",
                                        description="Exporte la liste.", task_type="ajout", status="archivee")
        from apps.documentation.models import PendingDocEntry
        self.pending = PendingDocEntry.objects.create(space=self.space, task=self.task, kind="fonctionnalite")

    def test_create_entry_from_pending(self):
        e = services.create_entry_from_pending(actor=self.mgr, project=self.project, pending_id=self.pending.id)
        self.assertEqual(e.title, "Export Excel")
        self.assertEqual(e.kind, "fonctionnalite")
        self.assertEqual(e.source, "tache")
        self.assertEqual(e.source_task_id, self.task.id)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "traitee")

    def test_create_entry_from_pending_carries_task_version(self):
        e = services.create_entry_from_pending(actor=self.mgr, project=self.project, pending_id=self.pending.id)
        self.assertEqual(e.version_id, self.version.id)

    def test_ignore_pending(self):
        services.ignore_pending(actor=self.mgr, project=self.project, pending_id=self.pending.id)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "ignoree")


class DocEntryVersionServiceTests(TestCase):
    def setUp(self):
        from apps.projects.models import ProjectVersion
        self.manager = User.objects.create(username="mgr")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        self.v1 = ProjectVersion.objects.create(project=self.project, label="v1", is_current=False)
        self.v2 = ProjectVersion.objects.create(project=self.project, label="v2", is_current=True)

    def test_update_entry_sets_version(self):
        e = services.create_entry(actor=self.manager, project=self.project, kind="fonctionnalite", title="X")
        e = services.update_entry(actor=self.manager, project=self.project, entry_id=e.id, version=self.v1)
        self.assertEqual(e.version_id, self.v1.id)

    def test_update_entry_detaches_version_with_explicit_none(self):
        e = services.create_entry(actor=self.manager, project=self.project, kind="fonctionnalite", title="X")
        e = services.update_entry(actor=self.manager, project=self.project, entry_id=e.id, version=self.v1)
        e = services.update_entry(actor=self.manager, project=self.project, entry_id=e.id, version=None)
        self.assertIsNone(e.version_id)

    def test_update_entry_without_version_kwarg_leaves_it_untouched(self):
        e = services.create_entry(actor=self.manager, project=self.project, kind="fonctionnalite", title="X")
        e = services.update_entry(actor=self.manager, project=self.project, entry_id=e.id, version=self.v1)
        e = services.update_entry(actor=self.manager, project=self.project, entry_id=e.id, title="Y")
        self.assertEqual(e.version_id, self.v1.id)


class ContributorsEntryServiceTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create(username="mgr", first_name="Ada", last_name="Lovelace")
        self.member = User.objects.create(username="mbr", first_name="Alan", last_name="Turing")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def test_generate_contributors_entry_lists_active_members(self):
        entry = services.generate_contributors_entry(actor=self.manager, project=self.project)
        self.assertEqual(entry.kind, "contributeurs")
        self.assertIn("Ada Lovelace", entry.description)
        self.assertIn("Alan Turing", entry.description)

    def test_generate_contributors_entry_is_idempotent_single_row(self):
        from apps.documentation.models import DocEntry
        services.generate_contributors_entry(actor=self.manager, project=self.project)
        services.generate_contributors_entry(actor=self.manager, project=self.project)
        self.assertEqual(DocEntry.all_objects.filter(kind="contributeurs").count(), 1)

    def test_regenerating_reflects_membership_changes(self):
        from apps.projects.models import ProjectMembership
        from apps.projects.services import remove_project_member
        entry = services.generate_contributors_entry(actor=self.manager, project=self.project)
        self.assertIn("Alan Turing", entry.description)
        membership = ProjectMembership.objects.get(project=self.project, user=self.member)
        remove_project_member(actor=self.manager, membership=membership)
        entry = services.generate_contributors_entry(actor=self.manager, project=self.project)
        self.assertNotIn("Alan Turing", entry.description)

    def test_member_cannot_generate(self):
        with self.assertRaises(services.DocsPermissionError):
            services.generate_contributors_entry(actor=self.member, project=self.project)


class PublicLinkSlugServiceTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create(username="mgr")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")

    def test_set_slug_before_link_enabled(self):
        space = services.set_public_slug(actor=self.manager, project=self.project, slug="Mon Projet !")
        self.assertEqual(space.custom_slug, "mon-projet")
        self.assertFalse(space.public_token)  # pas encore de lien actif, rien à régénérer

    def test_set_slug_regenerates_active_token_with_prefix(self):
        services.enable_public_link(actor=self.manager, project=self.project)
        space = services.set_public_slug(actor=self.manager, project=self.project, slug="mon-projet")
        self.assertTrue(space.public_token.startswith("mon-projet-"))

    def test_clearing_slug_removes_prefix_on_next_rotation(self):
        services.enable_public_link(actor=self.manager, project=self.project)
        services.set_public_slug(actor=self.manager, project=self.project, slug="mon-projet")
        space = services.set_public_slug(actor=self.manager, project=self.project, slug="")
        self.assertFalse(space.public_token.startswith("mon-projet"))


class SpaceAppearanceServiceTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create(username="mgr")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")

    def test_update_appearance_partial(self):
        space = services.update_space_appearance(actor=self.manager, project=self.project, accent_color="#7A4F9E")
        self.assertEqual(space.accent_color, "#7A4F9E")
        self.assertEqual(space.header_content, "")

        space = services.update_space_appearance(actor=self.manager, project=self.project, header_content="Bienvenue")
        self.assertEqual(space.accent_color, "#7A4F9E")  # non touché par cet appel
        self.assertEqual(space.header_content, "Bienvenue")
