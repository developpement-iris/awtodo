from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.accounts.models import User
from apps.common.audit import get_audit_log, record_changes
from apps.common.models import AuditLogEntry


class AuditLogEntryModelTests(TestCase):
    def test_creates_entry_linked_to_any_model_via_generic_relation(self):
        actor = User.objects.create_user(username="alice")
        target = User.objects.create_user(username="bob")

        entry = AuditLogEntry.objects.create(
            content_object=target,
            actor=actor,
            field_name="first_name",
            old_value="",
            new_value="Bob",
        )

        self.assertEqual(entry.content_object, target)
        self.assertEqual(entry.content_type, ContentType.objects.get_for_model(User))
        self.assertEqual(entry.object_id, target.id)


class RecordChangesTests(TestCase):
    def test_logs_only_changed_fields(self):
        actor = User.objects.create_user(username="alice")
        target = User.objects.create_user(username="bob", first_name="Bob", last_name="Original")

        with record_changes(target, actor=actor):
            target.first_name = "Robert"
            target.save()

        entries = list(get_audit_log(target))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].field_name, "first_name")
        self.assertEqual(entries[0].old_value, "Bob")
        self.assertEqual(entries[0].new_value, "Robert")
        self.assertEqual(entries[0].actor, actor)

    def test_no_entry_when_nothing_changes(self):
        actor = User.objects.create_user(username="alice2")
        target = User.objects.create_user(username="bob2")

        with record_changes(target, actor=actor):
            target.save()

        self.assertEqual(get_audit_log(target).count(), 0)

    def test_choices_are_resolved_to_display_labels(self):
        actor = User.objects.create_user(username="alice3")
        target = User.objects.create_user(username="bob3", organisation_role="membre")

        with record_changes(target, actor=actor):
            target.organisation_role = "admin"
            target.save()

        entry = get_audit_log(target).get(field_name="organisation_role")
        self.assertEqual(entry.old_value, "Membre")
        self.assertEqual(entry.new_value, "Administrateur")
