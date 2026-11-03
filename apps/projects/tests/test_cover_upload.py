from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.models import AuditLogEntry

from ..models import Project, ProjectCoverUpload, ProjectMembership
from ..services import MAX_COVER_UPLOAD_BYTES

WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 40
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40


@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "apps.accounts.authentication.DebugUserIdAuthentication",
            "rest_framework.authentication.SessionAuthentication",
        ],
    },
)
class ProjectCoverUploadApiTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="cover-manager")
        self.member = User.objects.create_user(username="cover-member")
        self.outsider = User.objects.create_user(username="cover-outsider")
        self.project = Project.objects.create(name="Projet Couverture")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.url = f"/api/v1/projects/{self.project.id}/cover/"

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def upload(self, data, user=None, name="cover.webp"):
        return self.client.post(
            self.url,
            {"file": SimpleUploadedFile(name, data, content_type="image/webp")},
            format="multipart",
            **self.as_user(user or self.manager),
        )

    def test_manager_uploads_and_member_reads(self):
        response = self.upload(WEBP)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cover_image"], "upload")
        self.assertIsNotNone(response.json()["cover_updated_at"])

        read = self.client.get(self.url, **self.as_user(self.member))
        self.assertEqual(read.status_code, 200)
        self.assertEqual(read["Content-Type"], "image/webp")
        self.assertEqual(read.content, WEBP)

    def test_replacing_overwrites_single_row(self):
        self.upload(WEBP)
        self.upload(PNG, name="cover.png")
        self.assertEqual(ProjectCoverUpload.objects.filter(project=self.project).count(), 1)
        read = self.client.get(self.url, **self.as_user(self.manager))
        self.assertEqual(read["Content-Type"], "image/png")

    def test_content_type_comes_from_bytes_not_client(self):
        response = self.upload(b"<svg onload=alert(1)></svg>", name="evil.webp")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ProjectCoverUpload.objects.exists())

    def test_too_large_rejected(self):
        response = self.upload(WEBP + b"\x00" * MAX_COVER_UPLOAD_BYTES)
        self.assertEqual(response.status_code, 400)

    def test_member_cannot_upload(self):
        self.assertEqual(self.upload(WEBP, user=self.member).status_code, 403)

    def test_outsider_cannot_read(self):
        self.upload(WEBP)
        self.assertEqual(self.client.get(self.url, **self.as_user(self.outsider)).status_code, 404)

    def test_switching_to_library_keeps_row_and_hides_upload(self):
        self.upload(WEBP)
        details = f"/api/v1/projects/{self.project.id}/update-details/"
        self.client.post(details, {"cover_image": "portail-client"}, format="json", **self.as_user(self.manager))
        self.assertEqual(self.client.get(self.url, **self.as_user(self.manager)).status_code, 404)
        self.assertTrue(ProjectCoverUpload.objects.filter(project=self.project).exists())

        back = self.client.post(details, {"cover_image": "upload"}, format="json", **self.as_user(self.manager))
        self.assertEqual(back.status_code, 200)
        self.assertEqual(self.client.get(self.url, **self.as_user(self.manager)).status_code, 200)

    def test_cannot_select_upload_without_image(self):
        details = f"/api/v1/projects/{self.project.id}/update-details/"
        response = self.client.post(details, {"cover_image": "upload"}, format="json", **self.as_user(self.manager))
        self.assertEqual(response.status_code, 400)

    def test_upload_not_settable_at_creation(self):
        response = self.client.post(
            "/api/v1/projects/",
            {"name": "X", "project_type": "individuel", "cover_image": "upload"},
            format="json",
            **self.as_user(self.manager),
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_is_audited(self):
        self.upload(WEBP)
        self.assertTrue(AuditLogEntry.objects.filter(project=self.project, field_name="cover_image").exists())
