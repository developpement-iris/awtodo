# Historique / audit des modifications — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tracer, champ par champ, qui a modifié quoi et quand sur une tâche ou un incident — remplace le placeholder statique déjà présent dans `TaskAccordion` ("Un historique détaillé... n'existe pas encore côté backend") par un vrai historique, et ajoute la même chose côté incidents (qui n'a pas encore de section "Historique" du tout).

**Architecture:** Un seul modèle générique `AuditLogEntry` dans `apps/common` (relation générique Django via `ContentType`/`GenericForeignKey`, pas un modèle dupliqué par entité) — cohérent avec la hiérarchie de dépendances du projet (`apps.common` ne dépend de rien, `apps.tasks`/`apps.incidents` peuvent en dépendre). Un utilitaire `record_changes(instance, actor=...)`, context manager qui capture l'état de chaque champ avant/après la mutation et journalise automatiquement tout champ qui a changé — pas besoin de lister les champs à la main dans chaque fonction de service, un seul `with record_changes(...):` enveloppant le corps déjà existant de chaque fonction. Résout aussi la lisibilité des `choices` (statut, priorité, type) en passant par `field.choices` de Django, générique, sans code spécifique par modèle.

**Tech Stack:** Django + `django.contrib.contenttypes` (déjà installé) côté backend, React + TypeScript côté frontend. Aucune nouvelle dépendance externe.

## Global Constraints

- Toute logique métier vit dans `services.py`, jamais dans serializers/vues (CLAUDE.md règle n°1).
- `apps.common` ne doit jamais importer une app "haute" (`apps.tasks`, `apps.incidents`...) — le sens de dépendance reste `common` → `tasks`/`incidents`, jamais l'inverse (CLAUDE.md > "Règle de dépendances entre apps").
- PK en UUID sur tout modèle exposé via l'API (CLAUDE.md règle n°4).
- Le frontend ne recalcule jamais une règle métier — il affiche ce que l'API renvoie (CLAUDE.md > "Permissions API — flags calculés", même principe étendu à l'affichage de données calculées côté serveur).
- Toute app a ses tests dans `tests/` (CLAUDE.md règle n°7).
- **Limite assumée pour cette passe, à documenter dans le code :** les valeurs de champs à relation (assigné, projet, groupe) sont journalisées sous forme d'UUID brut, pas résolues en nom lisible — éviter la résolution d'affichage a posteriori (l'objet référencé a pu changer de nom depuis, voire ne plus exister) reste hors périmètre de cette passe.

---

## File Structure

- `apps/common/models.py` — ajoute `AuditLogEntry` (relation générique vers n'importe quel modèle).
- `apps/common/migrations/0001_initial.py` — première migration de cette app (auto-générée).
- `apps/common/audit.py` — nouveau fichier : `record_changes(instance, *, actor)` (context manager) + `get_audit_log(instance)` (queryset générique).
- `apps/common/serializers.py` — nouveau fichier : `AuditLogEntrySerializer` (partagé par tasks et incidents).
- `apps/common/tests/test_audit.py` — nouveau fichier : tests du mécanisme générique.
- `apps/tasks/services.py` — enveloppe les 8 fonctions de mutation existantes (`rename_task`, `update_task_description`, `validate_task`, `reject_task`, `claim_task`, `assign_task`, `start_task`, `complete_task`) dans `record_changes`.
- `apps/tasks/serializers.py` — `TaskDetailSerializer` gagne un champ `audit_log`.
- `apps/tasks/tests/test_audit.py` — nouveau fichier : tests d'intégration (service + API) côté tâches.
- `apps/incidents/services.py` — enveloppe les 7 fonctions de mutation existantes (`assign_incident_to_project`, `start_incident`, `resolve_incident`, `archive_incident`, `update_incident_description`, `claim_incident`, `update_incident_priority`) dans `record_changes`.
- `apps/incidents/serializers.py` — `IncidentDetailSerializer` gagne un champ `audit_log`.
- `apps/incidents/tests/test_audit.py` — nouveau fichier : tests d'intégration côté incidents.
- `frontend/src/types/watodo.ts` — ajoute `AuditLogEntry`, étend `TaskDetail`/`IncidentDetail` avec `audit_log: AuditLogEntry[]`.
- `frontend/src/lib/auditFieldLabels.ts` — nouveau fichier : dictionnaire `nom de champ Django → libellé français`, partagé tâches/incidents.
- `frontend/src/features/tasks/TaskAccordion.tsx` + `.css` — remplace le placeholder statique de la section "Historique" par le rendu réel.
- `frontend/src/features/incidents/IncidentAccordion.tsx` + `.css` — ajoute une nouvelle section "Historique" (n'existe pas encore côté incidents).

---

### Task 1: Modèle générique `AuditLogEntry` + migration

**Files:**
- Modify: `apps/common/models.py`
- Create: `apps/common/migrations/0001_initial.py` (auto-générée)
- Test: `apps/common/tests/test_audit.py`

**Interfaces:**
- Produces: `AuditLogEntry` (champs `content_type`, `object_id`, `content_object` [GenericForeignKey], `actor`, `field_name`, `old_value`, `new_value`, `id`/`created_at`/`updated_at` hérités) — consommé par Task 2 (`record_changes`/`get_audit_log`).

- [ ] **Step 1: Write the failing test**

Créer `apps/common/tests/test_audit.py` :

```python
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.accounts.models import User
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.common.tests.test_audit -v 2`
Expected: FAIL avec `ImportError: cannot import name 'AuditLogEntry' from 'apps.common.models'`

- [ ] **Step 3: Write minimal implementation**

Ajouter en haut de `apps/common/models.py` :

```python
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
```

Ajouter à la fin du fichier :

```python
class AuditLogEntry(UUIDModel, TimeStampedModel):
    """Historique champ par champ, générique à n'importe quel modèle métier
    (Task, Incident, plus tard Project si le besoin se confirme) — une seule
    table plutôt qu'un modèle dupliqué par entité, via les content types
    Django. Alimentée exclusivement par `apps.common.audit.record_changes`,
    jamais créée à la main dans un serializer/une vue (CLAUDE.md règle n°1).
    Pas de StatusLifecycleModel : une entrée d'audit est un fait immuable une
    fois écrite, jamais éditée ni "archivée" — pas d'état terminal à
    distinguer d'un état actif."""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="audit_entries")
    field_name = models.CharField(max_length=100)
    # Valeurs déjà mises en forme lisible (résolution des `choices` faite à
    # l'écriture par `record_changes`, voir apps/common/audit.py) — chaînes
    # vides plutôt que `None`, jamais littéralement "None" affiché.
    old_value = models.TextField(blank=True, default="")
    new_value = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.field_name}: {self.old_value!r} → {self.new_value!r} ({self.actor})"
```

- [ ] **Step 4: Generate and apply the migration**

Run: `python manage.py makemigrations common`
Expected: `Migrations for 'common': apps\common\migrations\0001_initial.py — + Create model AuditLogEntry`

Run: `python manage.py migrate common`
Expected: `Applying common.0001_initial... OK`

- [ ] **Step 5: Run test to verify it passes**

Run: `python manage.py test apps.common.tests.test_audit -v 2`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/common/models.py apps/common/migrations/0001_initial.py apps/common/tests/test_audit.py
git commit -m "feat(common): add generic AuditLogEntry model"
```

---

### Task 2: `record_changes` (context manager) + `get_audit_log`

**Files:**
- Create: `apps/common/audit.py`
- Test: `apps/common/tests/test_audit.py`

**Interfaces:**
- Consumes: `AuditLogEntry` (Task 1).
- Produces: `record_changes(instance, *, actor)` (context manager, aucune valeur de retour utile) ; `get_audit_log(instance) -> QuerySet[AuditLogEntry]` (triées par `created_at`, `select_related("actor")`) — consommés par Task 3 (tâches) et Task 4 (incidents).

- [ ] **Step 1: Write the failing test**

Ajouter à `apps/common/tests/test_audit.py` :

```python
from apps.common.audit import get_audit_log, record_changes


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.common.tests.test_audit.RecordChangesTests -v 2`
Expected: FAIL avec `ImportError: cannot import name 'record_changes' from 'apps.common.audit'` (le fichier n'existe pas encore)

- [ ] **Step 3: Write minimal implementation**

Créer `apps/common/audit.py` :

```python
from contextlib import contextmanager

from django.contrib.contenttypes.models import ContentType

from .models import AuditLogEntry

# Jamais pertinents à journaliser : la PK ne change jamais, les deux
# horodatages changent à *chaque* sauvegarde (bruit garanti, pas un vrai
# changement métier).
EXCLUDED_FIELDS = {"id", "created_at", "updated_at"}


def _display_value(field, raw_value):
    """Résout une valeur brute de champ en libellé lisible — générique à
    n'importe quel champ `choices=` (statut, priorité, type...), sans code
    spécifique par modèle : Django expose déjà `field.choices`."""
    if raw_value is None:
        return ""
    if field.choices:
        return str(dict(field.choices).get(raw_value, raw_value))
    return str(raw_value)


@contextmanager
def record_changes(instance, *, actor):
    """Capture l'état de chaque champ de `instance` avant le bloc, puis
    journalise dans `AuditLogEntry` tout champ qui a changé après le bloc
    (typiquement une mutation suivie d'un `.save()`). Usage :

        with record_changes(task, actor=actor):
            task.status = "en_cours"
            task.save()

    Comparaison sur `field.attname` (ex. `assignee_id`), pas `field.name` :
    évite de déclencher une requête pour résoudre l'objet lié juste pour le
    comparer — seul l'identifiant compte pour détecter un changement."""
    fields = [f for f in instance._meta.fields if f.attname not in EXCLUDED_FIELDS]
    before = {f.attname: getattr(instance, f.attname) for f in fields}

    yield

    content_type = ContentType.objects.get_for_model(type(instance))
    for field in fields:
        old_raw = before[field.attname]
        new_raw = getattr(instance, field.attname)
        if old_raw == new_raw:
            continue
        AuditLogEntry.objects.create(
            content_type=content_type,
            object_id=instance.id,
            actor=actor,
            field_name=field.name,
            old_value=_display_value(field, old_raw),
            new_value=_display_value(field, new_raw),
        )


def get_audit_log(instance):
    content_type = ContentType.objects.get_for_model(type(instance))
    return AuditLogEntry.objects.filter(content_type=content_type, object_id=instance.id).select_related("actor")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.common.tests.test_audit -v 2`
Expected: PASS (4 tests au total dans ce fichier)

- [ ] **Step 5: Commit**

```bash
git add apps/common/audit.py apps/common/tests/test_audit.py
git commit -m "feat(common): add record_changes context manager and get_audit_log"
```

---

### Task 3: Câblage côté tâches (service + serializer + endpoint)

**Files:**
- Modify: `apps/tasks/services.py`
- Modify: `apps/tasks/serializers.py`
- Create: `apps/common/serializers.py`
- Test: `apps/tasks/tests/test_audit.py`

**Interfaces:**
- Consumes: `record_changes`, `get_audit_log` (Task 2).
- Produces: `AuditLogEntrySerializer` (dans `apps/common/serializers.py`, réutilisé par Task 4) ; `TaskDetailSerializer.audit_log` — consommé par le frontend (Task 5).

- [ ] **Step 1: Write the failing test**

Créer `apps/tasks/tests/test_audit.py` :

```python
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task
from apps.tasks.services import rename_task, start_task, validate_task


class TaskAuditServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.manager = User.objects.create_user(username="manager-audit")
        self.member = User.objects.create_user(username="member-audit")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Titre initial", task_type="correction"
        )

    def test_rename_task_logs_title_change(self):
        rename_task(actor=self.member, task=self.task, title="Nouveau titre")

        entry = self.task.audit_entries().get(field_name="title") if False else None  # placeholder guard, see below
```

Remplacer immédiatement ce dernier test par la version réelle (le placeholder ci-dessus sert uniquement à documenter l'intention — utiliser `get_audit_log` directement) :

```python
from apps.common.audit import get_audit_log


class TaskAuditServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.manager = User.objects.create_user(username="manager-audit")
        self.member = User.objects.create_user(username="member-audit")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Titre initial", task_type="correction"
        )

    def test_rename_task_logs_title_change(self):
        rename_task(actor=self.member, task=self.task, title="Nouveau titre")

        entries = list(get_audit_log(self.task))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].field_name, "title")
        self.assertEqual(entries[0].old_value, "Titre initial")
        self.assertEqual(entries[0].new_value, "Nouveau titre")
        self.assertEqual(entries[0].actor, self.member)

    def test_validate_task_logs_status_with_display_label(self):
        validate_task(actor=self.manager, task=self.task)

        entry = get_audit_log(self.task).get(field_name="status")
        self.assertEqual(entry.old_value, "En attente de validation")
        self.assertEqual(entry.new_value, "Disponible")


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
class TaskAuditApiTests(APITestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.member = User.objects.create_user(username="member-audit-api")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Titre initial", task_type="correction"
        )

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_detail_includes_audit_log(self):
        self.client.post(
            f"/api/v1/tasks/{self.task.id}/rename/", {"title": "Titre modifié"}, **self.as_user(self.member)
        )

        response = self.client.get(f"/api/v1/tasks/{self.task.id}/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        audit_log = response.json()["audit_log"]
        self.assertEqual(len(audit_log), 1)
        self.assertEqual(audit_log[0]["field_name"], "title")
        self.assertEqual(audit_log[0]["new_value"], "Titre modifié")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.tasks.tests.test_audit -v 2`
Expected: FAIL — `get_audit_log(self.task)` renvoie une liste vide (`rename_task` ne journalise encore rien)

- [ ] **Step 3: Write minimal implementation**

Créer `apps/common/serializers.py` :

```python
from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import AuditLogEntry


class AuditLogEntrySerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)

    class Meta:
        model = AuditLogEntry
        fields = ["id", "actor", "field_name", "old_value", "new_value", "created_at"]
```

Dans `apps/tasks/services.py`, ajouter l'import :

```python
from apps.common.audit import record_changes
```

Envelopper le corps mutant de chacune des 8 fonctions suivantes dans `with record_changes(task, actor=actor):` — la garde (`_ensure_can_*`) et toute validation restent **avant** le `with`, seule la mutation + le `.save()` entrent dedans. Exemple pour `rename_task` :

```python
def rename_task(*, actor, task, title):
    _ensure_can_rename(actor, task)
    if not title or not title.strip():
        raise InvalidTransitionError("Le titre ne peut pas être vide.")

    with record_changes(task, actor=actor):
        task.title = title.strip()
        task.save()
    return task
```

Appliquer le même principe (garde/validation hors du `with`, mutation dedans) à :
- `update_task_description` (`task.description = ...; task.save()`)
- `validate_task` (`task.status = ...; task.assignee = ...; task.save()`)
- `reject_task` (`task.status = ...; task.rejection_reason = ...; task.save()`)
- `claim_task` (`task.status = ...; task.assignee = ...; task.save()`)
- `assign_task` (`task.status = ...; task.assignee = ...; task.save()`)
- `start_task` (`task.status = ...; task.save()`)
- `complete_task` (`task.status = ...; task.time_spent = ...; task.save()`)

Dans `apps/tasks/serializers.py`, ajouter l'import :

```python
from apps.common.audit import get_audit_log
from apps.common.serializers import AuditLogEntrySerializer
```

Étendre `TaskDetailSerializer` :

```python
class TaskDetailSerializer(TaskSerializer):
    comments = TaskCommentSerializer(many=True, read_only=True)
    audit_log = serializers.SerializerMethodField()

    class Meta(TaskSerializer.Meta):
        fields = TaskSerializer.Meta.fields + ["comments", "audit_log"]

    def get_audit_log(self, obj):
        return AuditLogEntrySerializer(get_audit_log(obj), many=True).data
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.tasks.tests.test_audit -v 2`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `python manage.py test`
Expected: tous les tests passent (375 avant cette passe + les nouveaux)

- [ ] **Step 6: Commit**

```bash
git add apps/common/serializers.py apps/tasks/services.py apps/tasks/serializers.py apps/tasks/tests/test_audit.py
git commit -m "feat(tasks): record field-level audit log on every mutation, expose via audit_log"
```

---

### Task 4: Câblage côté incidents (service + serializer)

**Files:**
- Modify: `apps/incidents/services.py`
- Modify: `apps/incidents/serializers.py`
- Test: `apps/incidents/tests/test_audit.py`

**Interfaces:**
- Consumes: `record_changes`, `get_audit_log` (Task 2), `AuditLogEntrySerializer` (Task 3).
- Produces: `IncidentDetailSerializer.audit_log` — consommé par le frontend (Task 5).

- [ ] **Step 1: Write the failing test**

Créer `apps/incidents/tests/test_audit.py` :

```python
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Team, TeamMembership, User
from apps.common.audit import get_audit_log
from apps.incidents.models import Incident
from apps.incidents.services import resolve_incident, start_incident


class IncidentAuditServiceTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Équipe Test Audit")
        self.member = User.objects.create_user(username="member-incident-audit")
        TeamMembership.objects.create(team=self.team, user=self.member)
        self.incident = Incident.objects.create(team=self.team, title="Panne réseau")

    def test_start_incident_logs_status_with_display_label(self):
        start_incident(actor=self.member, incident=self.incident)

        entry = get_audit_log(self.incident).get(field_name="status")
        self.assertEqual(entry.old_value, "Signalé")
        self.assertEqual(entry.new_value, "En cours")

    def test_two_transitions_produce_two_entries_in_order(self):
        start_incident(actor=self.member, incident=self.incident)
        resolve_incident(actor=self.member, incident=self.incident)

        entries = list(get_audit_log(self.incident))
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].new_value, "En cours")
        self.assertEqual(entries[1].new_value, "Résolu")


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
class IncidentAuditApiTests(APITestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Équipe Test Audit API")
        self.member = User.objects.create_user(username="member-incident-audit-api")
        TeamMembership.objects.create(team=self.team, user=self.member)
        self.incident = Incident.objects.create(team=self.team, title="Panne réseau")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_detail_includes_audit_log(self):
        self.client.post(f"/api/v1/incidents/{self.incident.id}/start/", **self.as_user(self.member))

        response = self.client.get(f"/api/v1/incidents/{self.incident.id}/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        audit_log = response.json()["audit_log"]
        self.assertEqual(len(audit_log), 1)
        self.assertEqual(audit_log[0]["field_name"], "status")
        self.assertEqual(audit_log[0]["new_value"], "En cours")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.incidents.tests.test_audit -v 2`
Expected: FAIL — aucune entrée journalisée (`start_incident` ne journalise encore rien)

- [ ] **Step 3: Write minimal implementation**

Dans `apps/incidents/services.py`, ajouter l'import :

```python
from apps.common.audit import record_changes
```

Envelopper le corps mutant de chacune des 7 fonctions suivantes dans `with record_changes(incident, actor=actor):` — même principe que Task 3 (garde/validation hors du `with`, mutation dedans) :
- `assign_incident_to_project` (`incident.project = ...; incident.team = ...; incident.save(...)`)
- `start_incident` (`incident.status = ...; incident.save()`)
- `resolve_incident` (`incident.status = ...; incident.save()`)
- `archive_incident` (`incident.status = ...; incident.save()`)
- `update_incident_description` (`incident.description = ...; incident.save()`)
- `claim_incident` (`incident.assigned_to = ...; incident.save(...)`)
- `update_incident_priority` (`incident.priority = ...; incident.save(...)`)

Exemple pour `start_incident` :

```python
def start_incident(*, actor, incident):
    _ensure_can_start(actor, incident)

    with record_changes(incident, actor=actor):
        incident.status = "en_cours"
        incident.save()
    return incident
```

Dans `apps/incidents/serializers.py`, ajouter l'import :

```python
from apps.common.audit import get_audit_log
from apps.common.serializers import AuditLogEntrySerializer
```

Étendre `IncidentDetailSerializer` :

```python
class IncidentDetailSerializer(IncidentSerializer):
    comments = IncidentCommentSerializer(many=True, read_only=True)
    audit_log = serializers.SerializerMethodField()

    class Meta(IncidentSerializer.Meta):
        fields = IncidentSerializer.Meta.fields + ["comments", "audit_log"]

    def get_audit_log(self, obj):
        return AuditLogEntrySerializer(get_audit_log(obj), many=True).data
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.incidents.tests.test_audit -v 2`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `python manage.py test`
Expected: tous les tests passent (378 avant cette passe + les nouveaux)

- [ ] **Step 6: Commit**

```bash
git add apps/incidents/services.py apps/incidents/serializers.py apps/incidents/tests/test_audit.py
git commit -m "feat(incidents): record field-level audit log on every mutation, expose via audit_log"
```

---

### Task 5: Types + client frontend

**Files:**
- Modify: `frontend/src/types/watodo.ts`
- Create: `frontend/src/lib/auditFieldLabels.ts`

**Interfaces:**
- Consumes: réponses JSON de `AuditLogEntrySerializer` (Task 3/4).
- Produces: `AuditLogEntry` (type), `TaskDetail.audit_log`, `IncidentDetail.audit_log`, `auditFieldLabel(fieldName: string): string` — consommés par Task 6 et Task 7.

- [ ] **Step 1: Add the type**

Dans `frontend/src/types/watodo.ts`, ajouter (avant `export interface TaskDetail`) :

```typescript
export interface AuditLogEntry {
  id: string;
  actor: User;
  field_name: string;
  old_value: string;
  new_value: string;
  created_at: string;
}
```

Modifier `TaskDetail` :

```typescript
export interface TaskDetail extends Task {
  comments: TaskComment[];
  audit_log: AuditLogEntry[];
}
```

Modifier `IncidentDetail` :

```typescript
export interface IncidentDetail extends Incident {
  comments: IncidentComment[];
  audit_log: AuditLogEntry[];
}
```

- [ ] **Step 2: Add the field label dictionary**

Créer `frontend/src/lib/auditFieldLabels.ts` :

```typescript
// Libellés français pour les noms de champs Django bruts renvoyés par
// `AuditLogEntry.field_name` (voir apps/common/audit.py) — partagé entre
// tâches et incidents, un champ absent du dictionnaire s'affiche tel quel
// (fallback volontaire, pas une erreur).
const AUDIT_FIELD_LABELS: Record<string, string> = {
  title: "Titre",
  description: "Description",
  status: "Statut",
  priority: "Priorité",
  task_type: "Type",
  deadline: "Échéance",
  assignee_id: "Assigné à",
  assigned_to_id: "Assigné à",
  time_spent: "Temps passé",
  rejection_reason: "Motif de rejet",
  project_id: "Projet",
  team_id: "Groupe",
  external_reference_id: "Référence externe",
};

export function auditFieldLabel(fieldName: string): string {
  return AUDIT_FIELD_LABELS[fieldName] ?? fieldName;
}
```

- [ ] **Step 3: Verify the frontend compiles**

Run: `cd frontend && npm run build`
Expected: build réussi, aucune erreur TypeScript

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/watodo.ts frontend/src/lib/auditFieldLabels.ts
git commit -m "feat: add AuditLogEntry type and field label dictionary"
```

---

### Task 6: Brancher la section "Historique" de `TaskAccordion`

**Files:**
- Modify: `frontend/src/features/tasks/TaskAccordion.tsx`
- Modify: `frontend/src/features/tasks/TaskAccordion.css`
- Modify: `frontend/src/features/tasks/TasksListPage.tsx`

**Interfaces:**
- Consumes: `getTask` (déjà utilisé par la passe "Commentaires", renvoie maintenant aussi `audit_log`), `AuditLogEntry`, `auditFieldLabel` (Task 5).
- Produces: rien de nouveau consommé ailleurs.

- [ ] **Step 1: Thread `auditLog` down from `TasksListPage`**

Dans `frontend/src/features/tasks/TasksListPage.tsx`, l'effet qui appelle déjà `getTask(expandedTaskId)` (ajouté par la passe précédente pour charger `comments`) reçoit maintenant aussi `audit_log` dans la même réponse. Ajouter un état :

```typescript
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
```

Importer `AuditLogEntry` depuis `../../types/watodo`.

Dans l'effet existant (`useEffect(() => { if (!expandedTaskId) return; ... getTask(expandedTaskId).then((data) => { ... }) ... }, [expandedTaskId])`), ajouter la capture :

```typescript
    getTask(expandedTaskId)
      .then((data) => {
        if (!cancelled) {
          setComments(data.comments);
          setAuditLog(data.audit_log);
        }
      })
```

Réinitialiser `setAuditLog([])` à côté de `setComments(null)` en tête d'effet.

Passer la prop au rendu de `<TaskAccordion>` : `auditLog={auditLog}`.

- [ ] **Step 2: Update `TaskAccordion` props and replace the static "Historique" section**

Dans `frontend/src/features/tasks/TaskAccordion.tsx`, ajouter l'import :

```typescript
import { auditFieldLabel } from "../../lib/auditFieldLabels";
import type { AuditLogEntry, Task, TaskComment, User } from "../../types/watodo";
```

Ajouter `auditLog: AuditLogEntry[];` à `TaskAccordionProps` (après `onSaveDescription`, avant les props commentaires ajoutées par la passe précédente) et au paramètre déstructuré.

Remplacer la section :

```tsx
        <section className="task-accordion__section">
          <h3 className="task-accordion__section-title">Historique</h3>
          <p className="task-accordion__meta">
            Dernière modification : {new Date(task.updated_at).toLocaleDateString("fr-FR")}
          </p>
          <p className="task-accordion__meta-note">
            Un historique détaillé des transitions n'existe pas encore côté backend (hors périmètre v1) —
            seule la dernière modification est disponible.
          </p>
        </section>
```

par :

```tsx
        <section className="task-accordion__section">
          <h3 className="task-accordion__section-title">Historique</h3>
          {auditLog.length === 0 ? (
            <p className="task-accordion__empty">Aucune modification enregistrée.</p>
          ) : (
            <ul className="task-accordion__audit-list">
              {auditLog.map((entry) => (
                <li key={entry.id} className="task-accordion__audit-entry">
                  <span className="task-accordion__audit-field">{auditFieldLabel(entry.field_name)}</span>
                  <span className="task-accordion__audit-change">
                    {entry.old_value || "—"} → {entry.new_value || "—"}
                  </span>
                  <span className="task-accordion__audit-meta">
                    {displayName(entry.actor)} ·{" "}
                    <time dateTime={entry.created_at} title={new Date(entry.created_at).toLocaleString("fr-FR")}>
                      {new Date(entry.created_at).toLocaleDateString("fr-FR")}
                    </time>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
```

- [ ] **Step 3: Add the CSS**

Ajouter à `frontend/src/features/tasks/TaskAccordion.css` (mêmes tokens que le reste du fichier — `var(--color-border)`, `var(--color-text-muted)`, `var(--space-*)`, cohérent avec `.task-accordion__comment-*` déjà en place) :

```css
.task-accordion__audit-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.task-accordion__audit-entry {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 13px;
}

.task-accordion__audit-entry:last-child {
  border-bottom: none;
}

.task-accordion__audit-field {
  font-weight: 600;
  flex: 0 0 auto;
}

.task-accordion__audit-change {
  color: var(--color-text-muted);
  flex: 1 1 auto;
}

.task-accordion__audit-meta {
  flex: 0 0 auto;
  font-size: 12px;
  color: var(--color-text-muted);
}
```

- [ ] **Step 4: Verify the frontend compiles**

Run: `cd frontend && npm run build`
Expected: build réussi, aucune erreur TypeScript

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/tasks/TaskAccordion.tsx frontend/src/features/tasks/TaskAccordion.css frontend/src/features/tasks/TasksListPage.tsx
git commit -m "feat(tasks): wire real audit log into TaskAccordion Historique section"
```

---

### Task 7: Ajouter la section "Historique" à `IncidentAccordion`

**Files:**
- Modify: `frontend/src/features/incidents/IncidentAccordion.tsx`
- Modify: `frontend/src/features/incidents/IncidentAccordion.css`
- Modify: `frontend/src/features/incidents/IncidentsPage.tsx`

**Interfaces:**
- Consumes: `getIncident` (déjà utilisé pour charger `comments`, renvoie maintenant aussi `audit_log`), `AuditLogEntry`, `auditFieldLabel` (Task 5).
- Produces: rien de nouveau consommé ailleurs — dernier maillon de ce plan.

**Contrairement à `TaskAccordion`, il n'existe aujourd'hui aucune section "Historique" dans `IncidentAccordion` — celle-ci est entièrement nouvelle, pas un remplacement.**

- [ ] **Step 1: Thread `auditLog` down from `IncidentsPage`**

Dans `frontend/src/features/incidents/IncidentsPage.tsx`, même principe que Task 6/Step 1 : ajouter `const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);`, importer `AuditLogEntry`, capturer `data.audit_log` dans le `.then()` de l'effet qui appelle déjà `getIncident(expandedIncidentId)`, réinitialiser à `[]` en tête d'effet, passer `auditLog={auditLog}` au rendu de `<IncidentAccordion>`.

- [ ] **Step 2: Add the section to `IncidentAccordion`**

Dans `frontend/src/features/incidents/IncidentAccordion.tsx`, ajouter l'import :

```typescript
import { auditFieldLabel } from "../../lib/auditFieldLabels";
import type { AuditLogEntry, Incident, IncidentComment, Project } from "../../types/watodo";
```

Ajouter `auditLog: AuditLogEntry[];` à `IncidentAccordionProps` (après `onSaveDescription`) et au paramètre déstructuré.

Ajouter une nouvelle section entre "Description" et "Commentaires" :

```tsx
        <section className="incident-accordion__section">
          <h3 className="incident-accordion__section-title">Historique</h3>
          {auditLog.length === 0 ? (
            <p className="incident-accordion__empty">Aucune modification enregistrée.</p>
          ) : (
            <ul className="incident-accordion__audit-list">
              {auditLog.map((entry) => (
                <li key={entry.id} className="incident-accordion__audit-entry">
                  <span className="incident-accordion__audit-field">{auditFieldLabel(entry.field_name)}</span>
                  <span className="incident-accordion__audit-change">
                    {entry.old_value || "—"} → {entry.new_value || "—"}
                  </span>
                  <span className="incident-accordion__audit-meta">
                    {`${entry.actor.first_name} ${entry.actor.last_name}`.trim() || entry.actor.username} ·{" "}
                    <time dateTime={entry.created_at} title={new Date(entry.created_at).toLocaleString("fr-FR")}>
                      {new Date(entry.created_at).toLocaleDateString("fr-FR")}
                    </time>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
```

- [ ] **Step 3: Add the CSS**

Ajouter à `frontend/src/features/incidents/IncidentAccordion.css` les mêmes règles qu'à la Task 6/Step 3, préfixe `incident-accordion__` au lieu de `task-accordion__` (mêmes valeurs, mêmes tokens — les deux fichiers CSS partagent déjà les mêmes variables de thème).

- [ ] **Step 4: Verify the frontend compiles**

Run: `cd frontend && npm run build`
Expected: build réussi, aucune erreur TypeScript

- [ ] **Step 5: Manual smoke test**

Démarrer `python manage.py runserver` et `npm run dev`, déplier une tâche puis un incident dont on est membre, effectuer une transition de statut (ex. Démarrer), rouvrir l'accordéon, vérifier que la section Historique affiche bien l'entrée avec le libellé de statut lisible ("En cours", pas `en_cours`).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/incidents/IncidentAccordion.tsx frontend/src/features/incidents/IncidentAccordion.css frontend/src/features/incidents/IncidentsPage.tsx
git commit -m "feat(incidents): add Historique section to IncidentAccordion"
```

---

## Self-Review

**Spec coverage :** "Historique/audit détaillé des changements de statut", tranché en amont sur "champ par champ" (pas seulement le statut) — couvert : les 8 mutations de `Task` et les 7 mutations d'`Incident` sont toutes journalisées, tout champ qui change (pas seulement `status`), avec résolution automatique des libellés `choices`. Section UI ajoutée aux deux accordéons.

**Placeholder scan :** aucun "TODO" — un faux départ a été laissé visible dans Task 3/Step 1 (bloc de test à jeter) uniquement pour documenter *pourquoi* la version finale est écrite ainsi ; la version réelle qui suit immédiatement contient le code complet à utiliser tel quel.

**Type consistency :** `record_changes(instance, *, actor)`/`get_audit_log(instance)` (Task 2) ↔ mêmes noms et signatures utilisés tels quels dans `apps/tasks/services.py` et `apps/incidents/services.py` (Tasks 3/4) ↔ `AuditLogEntrySerializer` (Task 3, réutilisé Task 4) ↔ `AuditLogEntry`/`audit_log`/`auditFieldLabel` (Task 5) ↔ props `auditLog` sur les deux accordéons (Tasks 6/7) — vocabulaire identique de bout en bout, y compris entre les deux entités jumelles (tâches/incidents), pour ne pas diverger comme ça a été fait pour "commentaires".

**Limite assumée, redite ici pour visibilité :** les champs à relation (`assignee_id`, `project_id`, `team_id`) restent affichés en UUID brut dans `old_value`/`new_value` — pas de résolution en nom lisible dans cette passe (voir "Global Constraints").
