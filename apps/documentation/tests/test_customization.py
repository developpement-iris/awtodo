from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, User
from apps.common.models import AuditLogEntry
from apps.documentation import services
from apps.documentation.models import DocAttachment, DocSpace
from apps.integrations.services import generate_api_key
from apps.projects.models import Project, ProjectMembership

PDF_BYTES = b"%PDF-1.7 contenu"


class AttachmentFixtureMixin:
    def _set_up_project(self):
        self.manager = User.objects.create(username="chef")
        self.member = User.objects.create(username="membre")
        self.outsider = User.objects.create(username="externe")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.page = services.create_page(actor=self.manager, project=self.project, title="Guide", section="support")

    def _upload(self, filename="notice.pdf", data=PDF_BYTES, page=None):
        return services.upload_attachment(
            actor=self.manager, project=self.project, page_id=(page or self.page).id, filename=filename, data=data
        )


class AttachmentServiceTests(AttachmentFixtureMixin, TestCase):
    def setUp(self):
        self._set_up_project()

    def test_upload_stores_file_with_server_detected_type(self):
        attachment = self._upload()
        self.assertEqual(attachment.filename, "notice.pdf")
        self.assertEqual(attachment.content_type, "application/pdf")
        self.assertEqual(attachment.size, len(PDF_BYTES))
        self.assertEqual(bytes(attachment.data), PDF_BYTES)

    def test_upload_is_audited_on_the_project(self):
        attachment = self._upload()
        entry = AuditLogEntry.objects.get(object_id=attachment.id)
        self.assertEqual(entry.project, self.project)
        self.assertEqual(entry.verb, "created")

    def test_member_cannot_upload(self):
        with self.assertRaises(services.DocsPermissionError):
            services.upload_attachment(
                actor=self.member, project=self.project, page_id=self.page.id, filename="a.pdf", data=PDF_BYTES
            )

    def test_only_support_pages_accept_attachments(self):
        doc_page = services.create_page(actor=self.manager, project=self.project, title="Doc")
        with self.assertRaises(services.DocsValidationError):
            self._upload(page=doc_page)

    def test_archived_page_rejects_attachment(self):
        services.archive_page(actor=self.manager, project=self.project, page_id=self.page.id)
        with self.assertRaises(services.DocsValidationError):
            self._upload()

    def test_rejects_file_over_the_limit(self):
        with self.assertRaises(services.DocsValidationError):
            self._upload(data=b"%PDF-" + b"0" * services.MAX_ATTACHMENT_BYTES)

    def test_rejects_empty_file(self):
        with self.assertRaises(services.DocsValidationError):
            self._upload(data=b"")

    def test_rejects_unlisted_extension(self):
        for filename in ("page.html", "dessin.svg", "script.exe", "sans-extension"):
            with self.assertRaises(services.DocsValidationError, msg=filename):
                self._upload(filename=filename)

    def test_rejects_content_not_matching_extension(self):
        with self.assertRaises(services.DocsValidationError):
            self._upload(filename="notice.pdf", data=b"<html>pas un pdf</html>")

    def test_rejects_binary_disguised_as_text(self):
        with self.assertRaises(services.DocsValidationError):
            self._upload(filename="notes.txt", data=b"MZ\x00\x00\x01")

    def test_accepts_office_and_text_formats(self):
        cases = {
            "a.docx": b"PK\x03\x04rest",
            "a.xlsx": b"PK\x03\x04rest",
            "a.pptx": b"PK\x03\x04rest",
            "a.zip": b"PK\x03\x04rest",
            "a.doc": bytes.fromhex("d0cf11e0a1b11ae1") + b"rest",
            "a.PNG": bytes.fromhex("89504e470d0a1a0a") + b"rest",
            "a.csv": "nom;rôle\n".encode("latin-1"),
            "a.txt": "bonjour".encode(),
        }
        for filename, data in cases.items():
            self.assertEqual(self._upload(filename=filename, data=data).filename, filename)

    def test_filename_keeps_only_the_base_name(self):
        attachment = self._upload(filename="..\\..\\dossier/notice\r\n.pdf")
        self.assertEqual(attachment.filename, "notice.pdf")

    def test_archive_keeps_the_row(self):
        attachment = self._upload()
        services.archive_attachment(
            actor=self.manager, project=self.project, page_id=self.page.id, attachment_id=attachment.id
        )
        self.assertEqual(DocAttachment.all_objects.get(id=attachment.id).status, "archive")
        self.assertFalse(DocAttachment.objects.filter(id=attachment.id).exists())

    def test_bundle_lists_attachments_without_their_bytes(self):
        attachment = self._upload()
        bundle = services.get_documentation_bundle(actor=self.manager, project=self.project)
        listed = bundle["support_pages"][0]["attachments"]
        self.assertEqual([a["id"] for a in listed], [str(attachment.id)])
        self.assertNotIn("data", listed[0])

    def test_bundle_attachment_count_does_not_add_a_query_per_page(self):
        self._upload()
        for index in range(3):
            page = services.create_page(actor=self.manager, project=self.project, title=f"G{index}", section="support")
            self._upload(page=page)
        with self.assertNumQueries(self._bundle_query_count()):
            services.get_documentation_bundle(actor=self.manager, project=self.project)

    def _bundle_query_count(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        other = Project.objects.create(name="Vide", project_type="collaboratif")
        ProjectMembership.objects.create(project=other, user=self.manager, role="chef_de_projet")
        services.create_page(actor=self.manager, project=other, title="Seule", section="support")
        with CaptureQueriesContext(connection) as context:
            services.get_documentation_bundle(actor=self.manager, project=other)
        return len(context)


class PublicAttachmentTests(AttachmentFixtureMixin, TestCase):
    def setUp(self):
        self._set_up_project()
        self.attachment = self._upload()
        self.space = services.enable_public_link(actor=self.manager, project=self.project)

    def _publish(self):
        services.publish_page(actor=self.manager, project=self.project, page_id=self.page.id)

    def test_public_docs_list_attachments_of_published_pages(self):
        self._publish()
        node = services.get_public_docs(self.space.public_token)["support_pages"][0]
        self.assertEqual(node["attachments"][0]["filename"], "notice.pdf")
        self.assertNotIn("data", node["attachments"][0])

    def test_public_download_of_published_page(self):
        self._publish()
        found = services.get_public_attachment(self.space.public_token, self.attachment.id)
        self.assertEqual(bytes(found.data), PDF_BYTES)

    def test_public_download_refused_on_draft_page(self):
        self.assertIsNone(services.get_public_attachment(self.space.public_token, self.attachment.id))

    def test_public_download_refused_once_archived(self):
        self._publish()
        services.archive_attachment(
            actor=self.manager, project=self.project, page_id=self.page.id, attachment_id=self.attachment.id
        )
        self.assertIsNone(services.get_public_attachment(self.space.public_token, self.attachment.id))

    def test_public_download_refused_after_link_revoked(self):
        self._publish()
        token = self.space.public_token
        services.revoke_public_link(actor=self.manager, project=self.project)
        self.assertIsNone(services.get_public_attachment(token, self.attachment.id))

    def test_public_token_of_another_project_cannot_reach_the_file(self):
        self._publish()
        other = Project.objects.create(name="Autre", project_type="collaboratif")
        ProjectMembership.objects.create(project=other, user=self.manager, role="chef_de_projet")
        other_space = services.enable_public_link(actor=self.manager, project=other)
        self.assertIsNone(services.get_public_attachment(other_space.public_token, self.attachment.id))


@override_settings(DEBUG=True)
class AttachmentApiTests(AttachmentFixtureMixin, APITestCase):
    def setUp(self):
        self._set_up_project()
        self.url = f"/api/v1/docs/{self.project.id}/pages/{self.page.id}/attachments/"
        self.admin = User.objects.create(username="admin", organisation_role="admin")
        _, self.raw_key = generate_api_key(actor=self.admin, organisation=self.project.organisation, name="QWEASE")

    def _as(self, user):
        self.client.credentials(HTTP_X_DEBUG_USER_ID=str(user.id))

    def _as_api_key(self, raw_key=None):
        self.client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key or self.raw_key}")

    def _post(self, url=None, name="notice.pdf", data=PDF_BYTES):
        file = SimpleUploadedFile(name, data, content_type="application/octet-stream")
        return self.client.post(url or self.url, {"file": file}, format="multipart")

    def test_manager_uploads_and_downloads(self):
        self._as(self.manager)
        created = self._post()
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["filename"], "notice.pdf")

        response = self.client.get(f"{self.url}{created.data['id']}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PDF_BYTES)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_upload_without_file_is_400(self):
        self._as(self.manager)
        self.assertEqual(self.client.post(self.url, {}, format="multipart").status_code, 400)

    def test_member_gets_403_and_outsider_404(self):
        self._as(self.member)
        self.assertEqual(self._post().status_code, 403)
        self._as(self.outsider)
        self.assertEqual(self._post().status_code, 404)

    def test_delete_archives(self):
        self._as(self.manager)
        attachment_id = self._post().data["id"]
        self.assertEqual(self.client.delete(f"{self.url}{attachment_id}/").status_code, 204)
        self.assertEqual(self.client.get(f"{self.url}{attachment_id}/").status_code, 400)

    def test_api_key_uploads_on_project_of_its_organisation(self):
        self._as_api_key()
        response = self._post()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(DocAttachment.objects.get(id=response.data["id"]).uploaded_by.is_service_account, True)

    def test_api_key_lists_support_pages_to_find_their_ids(self):
        self._upload()
        self._as_api_key()
        response = self.client.get(f"/api/v1/docs/{self.project.id}/support-pages/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], str(self.page.id))
        self.assertEqual(response.data[0]["attachments"][0]["filename"], "notice.pdf")
        self.assertNotIn("content", response.data[0])

    def test_api_key_cannot_reach_a_project_of_another_organisation(self):
        other_org = Organisation.objects.create(name="Autre organisation")
        other_admin = User.objects.create(username="admin2", organisation=other_org, organisation_role="admin")
        _, other_key = generate_api_key(actor=other_admin, organisation=other_org, name="Autre")
        self._as_api_key(other_key)
        self.assertEqual(self._post().status_code, 404)

    def test_api_key_has_no_access_to_the_rest_of_the_documentation(self):
        self._as_api_key()
        base = f"/api/v1/docs/{self.project.id}/"
        self.assertEqual(self.client.get(base).status_code, 404)
        self.assertEqual(self.client.post(f"{base}pages/", {"title": "X"}, format="json").status_code, 404)
        self.assertEqual(self.client.patch(f"{base}appearance/", {"accent_color": ""}, format="json").status_code, 404)

    def test_public_download_endpoint(self):
        attachment = self._upload()
        services.publish_page(actor=self.manager, project=self.project, page_id=self.page.id)
        space = services.enable_public_link(actor=self.manager, project=self.project)
        self.client.credentials()
        response = self.client.get(f"/api/v1/docs/public/{space.public_token}/attachments/{attachment.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PDF_BYTES)
        self.assertIn("attachment", response["Content-Disposition"])

    def test_public_download_of_draft_is_404(self):
        attachment = self._upload()
        space = services.enable_public_link(actor=self.manager, project=self.project)
        self.client.credentials()
        response = self.client.get(f"/api/v1/docs/public/{space.public_token}/attachments/{attachment.id}/")
        self.assertEqual(response.status_code, 404)


class AppearanceServiceTests(AttachmentFixtureMixin, TestCase):
    def setUp(self):
        self._set_up_project()

    def _update(self, **kwargs):
        return services.update_space_appearance(actor=self.manager, project=self.project, **kwargs)

    def test_theme_colors_merge_and_blank_clears_a_zone(self):
        self._update(theme_colors={"sidebar": "#112233", "footer": "#445566"})
        space = self._update(theme_colors={"footer": "", "header": "#778899"})
        self.assertEqual(space.theme_colors, {"sidebar": "#112233", "header": "#778899"})

    def test_rejects_unknown_zone(self):
        with self.assertRaises(services.DocsValidationError):
            self._update(theme_colors={"partout": "#112233"})

    def test_rejects_invalid_colors(self):
        for value in ("rouge", "#12345", "#12345G", "url(x)"):
            with self.assertRaises(services.DocsValidationError, msg=value):
                self._update(theme_colors={"sidebar": value})
        with self.assertRaises(services.DocsValidationError):
            self._update(accent_color="rouge")

    def test_blank_accent_color_still_resets_it(self):
        self._update(accent_color="#7A4F9E")
        self.assertEqual(self._update(accent_color="").accent_color, "")

    def test_powered_by_mention_is_shown_by_default_and_can_be_hidden(self):
        self.assertTrue(DocSpace.objects.get_or_create(project=self.project)[0].show_powered_by)
        self.assertFalse(self._update(show_powered_by=False).show_powered_by)

    def test_member_cannot_change_appearance(self):
        with self.assertRaises(services.DocsPermissionError):
            services.update_space_appearance(actor=self.member, project=self.project, theme_colors={})

    def test_public_docs_expose_appearance(self):
        self._update(theme_colors={"sidebar": "#112233"}, show_powered_by=False, header_content="**Bienvenue**")
        space = services.enable_public_link(actor=self.manager, project=self.project)
        public = services.get_public_docs(space.public_token)
        self.assertEqual(public["theme_colors"], {"sidebar": "#112233"})
        self.assertFalse(public["show_powered_by"])
        self.assertEqual(public["header_content"], "**Bienvenue**")


@override_settings(DEBUG=True)
class AppearanceApiTests(AttachmentFixtureMixin, APITestCase):
    def setUp(self):
        self._set_up_project()
        self.client.credentials(HTTP_X_DEBUG_USER_ID=str(self.manager.id))
        self.url = f"/api/v1/docs/{self.project.id}/appearance/"

    def test_patch_returns_new_appearance(self):
        response = self.client.patch(
            self.url, {"theme_colors": {"background": "#FAFAFA"}, "show_powered_by": False}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["space"]["theme_colors"], {"background": "#FAFAFA"})
        self.assertFalse(response.data["space"]["show_powered_by"])

    def test_invalid_color_is_400(self):
        response = self.client.patch(self.url, {"theme_colors": {"background": "rouge"}}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_partial_patch_leaves_powered_by_untouched(self):
        self.client.patch(self.url, {"show_powered_by": False}, format="json")
        response = self.client.patch(self.url, {"header_content": "Salut"}, format="json")
        self.assertFalse(response.data["space"]["show_powered_by"])
