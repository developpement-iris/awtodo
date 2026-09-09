# Notifications (in-app + email) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Notifier un utilisateur en app (cloche du `Topbar`, aujourd'hui un bouton muet) et par email quand une tâche lui est assignée, ou qu'un commentaire est posté sur une tâche/un incident dont il est l'assigné.

**Architecture:** `apps.notifications` est déjà scaffoldé (fichiers vides) et déjà en tête de la hiérarchie de dépendances du projet ("dépend de tout, déclenchée par signals" — voir CLAUDE.md > "Structure du projet"). On respecte ce sens : `apps.tasks`/`apps.incidents` définissent et émettent des `django.dispatch.Signal` (`task_assigned`, `task_commented`, `incident_commented`) sans jamais importer `apps.notifications` ; `apps.notifications` importe ces signaux (autorisé, il est plus haut dans la hiérarchie) et s'y abonne via des receivers enregistrés dans `AppConfig.ready()`. Un seul modèle `Notification` (FK directes vers `Task`/`Incident`, pas de relation générique — contrairement à l'audit log, il n'y a ici que deux cibles possibles, un FK classique par cible reste plus simple et suffisant).

**Tech Stack:** Django (signals, `send_mail`), DRF côté API. React + TypeScript côté frontend, aucune nouvelle dépendance.

## Global Constraints

- `apps.tasks`/`apps.incidents` ne doivent jamais importer `apps.notifications` (CLAUDE.md > "Règle de dépendances entre apps") — la communication passe exclusivement par les signaux déclarés dans chaque app émettrice.
- **Envoi d'email synchrone assumé pour cette passe** (backend console en dev, voir `config/settings/dev.py`) — même décision déjà prise et documentée pour les emails d'invitation (`apps.accounts.services._send_invitation_email`, session du 06/08/2026) : Celery n'est qu'une dépendance déclarée dans ce projet, pas câblée (aucun `celery.py`/config broker n'existe). La règle d'architecture n°2 (CLAUDE.md, "aucun appel synchrone vers un système externe... signal → tâche Celery async") reste la cible visée quand Celery sera réellement branché — pas avant, cohérent avec le précédent déjà accepté sur les invitations.
- **Pas de champ `created_by` sur `Task`** — seuls des déclencheurs à destinataire unique et non ambigu sont notifiés : assignation d'une tâche (au nouvel assigné, jamais à soi-même) et nouveau commentaire (à l'assigné actuel, sauf si c'est lui qui commente). Pas de notification "incident assigné" : `claim_incident` est toujours une auto-assignation, il n'y a personne d'autre à notifier.
- Toute logique métier vit dans `services.py`, jamais dans serializers/vues/signals eux-mêmes (les receivers appellent un service, ils ne contiennent pas la logique).
- Toute app a ses tests dans `tests/` (CLAUDE.md règle n°7).
- Pas de librairie de routing dans le frontend (`App.tsx`, état React pur, voir son commentaire en tête de fichier) — le clic sur une notification réutilise ce mécanisme, pas une nouvelle dépendance.

---

## File Structure

- `apps/notifications/models.py` — `Notification` (déjà scaffoldé vide).
- `apps/notifications/migrations/0001_initial.py` — auto-générée.
- `apps/tasks/signals.py` — `task_assigned`, `task_commented` (déjà scaffoldé vide).
- `apps/incidents/signals.py` — `incident_commented` (déjà scaffoldé vide).
- `apps/tasks/services.py` — `assign_task`/`validate_task`/`add_comment` émettent les signaux.
- `apps/incidents/services.py` — `add_comment` émet le signal.
- `apps/notifications/services.py` — `create_notification`, `notify_task_assigned`, `notify_task_commented`, `notify_incident_commented`, `send_notification_email`, `mark_notification_read`, `mark_all_read`, `get_unread_count` (déjà scaffoldé vide).
- `apps/notifications/signals.py` — receivers, connectent les signaux ci-dessus aux fonctions `notify_*` (déjà scaffoldé vide).
- `apps/notifications/apps.py` — `ready()` importe `signals` pour enregistrer les receivers.
- `apps/notifications/serializers.py` — `NotificationSerializer` (déjà scaffoldé vide).
- `apps/notifications/views.py` — `NotificationViewSet` (liste + `mark-read` + `mark-all-read` + `unread-count`) (déjà scaffoldé vide).
- `apps/notifications/urls.py` — déjà branché dans `config/urls.py` (`notifications/`), contenu actuel `urlpatterns = []` à remplacer par le vrai router.
- `apps/notifications/tests/test_notifications.py` — nouveau : modèle + services + signaux + API.
- `apps/tasks/tests/test_notifications.py` — nouveau : vérifie que les actions tâches émettent bien les signaux.
- `apps/incidents/tests/test_notifications.py` — nouveau : vérifie que `add_comment` émet bien le signal.
- `frontend/src/types/watodo.ts` — ajoute `Notification`.
- `frontend/src/api/client.ts` — ajoute `getNotifications`, `getUnreadNotificationCount`, `markNotificationRead`, `markAllNotificationsRead`.
- `frontend/src/components/NotificationsDropdown.tsx` + `.css` — nouveau composant, remplace le bouton cloche muet du `Topbar`.
- `frontend/src/layout/Topbar.tsx` — branche `NotificationsDropdown` à la place de `handlePlaceholderAction` sur la cloche.
- `frontend/src/types/navigation.ts`, `frontend/src/App.tsx`, `frontend/src/features/tasks/TasksListPage.tsx` — ajoutent le mécanisme de lien direct vers une tâche (`focusTaskId`), symétrique à celui déjà existant pour les incidents (`focusIncidentId`).

---

### Task 1: Modèle `Notification` + migration

**Files:**
- Modify: `apps/notifications/models.py` (actuellement vide)
- Create: `apps/notifications/migrations/0001_initial.py` (auto-générée)
- Create: `apps/notifications/tests/test_notifications.py`

**Interfaces:**
- Produces: `Notification` (champs `recipient`, `verb`, `message`, `task`, `incident`, `is_read`, `id`/`created_at`/`updated_at` hérités) — consommé par toutes les tâches suivantes.

- [ ] **Step 1: Write the failing test**

Créer `apps/notifications/tests/test_notifications.py` :

```python
from django.test import TestCase

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task


class NotificationModelTests(TestCase):
    def test_creates_notification_linked_to_task(self):
        recipient = User.objects.create_user(username="alice-notif")
        project = Project.objects.create(name="Projet Test")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        ProjectMembership.objects.create(project=project, user=recipient, role="membre")
        task = Task.objects.create(project=project, version=version, title="Corriger le bug", task_type="correction")

        notification = Notification.objects.create(
            recipient=recipient,
            verb="task_assigned",
            message="On vous a assigné une tâche.",
            task=task,
        )

        self.assertEqual(notification.recipient, recipient)
        self.assertEqual(notification.task, task)
        self.assertIsNone(notification.incident)
        self.assertFalse(notification.is_read)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.notifications.tests.test_notifications -v 2`
Expected: FAIL avec `ImportError: cannot import name 'Notification' from 'apps.notifications.models'`

- [ ] **Step 3: Write minimal implementation**

Remplacer le contenu de `apps/notifications/models.py` :

```python
from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel
from apps.incidents.models import Incident
from apps.tasks.models import Task


class Notification(UUIDModel, TimeStampedModel):
    """`apps.notifications` est en tête de la hiérarchie de dépendances du
    projet (voir CLAUDE.md > "Structure du projet") — importer `Task`/
    `Incident` ici est autorisé dans ce sens précis, jamais l'inverse. FK
    directes plutôt qu'une relation générique (contrairement à
    `apps.common.models.AuditLogEntry`) : il n'existe que deux cibles
    possibles pour une notification, une relation générique n'apporterait
    rien ici."""

    VERB_CHOICES = [
        ("task_assigned", "Tâche assignée"),
        ("task_commented", "Commentaire sur une tâche"),
        ("incident_commented", "Commentaire sur un incident"),
    ]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    verb = models.CharField(max_length=30, choices=VERB_CHOICES)
    message = models.CharField(max_length=255)
    task = models.ForeignKey(Task, null=True, blank=True, on_delete=models.PROTECT, related_name="notifications")
    incident = models.ForeignKey(
        Incident, null=True, blank=True, on_delete=models.PROTECT, related_name="notifications"
    )
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.verb} → {self.recipient}"
```

- [ ] **Step 4: Generate and apply the migration**

Run: `python manage.py makemigrations notifications`
Expected: `Migrations for 'notifications': apps\notifications\migrations\0001_initial.py — + Create model Notification`

Run: `python manage.py migrate notifications`
Expected: `Applying notifications.0001_initial... OK`

- [ ] **Step 5: Run test to verify it passes**

Run: `python manage.py test apps.notifications.tests.test_notifications -v 2`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/notifications/models.py apps/notifications/migrations/0001_initial.py apps/notifications/tests/test_notifications.py
git commit -m "feat(notifications): add Notification model"
```

---

### Task 2: Signaux déclarés et émis (tâches + incidents)

**Files:**
- Modify: `apps/tasks/signals.py` (actuellement vide)
- Modify: `apps/incidents/signals.py` (actuellement vide)
- Modify: `apps/tasks/services.py`
- Modify: `apps/incidents/services.py`
- Create: `apps/tasks/tests/test_notifications.py`
- Create: `apps/incidents/tests/test_notifications.py`

**Interfaces:**
- Produces: `apps.tasks.signals.task_assigned` (kwargs `task`, `actor`), `apps.tasks.signals.task_commented` (kwargs `task`, `comment`, `actor`), `apps.incidents.signals.incident_commented` (kwargs `incident`, `comment`, `actor`) — consommés par Task 3 (receivers dans `apps.notifications`).

- [ ] **Step 1: Write the failing tests**

Créer `apps/tasks/tests/test_notifications.py` :

```python
from django.test import TestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task
from apps.tasks.services import add_comment, assign_task, validate_task
from apps.tasks.signals import task_assigned, task_commented


class TaskSignalsTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.manager = User.objects.create_user(username="manager-notif")
        self.member = User.objects.create_user(username="member-notif")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Corriger le bug", task_type="correction"
        )

    def test_assign_task_sends_task_assigned_signal(self):
        received = []
        task_assigned.connect(lambda sender, **kwargs: received.append(kwargs))
        try:
            assign_task(actor=self.manager, task=self.task, assignee=self.member)
        finally:
            task_assigned.disconnect(dispatch_uid=None)
        # `disconnect` sans receiver précis ne fonctionne pas de manière fiable
        # avec une lambda — voir Step 3 pour la vraie implémentation utilisée
        # dans les tests suivants (fonction nommée, déconnectée explicitement).

    def test_validate_task_with_assignee_sends_task_assigned_signal(self):
        pending = Task.objects.create(
            project=self.project, version=self.version, title="Autre tâche", task_type="correction",
            status="en_attente_validation",
        )
        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        task_assigned.connect(handler)
        try:
            validate_task(actor=self.manager, task=pending, assignee=self.member)
        finally:
            task_assigned.disconnect(handler)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["task"], pending)
        self.assertEqual(received[0]["actor"], self.manager)

    def test_add_comment_sends_task_commented_signal(self):
        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        task_commented.connect(handler)
        try:
            comment = add_comment(actor=self.member, task=self.task, content="On regarde ça")
        finally:
            task_commented.disconnect(handler)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["task"], self.task)
        self.assertEqual(received[0]["comment"], comment)
        self.assertEqual(received[0]["actor"], self.member)
```

Remplacer immédiatement le premier test (`test_assign_task_sends_task_assigned_signal`), écrit avec une lambda non fiable à déconnecter — utiliser le même pattern à fonction nommée que les deux tests suivants :

```python
    def test_assign_task_sends_task_assigned_signal(self):
        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        task_assigned.connect(handler)
        try:
            assign_task(actor=self.manager, task=self.task, assignee=self.member)
        finally:
            task_assigned.disconnect(handler)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["task"], self.task)
        self.assertEqual(received[0]["actor"], self.manager)
```

Créer `apps/incidents/tests/test_notifications.py` :

```python
from django.test import TestCase

from apps.accounts.models import Team, TeamMembership, User
from apps.incidents.models import Incident
from apps.incidents.services import add_comment
from apps.incidents.signals import incident_commented


class IncidentSignalsTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Équipe Test Notif")
        self.member = User.objects.create_user(username="member-incident-notif")
        TeamMembership.objects.create(team=self.team, user=self.member)
        self.incident = Incident.objects.create(team=self.team, title="Panne réseau")

    def test_add_comment_sends_incident_commented_signal(self):
        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        incident_commented.connect(handler)
        try:
            comment = add_comment(actor=self.member, incident=self.incident, content="Je regarde")
        finally:
            incident_commented.disconnect(handler)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["incident"], self.incident)
        self.assertEqual(received[0]["comment"], comment)
        self.assertEqual(received[0]["actor"], self.member)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test apps.tasks.tests.test_notifications apps.incidents.tests.test_notifications -v 2`
Expected: FAIL — `ImportError: cannot import name 'task_assigned' from 'apps.tasks.signals'` (et équivalent côté incidents)

- [ ] **Step 3: Write minimal implementation**

Remplacer le contenu de `apps/tasks/signals.py` :

```python
import django.dispatch

# kwargs: task (Task), actor (User) — émis quand une tâche est assignée à
# quelqu'un d'autre que l'acteur (jamais sur une auto-attribution via
# `claim_task`, voir apps/tasks/services.py).
task_assigned = django.dispatch.Signal()

# kwargs: task (Task), comment (TaskComment), actor (User)
task_commented = django.dispatch.Signal()
```

Remplacer le contenu de `apps/incidents/signals.py` :

```python
import django.dispatch

# kwargs: incident (Incident), comment (IncidentComment), actor (User)
incident_commented = django.dispatch.Signal()
```

Dans `apps/tasks/services.py`, ajouter l'import :

```python
from .signals import task_assigned, task_commented
```

Dans `assign_task`, émettre le signal juste après `task.save()` (donc après le bloc `record_changes`, une fois la tâche enregistrée) :

```python
def assign_task(*, actor, task, assignee):
    _ensure_can_assign(actor, task)
    if assignee is None:
        raise InvalidTransitionError("Un assigné est requis.")
    if not _is_member(assignee, task.project):
        raise InvalidTransitionError("L'assigné doit être membre du projet.")

    with record_changes(task, actor=actor):
        task.status = "assignee"
        task.assignee = assignee
        task.save()
    task_assigned.send(sender=Task, task=task, actor=actor)
    return task
```

Dans `validate_task`, émettre le signal seulement si un assigné a été fourni :

```python
def validate_task(*, actor, task, assignee=None):
    _ensure_can_validate(actor, task)

    with record_changes(task, actor=actor):
        task.status = "assignee" if assignee else "disponible"
        task.assignee = assignee
        task.save()
    if assignee:
        task_assigned.send(sender=Task, task=task, actor=actor)
    return task
```

Dans `add_comment` (tâches), émettre après la création du commentaire :

```python
def add_comment(*, actor, task, content):
    _ensure_can_comment(actor, task)
    if not content or not content.strip():
        raise InvalidTransitionError("Le commentaire ne peut pas être vide.")

    comment = TaskComment.objects.create(task=task, author=actor, content=content.strip())
    task_commented.send(sender=Task, task=task, comment=comment, actor=actor)
    return comment
```

Dans `apps/incidents/services.py`, ajouter l'import :

```python
from .signals import incident_commented
```

Dans `add_comment` (incidents), même principe :

```python
def add_comment(*, actor, incident, content):
    _ensure_can_comment(actor, incident)
    if not content or not content.strip():
        raise IncidentValidationError("Le commentaire ne peut pas être vide.")

    comment = IncidentComment.objects.create(incident=incident, author=actor, content=content.strip())
    incident_commented.send(sender=Incident, incident=incident, comment=comment, actor=actor)
    return comment
```

**Ne pas** ajouter d'émission dans `claim_task`/`claim_incident` (auto-attribution, personne d'autre à notifier — voir "Global Constraints").

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test apps.tasks.tests.test_notifications apps.incidents.tests.test_notifications -v 2`
Expected: PASS (3 tests côté tâches, 1 côté incidents)

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `python manage.py test`
Expected: tous les tests passent (385 avant cette passe + les nouveaux de Task 1/2)

- [ ] **Step 6: Commit**

```bash
git add apps/tasks/signals.py apps/incidents/signals.py apps/tasks/services.py apps/incidents/services.py apps/tasks/tests/test_notifications.py apps/incidents/tests/test_notifications.py
git commit -m "feat: emit task_assigned/task_commented/incident_commented signals"
```

---

### Task 3: Services de notification + receivers + email

**Files:**
- Modify: `apps/notifications/services.py` (actuellement vide)
- Modify: `apps/notifications/signals.py` (actuellement vide)
- Modify: `apps/notifications/apps.py`
- Modify: `apps/notifications/tests/test_notifications.py`

**Interfaces:**
- Consumes: `task_assigned`, `task_commented` (Task 2, `apps.tasks.signals`), `incident_commented` (Task 2, `apps.incidents.signals`), `Notification` (Task 1).
- Produces: `create_notification(*, recipient, verb, message, task=None, incident=None)`, `notify_task_assigned(*, task, actor)`, `notify_task_commented(*, task, comment, actor)`, `notify_incident_commented(*, incident, comment, actor)`, `send_notification_email(notification)` — consommés en interne par cette tâche (receivers) et par Task 4 (tests d'intégration bout en bout via l'API).

- [ ] **Step 1: Write the failing test**

Ajouter à `apps/notifications/tests/test_notifications.py` :

```python
from django.core import mail

from apps.accounts.models import Team, TeamMembership
from apps.incidents.models import Incident
from apps.tasks.services import add_comment as add_task_comment
from apps.tasks.services import assign_task
from apps.incidents.services import add_comment as add_incident_comment


class NotificationSignalIntegrationTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test Notif")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.manager = User.objects.create_user(username="manager-notif-2", email="manager@example.com")
        self.member = User.objects.create_user(username="member-notif-2", email="member@example.com")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Corriger le bug", task_type="correction"
        )

        self.team = Team.objects.create(name="Équipe Test Notif 2")
        TeamMembership.objects.create(team=self.team, user=self.member)
        self.incident = Incident.objects.create(team=self.team, title="Panne réseau", assigned_to=self.member)

    def test_assign_task_creates_notification_and_sends_email(self):
        assign_task(actor=self.manager, task=self.task, assignee=self.member)

        notification = Notification.objects.get(recipient=self.member, verb="task_assigned")
        self.assertIn("Corriger le bug", notification.message)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["member@example.com"])

    def test_assign_task_to_self_does_not_notify(self):
        # `assign_task` n'est normalement jamais appelé par l'assigné
        # lui-même (c'est le rôle de `claim_task`), mais la garde de
        # `notify_task_assigned` doit rester silencieuse dans ce cas plutôt
        # que de planter, au cas où.
        assign_task(actor=self.manager, task=self.task, assignee=self.manager)

        self.assertFalse(Notification.objects.filter(verb="task_assigned").exists())

    def test_comment_on_unassigned_task_does_not_notify(self):
        add_task_comment(actor=self.member, task=self.task, content="Personne assigné, pas de destinataire")

        self.assertFalse(Notification.objects.filter(verb="task_commented").exists())

    def test_comment_by_assignee_does_not_self_notify(self):
        assign_task(actor=self.manager, task=self.task, assignee=self.member)
        mail.outbox.clear()

        add_task_comment(actor=self.member, task=self.task, content="Je m'en occupe")

        self.assertFalse(Notification.objects.filter(verb="task_commented").exists())

    def test_comment_by_someone_else_notifies_task_assignee(self):
        assign_task(actor=self.manager, task=self.task, assignee=self.member)
        mail.outbox.clear()

        add_task_comment(actor=self.manager, task=self.task, content="Des nouvelles ?")

        notification = Notification.objects.get(recipient=self.member, verb="task_commented")
        self.assertIn("Corriger le bug", notification.message)

    def test_comment_on_incident_notifies_assignee(self):
        add_incident_comment(actor=self.manager, incident=self.incident, content="Ça avance ?")

        notification = Notification.objects.get(recipient=self.member, verb="incident_commented")
        self.assertIn("Panne réseau", notification.message)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test apps.notifications.tests.test_notifications.NotificationSignalIntegrationTests -v 2`
Expected: FAIL — aucune `Notification` créée (les signaux n'ont encore aucun abonné)

- [ ] **Step 3: Write minimal implementation**

Remplacer le contenu de `apps/notifications/services.py` :

```python
from django.core.mail import send_mail

from .models import Notification


class NotificationPermissionError(Exception):
    """L'acteur n'a pas le droit d'effectuer cette action."""


def _display_name(user):
    return f"{user.first_name} {user.last_name}".strip() or user.username


def create_notification(*, recipient, verb, message, task=None, incident=None):
    return Notification.objects.create(recipient=recipient, verb=verb, message=message, task=task, incident=incident)


def send_notification_email(notification):
    # Synchrone, backend console en dev — voir "Global Constraints" en tête
    # de ce plan pour la justification (même précédent que les emails
    # d'invitation).
    if not notification.recipient.email:
        return
    send_mail(
        subject="Awtodo — nouvelle notification",
        message=notification.message,
        from_email=None,
        recipient_list=[notification.recipient.email],
        fail_silently=True,
    )


def notify_task_assigned(*, task, actor):
    if task.assignee_id is None or task.assignee_id == actor.id:
        return None
    notification = create_notification(
        recipient=task.assignee,
        verb="task_assigned",
        message=f"{_display_name(actor)} vous a assigné la tâche « {task.title} ».",
        task=task,
    )
    send_notification_email(notification)
    return notification


def notify_task_commented(*, task, comment, actor):
    if task.assignee_id is None or task.assignee_id == actor.id:
        return None
    notification = create_notification(
        recipient=task.assignee,
        verb="task_commented",
        message=f"{_display_name(actor)} a commenté la tâche « {task.title} ».",
        task=task,
    )
    send_notification_email(notification)
    return notification


def notify_incident_commented(*, incident, comment, actor):
    if incident.assigned_to_id is None or incident.assigned_to_id == actor.id:
        return None
    notification = create_notification(
        recipient=incident.assigned_to,
        verb="incident_commented",
        message=f"{_display_name(actor)} a commenté l'incident « {incident.title} ».",
        incident=incident,
    )
    send_notification_email(notification)
    return notification


def mark_notification_read(*, actor, notification):
    # Garde en défense en profondeur : `NotificationViewSet.get_queryset()`
    # (Task 4) scope déjà `self.get_object()` à `recipient=request.user`, donc
    # ce cas n'est normalement jamais atteint via l'API (404 avant, même
    # principe que le scoping par appartenance déjà en place ailleurs dans le
    # projet) — reste utile pour un appel direct au service, hors HTTP.
    if notification.recipient_id != actor.id:
        raise NotificationPermissionError("Cette notification ne vous appartient pas.")
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return notification


def mark_all_read(*, actor):
    Notification.objects.filter(recipient=actor, is_read=False).update(is_read=True)


def get_unread_count(*, actor):
    return Notification.objects.filter(recipient=actor, is_read=False).count()
```

Remplacer le contenu de `apps/notifications/signals.py` :

```python
from django.dispatch import receiver

from apps.incidents.signals import incident_commented
from apps.tasks.signals import task_assigned, task_commented

from .services import notify_incident_commented, notify_task_assigned, notify_task_commented


@receiver(task_assigned)
def handle_task_assigned(sender, task, actor, **kwargs):
    notify_task_assigned(task=task, actor=actor)


@receiver(task_commented)
def handle_task_commented(sender, task, comment, actor, **kwargs):
    notify_task_commented(task=task, comment=comment, actor=actor)


@receiver(incident_commented)
def handle_incident_commented(sender, incident, comment, actor, **kwargs):
    notify_incident_commented(incident=incident, comment=comment, actor=actor)
```

Remplacer le contenu de `apps/notifications/apps.py` :

```python
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"

    def ready(self):
        from . import signals  # noqa: F401 — enregistre les receivers au démarrage
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test apps.notifications.tests.test_notifications -v 2`
Expected: PASS (1 test de Task 1 + 6 tests de cette tâche = 7)

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `python manage.py test`
Expected: tous les tests passent

- [ ] **Step 6: Commit**

```bash
git add apps/notifications/services.py apps/notifications/signals.py apps/notifications/apps.py apps/notifications/tests/test_notifications.py
git commit -m "feat(notifications): wire signal receivers, create notifications and send email"
```

---

### Task 4: API — liste, marquer lu, compteur

**Files:**
- Modify: `apps/notifications/serializers.py` (actuellement vide)
- Modify: `apps/notifications/views.py` (actuellement vide)
- Modify: `apps/notifications/urls.py` (actuellement `urlpatterns = []`)
- Modify: `apps/notifications/tests/test_notifications.py`

**Interfaces:**
- Consumes: `Notification` (Task 1), `mark_notification_read`, `mark_all_read`, `get_unread_count`, `NotificationPermissionError` (Task 3).
- Produces: `GET /api/v1/notifications/`, `POST /api/v1/notifications/{id}/mark-read/`, `POST /api/v1/notifications/mark-all-read/`, `GET /api/v1/notifications/unread-count/` — consommés par le frontend (Task 5).

- [ ] **Step 1: Write the failing test**

Ajouter à `apps/notifications/tests/test_notifications.py` :

```python
from django.test import override_settings
from rest_framework.test import APITestCase


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
class NotificationApiTests(APITestCase):
    def setUp(self):
        self.recipient = User.objects.create_user(username="notif-api-recipient")
        self.other_user = User.objects.create_user(username="notif-api-other")
        self.notification = Notification.objects.create(
            recipient=self.recipient, verb="task_assigned", message="Test"
        )

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_list_only_returns_own_notifications(self):
        Notification.objects.create(recipient=self.other_user, verb="task_assigned", message="Pas pour vous")

        response = self.client.get("/api/v1/notifications/", **self.as_user(self.recipient))

        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()]
        self.assertEqual(ids, [str(self.notification.id)])

    def test_mark_read(self):
        response = self.client.post(
            f"/api/v1/notifications/{self.notification.id}/mark-read/", **self.as_user(self.recipient)
        )

        self.assertEqual(response.status_code, 200)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_cannot_mark_read_someone_elses_notification(self):
        response = self.client.post(
            f"/api/v1/notifications/{self.notification.id}/mark-read/", **self.as_user(self.other_user)
        )

        # 404, pas 403 : get_queryset() scope déjà par destinataire, même
        # principe que le scoping par appartenance déjà en place ailleurs.
        self.assertEqual(response.status_code, 404)

    def test_mark_all_read(self):
        Notification.objects.create(recipient=self.recipient, verb="task_commented", message="Deuxième")

        response = self.client.post("/api/v1/notifications/mark-all-read/", **self.as_user(self.recipient))

        self.assertEqual(response.status_code, 204)
        self.assertEqual(Notification.objects.filter(recipient=self.recipient, is_read=False).count(), 0)

    def test_unread_count(self):
        Notification.objects.create(recipient=self.recipient, verb="task_commented", message="Deuxième")

        response = self.client.get("/api/v1/notifications/unread-count/", **self.as_user(self.recipient))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.notifications.tests.test_notifications.NotificationApiTests -v 2`
Expected: FAIL avec 404 sur `GET /api/v1/notifications/` (aucune route enregistrée, `urlpatterns` est vide)

- [ ] **Step 3: Write minimal implementation**

Remplacer le contenu de `apps/notifications/serializers.py` :

```python
from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "verb", "message", "task", "incident", "is_read", "created_at"]
```

Remplacer le contenu de `apps/notifications/views.py` :

```python
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer
from .services import NotificationPermissionError, get_unread_count, mark_all_read, mark_notification_read


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        try:
            mark_notification_read(actor=request.user, notification=notification)
        except NotificationPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read_action(self, request):
        mark_all_read(actor=request.user)
        return Response(status=204)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return Response({"count": get_unread_count(actor=request.user)})
```

Remplacer le contenu de `apps/notifications/urls.py` :

```python
from rest_framework.routers import DefaultRouter

from .views import NotificationViewSet

router = DefaultRouter()
router.register("", NotificationViewSet, basename="notification")

urlpatterns = router.urls
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.notifications.tests.test_notifications -v 2`
Expected: PASS (12 tests au total dans ce fichier)

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `python manage.py test`
Expected: tous les tests passent

- [ ] **Step 6: Commit**

```bash
git add apps/notifications/serializers.py apps/notifications/views.py apps/notifications/urls.py apps/notifications/tests/test_notifications.py
git commit -m "feat(notifications): expose list/mark-read/mark-all-read/unread-count API"
```

---

### Task 5: Types + client frontend

**Files:**
- Modify: `frontend/src/types/watodo.ts`
- Modify: `frontend/src/api/client.ts`

**Interfaces:**
- Consumes: réponses JSON de `NotificationSerializer` (Task 4).
- Produces: `Notification` (type), `getNotifications()`, `getUnreadNotificationCount()`, `markNotificationRead(id)`, `markAllNotificationsRead()` — consommés par Task 6.

- [ ] **Step 1: Add the type**

Dans `frontend/src/types/watodo.ts`, ajouter (à la fin du fichier) :

```typescript
export interface Notification {
  id: string;
  verb: "task_assigned" | "task_commented" | "incident_commented";
  message: string;
  task: string | null;
  incident: string | null;
  is_read: boolean;
  created_at: string;
}
```

- [ ] **Step 2: Add the client functions**

Dans `frontend/src/api/client.ts`, ajouter `Notification` à l'import de types en haut du fichier.

Ajouter à la fin du fichier :

```typescript
export function getNotifications(): Promise<Notification[]> {
  return getJson<Notification[]>("/notifications/");
}

export function getUnreadNotificationCount(): Promise<{ count: number }> {
  return getJson<{ count: number }>("/notifications/unread-count/");
}

export function markNotificationRead(notificationId: string): Promise<Notification> {
  return postJson<Notification>(`/notifications/${notificationId}/mark-read/`);
}

export async function markAllNotificationsRead(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/notifications/mark-all-read/`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw new Error(`Échec de la requête /notifications/mark-all-read/ (${response.status})`);
  }
}
```

`markAllNotificationsRead` n'utilise pas `postJson` (qui attend un corps JSON en retour, `204 No Content` n'en renvoie pas) — appel `fetch` direct, même pattern que `getJson`/`postJson` mais sans tenter de parser une réponse vide.

- [ ] **Step 3: Verify the frontend compiles**

Run: `cd frontend && npm run build`
Expected: build réussi, aucune erreur TypeScript

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/watodo.ts frontend/src/api/client.ts
git commit -m "feat(notifications): add Notification type and client functions"
```

---

### Task 6: `NotificationsDropdown` branché sur la cloche du `Topbar`

**Files:**
- Create: `frontend/src/components/NotificationsDropdown.tsx`
- Create: `frontend/src/components/NotificationsDropdown.css`
- Modify: `frontend/src/layout/Topbar.tsx`

**Interfaces:**
- Consumes: `getNotifications`, `getUnreadNotificationCount`, `markNotificationRead`, `markAllNotificationsRead`, `Notification` (Task 5).
- Produces: `NotificationsDropdown` (composant), prop `onNotificationClick?: (notification: Notification) => void` — consommée par Task 8 (navigation).

- [ ] **Step 1: Create the component**

Créer `frontend/src/components/NotificationsDropdown.tsx` (pattern popover déjà établi dans le projet — `ref` + écouteur `mousedown` extérieur, voir `StatusFilterDropdown.tsx`) :

```tsx
import { Bell, Check } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  getNotifications,
  getUnreadNotificationCount,
  markAllNotificationsRead,
  markNotificationRead,
} from "../api/client";
import { formatRelativeTime } from "../lib/relativeTime";
import type { Notification } from "../types/watodo";
import "./NotificationsDropdown.css";

interface NotificationsDropdownProps {
  onNotificationClick?: (notification: Notification) => void;
}

export function NotificationsDropdown({ onNotificationClick }: NotificationsDropdownProps) {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[] | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getUnreadNotificationCount()
      .then((data) => setUnreadCount(data.count))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!open) return;
    getNotifications()
      .then(setNotifications)
      .catch(() => setNotifications([]));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  async function handleNotificationClick(notification: Notification) {
    if (!notification.is_read) {
      try {
        await markNotificationRead(notification.id);
        setNotifications((current) =>
          current ? current.map((n) => (n.id === notification.id ? { ...n, is_read: true } : n)) : current,
        );
        setUnreadCount((current) => Math.max(0, current - 1));
      } catch {
        // Navigation quand même — un échec de marquage-lu ne doit pas
        // bloquer l'accès à la notification elle-même.
      }
    }
    setOpen(false);
    onNotificationClick?.(notification);
  }

  async function handleMarkAllRead() {
    try {
      await markAllNotificationsRead();
      setNotifications((current) => (current ? current.map((n) => ({ ...n, is_read: true })) : current));
      setUnreadCount(0);
    } catch {
      // Silencieux : l'utilisateur peut réessayer, pas d'état bloquant.
    }
  }

  return (
    <div className="notifications-dropdown" ref={containerRef}>
      <button
        type="button"
        className="topbar__icon-btn notifications-dropdown__trigger"
        onClick={() => setOpen((current) => !current)}
        aria-label="Notifications"
        title="Notifications"
      >
        <Bell size={17} strokeWidth={1.75} aria-hidden="true" />
        {unreadCount > 0 && <span className="notifications-dropdown__badge">{unreadCount}</span>}
      </button>

      {open && (
        <div className="notifications-dropdown__panel">
          <div className="notifications-dropdown__header">
            <span>Notifications</span>
            {unreadCount > 0 && (
              <button type="button" className="notifications-dropdown__mark-all" onClick={handleMarkAllRead}>
                <Check size={13} strokeWidth={1.75} aria-hidden="true" />
                Tout marquer comme lu
              </button>
            )}
          </div>

          {notifications === null && <p className="notifications-dropdown__empty">Chargement…</p>}
          {notifications !== null && notifications.length === 0 && (
            <p className="notifications-dropdown__empty">Aucune notification.</p>
          )}
          {notifications !== null && notifications.length > 0 && (
            <ul className="notifications-dropdown__list">
              {notifications.map((notification) => (
                <li key={notification.id}>
                  <button
                    type="button"
                    className={
                      notification.is_read
                        ? "notifications-dropdown__item"
                        : "notifications-dropdown__item notifications-dropdown__item--unread"
                    }
                    onClick={() => handleNotificationClick(notification)}
                  >
                    <span className="notifications-dropdown__item-message">{notification.message}</span>
                    <time
                      dateTime={notification.created_at}
                      title={new Date(notification.created_at).toLocaleString("fr-FR")}
                    >
                      {formatRelativeTime(notification.created_at)}
                    </time>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
```

Créer `frontend/src/components/NotificationsDropdown.css` (mêmes tokens que le reste du projet — inspiré de `StatusFilterDropdown.css`/`UserMenu.css` pour le panneau flottant) :

```css
.notifications-dropdown {
  position: relative;
}

.notifications-dropdown__trigger {
  position: relative;
}

.notifications-dropdown__badge {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 15px;
  height: 15px;
  padding: 0 3px;
  border-radius: 999px;
  background: var(--color-accent);
  color: var(--color-accent-contrast);
  font-size: 10px;
  font-weight: 700;
  line-height: 15px;
  text-align: center;
}

.notifications-dropdown__panel {
  position: absolute;
  top: calc(100% + var(--space-2));
  right: 0;
  width: 320px;
  max-height: 420px;
  overflow-y: auto;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-overlay);
  z-index: 40;
}

.notifications-dropdown__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  font-weight: 600;
  font-size: 13px;
}

.notifications-dropdown__mark-all {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  background: none;
  border: none;
  color: var(--color-accent);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}

.notifications-dropdown__empty {
  padding: var(--space-4);
  color: var(--color-text-muted);
  font-size: 13px;
  text-align: center;
}

.notifications-dropdown__list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.notifications-dropdown__item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  border-bottom: 1px solid var(--color-border);
  padding: var(--space-3) var(--space-4);
  cursor: pointer;
  font-family: inherit;
  transition: background-color var(--transition-fast);
}

.notifications-dropdown__item:hover {
  background: var(--color-surface-alt, var(--color-bg));
}

.notifications-dropdown__item--unread {
  background: color-mix(in srgb, var(--color-accent) 6%, transparent);
}

.notifications-dropdown__item-message {
  font-size: 13px;
  color: var(--color-text);
}

.notifications-dropdown__item time {
  font-size: 11.5px;
  color: var(--color-text-muted);
}
```

- [ ] **Step 2: Wire it into `Topbar`**

Dans `frontend/src/layout/Topbar.tsx`, ajouter l'import :

```typescript
import { NotificationsDropdown } from "../components/NotificationsDropdown";
```

Remplacer le bouton cloche :

```tsx
        <button
          type="button"
          className="topbar__icon-btn"
          onClick={handlePlaceholderAction}
          aria-label="Notifications"
          title="Notifications"
        >
          <Bell size={17} strokeWidth={1.75} aria-hidden="true" />
        </button>
```

par :

```tsx
        <NotificationsDropdown />
```

Retirer l'import `Bell` de `lucide-react` en tête de fichier s'il n'est plus utilisé ailleurs dans `Topbar.tsx` (il ne l'était que pour ce bouton).

- [ ] **Step 3: Verify the frontend compiles**

Run: `cd frontend && npm run build`
Expected: build réussi, aucune erreur TypeScript

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/NotificationsDropdown.tsx frontend/src/components/NotificationsDropdown.css frontend/src/layout/Topbar.tsx
git commit -m "feat(notifications): add NotificationsDropdown, wire into Topbar bell"
```

---

### Task 7: Lien direct vers une tâche (`focusTaskId`)

**Files:**
- Modify: `frontend/src/types/navigation.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/features/tasks/TasksListPage.tsx`

**Interfaces:**
- Produces: `handleNavigate("tasks", { taskId })` (App.tsx), prop `focusTaskId?: string` sur `TasksListPage` — consommés par Task 8 (clic sur une notification de type tâche).

**Prérequis pour que le clic sur une notification "tâche" mène quelque part** — symétrique au mécanisme déjà existant pour les incidents (`focusIncidentId`, implémenté lors de la passe "deep-linking depuis le backlog de l'accueil", session du 10/08/2026).

- [ ] **Step 1: Extend the route type**

Dans `frontend/src/App.tsx`, modifier la définition de `Route` :

```typescript
type Route =
  | { name: "home" }
  | { name: "projects" }
  | { name: "project"; project: Project }
  | { name: "tasks"; focusTaskId?: string }
  | { name: "incidents"; focusIncidentId?: string }
  | { name: "stats" }
  | { name: "administration" }
  | { name: "login" };
```

Modifier `handleNavigate` :

```typescript
  function handleNavigate(view: ViewName, options?: { taskId?: string; incidentId?: string }) {
    if (view === "tasks" && options?.taskId) {
      setRoute({ name: "tasks", focusTaskId: options.taskId });
      return;
    }
    if (view === "incidents" && options?.incidentId) {
      setRoute({ name: "incidents", focusIncidentId: options.incidentId });
      return;
    }
    setRoute({ name: view } as Route);
  }
```

Passer la prop au rendu :

```tsx
        {route.name === "tasks" && <TasksListPage focusTaskId={route.focusTaskId} />}
```

- [ ] **Step 2: Add the row id and focus effect in `TasksListPage`**

Dans `frontend/src/features/tasks/TasksListPage.tsx`, ajouter `focusTaskId?: string;` aux props du composant (nouvelle interface si elle n'existe pas encore, sinon l'étendre) et au paramètre déstructuré.

Ajouter `id={`task-row-${task.id}`}` sur la balise `<tr>` de chaque ligne (celle qui a déjà `className={mode === "mine" ? ... }`) :

```tsx
                    <tr
                      id={`task-row-${task.id}`}
                      className={mode === "mine" ? "tasks-list-page__row--clickable" : undefined}
                      onClick={
                        mode === "mine"
                          ? () => setExpandedTaskId((current) => (current === task.id ? null : task.id))
                          : undefined
                      }
                    >
```

Ajouter un effet (même emplacement relatif que l'effet équivalent dans `IncidentsPage.tsx`) :

```typescript
  useEffect(() => {
    if (!focusTaskId) return;
    setMode("mine");
    setExpandedTaskId(focusTaskId);
    const timeout = window.setTimeout(() => {
      document.getElementById(`task-row-${focusTaskId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
    return () => window.clearTimeout(timeout);
  }, [focusTaskId]);
```

`setMode("mine")` est nécessaire ici (absent de l'équivalent côté incidents, qui n'a pas cette notion de mode) : l'accordéon ne se rend que si `mode === "mine"` (voir la condition déjà en place plus bas dans le fichier) — sans ce forçage, un lien entrant alors qu'on est en mode "équipe" n'ouvrirait rien.

- [ ] **Step 3: Verify the frontend compiles**

Run: `cd frontend && npm run build`
Expected: build réussi, aucune erreur TypeScript

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/navigation.ts frontend/src/App.tsx frontend/src/features/tasks/TasksListPage.tsx
git commit -m "feat(tasks): add focusTaskId deep-link, symmetric to incidents' focusIncidentId"
```

---

### Task 8: Clic sur une notification → navigation + marquage lu

**Files:**
- Modify: `frontend/src/layout/Topbar.tsx`
- Modify: `frontend/src/layout/AppShell.tsx` (si `onNavigate` n'y transite pas déjà jusqu'à `Topbar`)
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `NotificationsDropdown`'s `onNotificationClick` (Task 6), `handleNavigate("tasks", { taskId })`/`handleNavigate("incidents", { incidentId })` (Task 7).
- Produces: rien de nouveau consommé ailleurs — dernier maillon de ce plan.

- [ ] **Step 1: Read the current `onNavigate` wiring**

Avant de coder cette tâche, lire `frontend/src/layout/AppShell.tsx` en entier pour voir si `onNavigate` (déjà passé par `App.tsx` à `AppShell`, voir Task 7) est déjà transmis jusqu'à `Topbar`, ou seulement à `BinderTabs`/`CommandPalette`. Si `Topbar` ne reçoit pas encore `onNavigate`, l'ajouter à `TopbarProps` et le faire suivre depuis `AppShell` — même prop, juste un maillon de plus dans la chaîne de props déjà existante.

- [ ] **Step 2: Wire `onNotificationClick` through `Topbar`**

Dans `frontend/src/layout/Topbar.tsx`, passer un handler à `NotificationsDropdown` :

```tsx
        <NotificationsDropdown
          onNotificationClick={(notification) => {
            if (notification.task) {
              onNavigate("tasks", { taskId: notification.task });
            } else if (notification.incident) {
              onNavigate("incidents", { incidentId: notification.incident });
            }
          }}
        />
```

(`onNavigate` vient de la prop ajoutée/confirmée à l'étape précédente — signature déjà compatible avec `handleNavigate` de `App.tsx`, mis à jour en Task 7 pour accepter `taskId`.)

- [ ] **Step 3: Verify the frontend compiles**

Run: `cd frontend && npm run build`
Expected: build réussi, aucune erreur TypeScript

- [ ] **Step 4: Manual smoke test**

Démarrer `python manage.py runserver` et `npm run dev`. En tant que chef de projet, assigner une tâche à un autre membre (via `TaskAccordion` > Attribution) ; se reconnecter en tant que ce membre ; vérifier que le badge de la cloche affiche 1, que le panneau liste la notification, et que cliquer dessus ouvre directement la tâche concernée (dépliée, scrollée à l'écran) et marque la notification comme lue (badge repasse à 0). Répéter le scénario pour un commentaire sur un incident assigné.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/layout/Topbar.tsx frontend/src/layout/AppShell.tsx frontend/src/App.tsx
git commit -m "feat(notifications): navigate to the linked task/incident on notification click"
```

---

## Self-Review

**Spec coverage :** "Système de notifications (interne à l'app/mail)" → couvert : canal in-app (cloche + panneau + compteur non lu) et email (synchrone, backend configurable), sur les deux déclencheurs à destinataire non ambigu identifiés (assignation de tâche, nouveau commentaire sur tâche/incident assigné). Architecture signal-based conforme à CLAUDE.md.

**Placeholder scan :** aucun "TODO" ; Task 2/Step 1 contient un premier jet volontairement imparfait (lambda non déconnectable) explicitement corrigé dans le même step, comme dans le plan "audit-history" précédent — le code final à utiliser est sans ambiguïté.

**Type consistency :** `task_assigned`/`task_commented`/`incident_commented` (Task 2) ↔ mêmes noms de kwargs (`task`, `comment`, `actor`/`incident`) repris tels quels dans les receivers (Task 3) ↔ `notify_*` (Task 3) ↔ `Notification`/`NotificationSerializer` (Task 1/4) ↔ `getNotifications`/`markNotificationRead`/etc. (Task 5) ↔ props `NotificationsDropdown` (Task 6) ↔ `focusTaskId`/`handleNavigate` (Task 7/8) — vocabulaire cohérent de bout en bout.

**Risque identifié, à surveiller en revue de Task 8 :** la chaîne de props `onNavigate` entre `App.tsx` → `AppShell` → `Topbar` n'a pas été vérifiée en détail avant l'écriture de ce plan (contrairement au reste, entièrement lu) — Task 8/Step 1 demande explicitement de la lire avant de coder, plutôt que de supposer sa forme exacte.
