# Documentation de projet — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner à chaque projet un espace de documentation utilisateur, rédigé par le chef de projet, consultable en ligne via un lien public non devinable, avec un onglet « Fonctionnalités » et un onglet « Résolution d'incidents » amorçables automatiquement (cahier des charges, tâches livrées, incidents résolus).

**Architecture :** Nouvelle app Django `apps/documentation/` (dépend de `projects`, `tasks`, `incidents` ; rien ne dépend d'elle). Modèles à statut/cycle de vie (`brouillon`/`publie`/`archive`, aucune suppression physique). API DRF sous `/api/v1/docs/` : endpoints authentifiés réservés au chef de projet + un endpoint public `AllowAny` qui n'expose que le contenu publié. Deux signaux (`task_completed`, `incident_resolved`, tous deux nouveaux) alimentent une file « À documenter ». Frontend : nouvel onglet dans `ProjectDetailView` + page publique autonome détectée par match d'URL dans `App.tsx` (même mécanisme que les invitations). Export `.docx` côté navigateur (lib `docx` déjà présente) + CSS d'impression sur la page publique pour le PDF.

**Tech Stack :** Django 5.2 + DRF 3.17, `djangorestframework-simplejwt` (déjà en place), React + TypeScript + Vite, lib `docx` (frontend, déjà présente), `MarkdownView` existant. Tests : `python manage.py test` (unittest / `APITestCase`, PAS pytest).

## Global Constraints

- **PK en UUID** sur tous les modèles exposés via l'API — hériter de `apps.common.models.UUIDModel`.
- **Aucune suppression physique** : tout modèle métier hérite de `StatusLifecycleModel` et se termine par un statut terminal. La « suppression » d'une page/fiche = passage à `archive`.
- **Piège manager Django** : tout modèle concret héritant de `StatusLifecycleModel` DOIT déclarer dans son propre `Meta` :
  ```python
  default_manager_name = "all_objects"
  base_manager_name = "all_objects"
  ```
  (ne s'hérite pas — voir CLAUDE.md). Régression à couvrir par un test.
- **Logique métier dans `services.py`**, jamais dans les serializers/vues (CLAUDE.md règle 1).
- **Aucun appel synchrone externe** dans le flux HTTP (CLAUDE.md règle 2) — non concerné ici, tout est interne.
- **Règle de dépendances entre apps** : `apps/tasks` et `apps/incidents` ne doivent JAMAIS importer `apps/documentation`. Le lien tâche/incident → doc se fait par **signal Django** émis par `tasks`/`incidents` et consommé par `documentation`. `apps/documentation` peut importer `projects`, `tasks`, `incidents` (elle est au-dessus dans la hiérarchie).
- **Permissions par objet** : garde « chef de projet de CE projet » via `apps.projects.services.is_project_manager(user, project)`.
- **Versionning d'API** : tout sous `/api/v1/`.
- **API ouverte / documentée** : serializers explicites, pas de `Response` nu non typé sur les endpoints publics ; pas de nouveaux warnings `drf-spectacular`.
- **Exception actée** (nouvelle, à inscrire dans CLAUDE.md) : la règle « la connexion est la porte d'entrée obligatoire du site » admet **une** exception — les pages de documentation *publiées* sont lisibles sans compte via un lien contenant un token non devinable, révocable. Aucune autre donnée du projet (tâches, membres, budget, incidents bruts) n'est jamais exposée par ce canal.
- **Copie UI** : « Awtodo » (jamais « Watodo ») dans tout texte visible.
- **Nom de l'app Django** : `apps.documentation`, label d'app `documentation` (choix explicite de l'utilisateur — évite la confusion avec le dossier `docs/` interne du repo).
- **Arbre de pages limité à 2 niveaux** : une page racine et ses sous-pages directes ; une sous-page ne peut pas avoir elle-même de sous-page (garde en service). Décision produit : un sommaire public au-delà de 2 niveaux devient illisible.
- **Page publique** : suit le thème clair/sombre du visiteur (comme `HomePage`).

---

## File Structure

### Backend — `apps/documentation/` (nouvelle app)

| Fichier | Responsabilité |
|---|---|
| `apps/documentation/__init__.py` | vide |
| `apps/documentation/apps.py` | `DocumentationConfig`, `name = "apps.documentation"`, `label = "documentation"`, `ready()` importe `signals` |
| `apps/documentation/models.py` | `DocSpace`, `DocPage`, `DocEntry`, `PendingDocEntry` |
| `apps/documentation/services.py` | toute la logique : get/create space, lien public, CRUD pages, CRUD entrées (fonctionnalités + résolutions), seed-from-spec, from-pending, ignore-pending, agrégat public |
| `apps/documentation/serializers.py` | serializers authentifiés + serializers publics (lecture seule) |
| `apps/documentation/views.py` | `DocSpaceViewSet` (authentifié) + `PublicDocsView` (`AllowAny`) |
| `apps/documentation/signals.py` | récepteurs de `apps.tasks.signals.task_completed` et `apps.incidents.signals.incident_resolved` |
| `apps/documentation/urls.py` | routeur DRF + route publique |
| `apps/documentation/admin.py` | enregistrement basique des 4 modèles |
| `apps/documentation/migrations/__init__.py` + `0001_initial.py` | généré |
| `apps/documentation/tests/__init__.py` | vide |
| `apps/documentation/tests/test_models.py` | régression manager (`all_objects` vs `objects`) |
| `apps/documentation/tests/test_services.py` | permissions, publication, seed-from-spec, from-pending, garde 2 niveaux, agrégat public |
| `apps/documentation/tests/test_signals.py` | file alimentée seulement pour `ajout`/`evolution` (tâches) et incidents `resolu`, et seulement si `DocSpace` existe |
| `apps/documentation/tests/test_api.py` | CRUD authentifié + endpoint public (publié seulement, token révoqué → 404) |

### Backend — modifications

| Fichier | Modification |
|---|---|
| `config/settings/base.py:23` | ajouter `"apps.documentation"` à `INSTALLED_APPS` (après `"apps.notifications"`) |
| `config/urls.py:4-12` | ajouter `path("docs/", include("apps.documentation.urls"))` dans `api_v1_patterns` |
| `apps/tasks/signals.py` | ajouter `task_completed = django.dispatch.Signal()` (kwargs: `task`, `actor`) |
| `apps/tasks/services.py` (`complete_task`, ~l.490-494) | émettre `task_completed.send(sender=Task, task=task, actor=actor)` après le `with record_changes(...)` |
| `apps/incidents/signals.py` | ajouter `incident_resolved = django.dispatch.Signal()` (kwargs: `incident`, `actor`) |
| `apps/incidents/services.py` (`resolve_incident`, ~l.258-264) | émettre `incident_resolved.send(sender=Incident, incident=incident, actor=actor)` après le `with record_changes(...)` |
| `apps/projects/services.py` (~l.112, l.140, l.143) | ajouter `_ensure_can_edit_documentation`, `can_edit_documentation`, et la clé `"can_edit_documentation"` dans `get_project_permissions` |

### Frontend — nouveaux fichiers

| Fichier | Responsabilité |
|---|---|
| `frontend/src/features/projects/DocumentationTab.tsx` / `.css` | onglet hub : sous-nav Pages / Fonctionnalités / Résolution d'incidents / À documenter / Lien public |
| `frontend/src/features/docs/PublicDocsPage.tsx` / `.css` | page publique autonome (pas d'`AppShell`, pas de garde d'auth) + `@media print` |
| `frontend/src/features/docs/exportDocx.ts` | génération `.docx` de la doc complète (lib `docx`) |

### Frontend — modifications

| Fichier | Modification |
|---|---|
| `frontend/src/App.tsx:25` | `const PUBLIC_DOCS_PATH_PATTERN = /^\/docs\/([^/]+)\/?$/;` + branchement **avant** toute garde d'auth |
| `frontend/src/features/projects/ProjectDetailView.tsx:19-21,142-151` | onglet `"documentation"` (visible si `project.permissions.can_edit_documentation`) |
| `frontend/src/api/client.ts` | fonctions API doc (Task 8) |
| `frontend/src/types/watodo.ts` | types + `can_edit_documentation` sur `Project["permissions"]` |

### Docs internes

| Fichier | Modification |
|---|---|
| `CLAUDE.md` | entrée Roadmap datée + acter l'exception « pages publiques de doc » (section Auth) |
| `docs/modeles-et-api.md` | nouvelle section « Documentation de projet » |
| `docs/charte-graphique.md` | onglet Documentation + page publique (dont `@media print`) |

---

## Modèle de données (référence pour toutes les tasks)

```python
# apps/documentation/models.py
from django.conf import settings
from django.db import models
from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel


class DocSpace(UUIDModel, TimeStampedModel):
    """Un espace de documentation par projet. Pas de StatusLifecycleModel :
    l'espace n'est jamais 'terminé', il suit le projet. Créé à la demande
    (get_or_create) au premier accès à l'onglet Documentation."""
    project = models.OneToOneField(
        "projects.Project", on_delete=models.PROTECT, related_name="doc_space"
    )
    is_public = models.BooleanField(default=False)
    # Token non devinable ; None tant que le lien public n'a jamais été activé.
    # Révoquer = None + is_public=False. Régénérer = nouveau token.
    public_token = models.CharField(max_length=64, null=True, blank=True, unique=True)

    def __str__(self):
        return f"Documentation — {self.project.name}"


class DocPage(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    STATUS_CHOICES = [
        ("brouillon", "Brouillon"),
        ("publie", "Publié"),
        ("archive", "Archivé"),
    ]
    ACTIVE_STATUSES = frozenset({"brouillon", "publie"})

    space = models.ForeignKey(DocSpace, on_delete=models.PROTECT, related_name="pages")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)  # unique par espace (hors archivées)
    content = models.TextField(blank=True, default="")  # Markdown
    order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="brouillon")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["space", "slug"],
                condition=~models.Q(status="archive"),
                name="uniq_active_docpage_slug_per_space",
            )
        ]

    def __str__(self):
        return f"{self.space.project.name} — {self.title}"


class DocEntry(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Fiche structurée d'un onglet : 'fonctionnalite' (onglet Fonctionnalités)
    ou 'resolution' (onglet Résolution d'incidents). Même forme, même cycle de
    vie, un seul modèle avec un champ `kind` — pas deux modèles jumeaux."""
    STATUS_CHOICES = [
        ("brouillon", "Brouillon"),
        ("publie", "Publié"),
        ("archive", "Archivé"),
    ]
    ACTIVE_STATUSES = frozenset({"brouillon", "publie"})
    KIND_CHOICES = [
        ("fonctionnalite", "Fonctionnalité"),
        ("resolution", "Résolution d'incident"),
    ]
    SOURCE_CHOICES = [
        ("manuelle", "Manuelle"),
        ("tache", "Tâche"),
        ("incident", "Incident"),
        ("cahier_des_charges", "Cahier des charges"),
    ]

    space = models.ForeignKey(DocSpace, on_delete=models.PROTECT, related_name="entries")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")  # Markdown
    order = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default="manuelle")
    source_task = models.ForeignKey(
        "tasks.Task", null=True, blank=True, on_delete=models.SET_NULL, related_name="doc_entries"
    )
    source_incident = models.ForeignKey(
        "incidents.Incident", null=True, blank=True, on_delete=models.SET_NULL, related_name="doc_entries"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="brouillon")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.space.project.name} — [{self.kind}] {self.title}"


class PendingDocEntry(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """File 'À documenter'. Une tâche ajout/évolution livrée -> kind=fonctionnalite ;
    un incident résolu -> kind=resolution. Statut terminal = 'traitee' ou 'ignoree'."""
    STATUS_CHOICES = [
        ("en_attente", "En attente"),
        ("traitee", "Traitée"),
        ("ignoree", "Ignorée"),
    ]
    ACTIVE_STATUSES = frozenset({"en_attente"})
    KIND_CHOICES = DocEntry.KIND_CHOICES

    space = models.ForeignKey(DocSpace, on_delete=models.PROTECT, related_name="pending_entries")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    task = models.OneToOneField(
        "tasks.Task", null=True, blank=True, on_delete=models.PROTECT, related_name="doc_pending_entry"
    )
    incident = models.OneToOneField(
        "incidents.Incident", null=True, blank=True, on_delete=models.PROTECT, related_name="doc_pending_entry"
    )
    entry = models.ForeignKey(
        DocEntry, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="en_attente")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(task__isnull=False, incident__isnull=True)
                    | models.Q(task__isnull=True, incident__isnull=False)
                ),
                name="pendingdocentry_exactly_one_source",
            )
        ]

    def __str__(self):
        src = self.task or self.incident
        return f"À documenter — {src}"
```

`DocSpace` n'hérite PAS de `StatusLifecycleModel` → pas de `default_manager_name`/`base_manager_name`. Les trois autres, si.

---

## Task 1: App `apps/documentation/` — scaffold, modèles, migration, test de régression manager

**Files:**
- Create: `apps/documentation/__init__.py`, `apps.py`, `models.py`, `admin.py`, `signals.py` (stub), `tests/__init__.py`, `tests/test_models.py`, `migrations/__init__.py`
- Modify: `config/settings/base.py:23`

**Interfaces:**
- Produces: modèles `DocSpace`, `DocPage`, `DocEntry`, `PendingDocEntry` (champs ci-dessus). `DocPage.objects` (actifs) / `DocPage.all_objects` (tout), idem `DocEntry`, `PendingDocEntry`.

- [ ] **Step 1: Écrire le test qui échoue** — `apps/documentation/tests/test_models.py`

```python
from django.test import TestCase

from apps.documentation.models import DocEntry, DocPage, DocSpace
from apps.projects.models import Project


class DocManagerRegressionTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        self.space = DocSpace.objects.create(project=self.project)

    def test_archived_page_hidden_from_default_manager(self):
        DocPage.objects.create(space=self.space, title="Vivante", slug="vivante")
        DocPage.all_objects.create(space=self.space, title="Vieille", slug="vieille", status="archive")
        self.assertEqual(DocPage.objects.count(), 1)
        self.assertEqual(DocPage.all_objects.count(), 2)

    def test_reverse_relation_uses_all_objects(self):
        DocPage.all_objects.create(space=self.space, title="A", slug="a", status="archive")
        self.assertEqual(self.space.pages.count(), 1)

    def test_docentry_managers(self):
        DocEntry.all_objects.create(space=self.space, kind="fonctionnalite", title="F", status="archive")
        self.assertEqual(DocEntry.objects.count(), 0)
        self.assertEqual(DocEntry.all_objects.count(), 1)
```

- [ ] **Step 2: Lancer — doit échouer** : `python manage.py test apps.documentation.tests.test_models -v 2` → `ModuleNotFoundError`.

- [ ] **Step 3: Créer le scaffold**

`apps/documentation/__init__.py` : vide. `apps/documentation/migrations/__init__.py` : vide. `apps/documentation/tests/__init__.py` : vide.

`apps/documentation/apps.py` :
```python
from django.apps import AppConfig


class DocumentationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.documentation"
    label = "documentation"

    def ready(self):
        from . import signals  # noqa: F401
```

`apps/documentation/signals.py` : `# Récepteurs branchés en Task 5.`

`apps/documentation/models.py` : coller le bloc complet de la section « Modèle de données ».

`apps/documentation/admin.py` :
```python
from django.contrib import admin

from .models import DocEntry, DocPage, DocSpace, PendingDocEntry

admin.site.register([DocSpace, DocPage, DocEntry, PendingDocEntry])
```

- [ ] **Step 4: Enregistrer l'app** — `config/settings/base.py`, après `"apps.notifications",` ajouter `"apps.documentation",`.

- [ ] **Step 5: Migration** : `python manage.py makemigrations documentation && python manage.py migrate documentation`.

- [ ] **Step 6: Lancer le test — doit passer** : `python manage.py test apps.documentation.tests.test_models -v 2`.

- [ ] **Step 7: Suite complète** : `python manage.py test` → aucun échec.

- [ ] **Step 8: Commit**

```bash
git add apps/documentation config/settings/base.py
git commit -m "feat(documentation): app scaffold + models for project documentation

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: Services — espace, lien public (activer / régénérer / révoquer), garde chef de projet

**Files:**
- Create: `apps/documentation/services.py`
- Modify: `apps/projects/services.py`
- Test: `apps/documentation/tests/test_services.py`

**Interfaces:**
- Consumes: `apps.projects.services.is_project_manager`, `is_project_member`, `apps.projects.models.Project`.
- Produces:
  - `class DocsPermissionError(Exception)` / `class DocsValidationError(Exception)`
  - `get_or_create_space(*, actor, project) -> DocSpace` (garde : membre du projet)
  - `enable_public_link(*, actor, project) -> DocSpace` / `rotate_public_link(...)` / `revoke_public_link(...)` (garde : chef de projet)
  - `apps.projects.services.can_edit_documentation(user, project) -> bool`

- [ ] **Step 1: Tests qui échouent** — `apps/documentation/tests/test_services.py`

```python
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
```

- [ ] **Step 2: Lancer — échoue.**

- [ ] **Step 3: Implémenter `apps/documentation/services.py`**

```python
import secrets

from apps.projects.services import is_project_manager, is_project_member

from .models import DocEntry, DocPage, DocSpace, PendingDocEntry


class DocsPermissionError(Exception):
    pass


class DocsValidationError(Exception):
    pass


def _require_member(actor, project):
    if actor is None or not getattr(actor, "is_authenticated", False) or not is_project_member(actor, project):
        raise DocsPermissionError("Seul un membre du projet peut consulter sa documentation.")


def _require_manager(actor, project):
    if actor is None or not getattr(actor, "is_authenticated", False) or not is_project_manager(actor, project):
        raise DocsPermissionError("Seul un chef de projet peut modifier la documentation.")


def _generate_token():
    return secrets.token_urlsafe(32)


def get_or_create_space(*, actor, project):
    _require_member(actor, project)
    space, _ = DocSpace.objects.get_or_create(project=project)
    return space


def _space_for_manager(actor, project):
    _require_manager(actor, project)
    space, _ = DocSpace.objects.get_or_create(project=project)
    return space


def enable_public_link(*, actor, project):
    space = _space_for_manager(actor, project)
    if not space.public_token:
        space.public_token = _generate_token()
    space.is_public = True
    space.save(update_fields=["public_token", "is_public", "updated_at"])
    return space


def rotate_public_link(*, actor, project):
    space = _space_for_manager(actor, project)
    space.public_token = _generate_token()
    space.is_public = True
    space.save(update_fields=["public_token", "is_public", "updated_at"])
    return space


def revoke_public_link(*, actor, project):
    space = _space_for_manager(actor, project)
    space.public_token = None
    space.is_public = False
    space.save(update_fields=["public_token", "is_public", "updated_at"])
    return space
```

- [ ] **Step 4: `apps/projects/services.py`** — après `_ensure_can_manage_budget` :
```python
def _ensure_can_edit_documentation(actor, project):
    _require_manager(actor, project)
```
après `can_manage_budget` :
```python
def can_edit_documentation(user, project):
    return _check(_ensure_can_edit_documentation, user, project)
```
dans `get_project_permissions`, ajouter `"can_edit_documentation": can_edit_documentation(user, project),`.

- [ ] **Step 5: Tests** : `python manage.py test apps.documentation.tests.test_services apps.projects -v 2`. Si un test projet assert sur l'ensemble exact des clés de permissions, y ajouter `can_edit_documentation`.

- [ ] **Step 6: Suite complète** : `python manage.py test`.

- [ ] **Step 7: Commit**

```bash
git add apps/documentation/services.py apps/documentation/tests/test_services.py apps/projects/services.py
git commit -m "feat(documentation): space + public link services, can_edit_documentation flag

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: Services — CRUD pages (arbre 2 niveaux, publier/dépublier, archiver)

**Files:** `apps/documentation/services.py`, `apps/documentation/tests/test_services.py`

**Interfaces (toutes gardées chef de projet) :**
- `create_page(*, actor, project, title, parent_id=None, content="") -> DocPage` — slug auto unique par espace (`-2`, `-3`…). Refuse si `parent_id` désigne une page qui a déjà un parent (garde 2 niveaux) → `DocsValidationError`.
- `update_page(*, actor, project, page_id, title=None, content=None, parent_id=_UNSET, order=None) -> DocPage` — `_UNSET` = inchangé, `None` = racine. Refuse cycle + refuse un parent de 2ᵉ niveau + refuse de re-parenter une page qui a elle-même des enfants.
- `publish_page(...)` / `unpublish_page(...)` / `archive_page(...) -> None` (enfants directs remontés au parent de la page archivée).

- [ ] **Step 1: Tests qui échouent** — ajouter à `test_services.py` :

```python
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
```

- [ ] **Step 2: Lancer — échoue.**

- [ ] **Step 3: Implémenter** (ajouter à `services.py`)

```python
from django.utils.text import slugify

_UNSET = object()


def _unique_slug(space, title):
    base = slugify(title)[:190] or "page"
    slug, n = base, 2
    taken = set(
        DocPage.all_objects.filter(space=space).exclude(status="archive").values_list("slug", flat=True)
    )
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    return slug


def _get_page(space, page_id):
    try:
        return DocPage.all_objects.get(space=space, id=page_id)
    except DocPage.DoesNotExist:
        raise DocsValidationError("Page introuvable.")


def create_page(*, actor, project, title, parent_id=None, content=""):
    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    if not title or not title.strip():
        raise DocsValidationError("Le titre est obligatoire.")
    parent = None
    if parent_id:
        parent = _get_page(space, parent_id)
        if parent.parent_id is not None:
            raise DocsValidationError("La documentation est limitée à 2 niveaux de pages.")
    max_order = (
        DocPage.all_objects.filter(space=space, parent=parent)
        .order_by("-order").values_list("order", flat=True).first()
    )
    return DocPage.objects.create(
        space=space, parent=parent, title=title.strip(),
        slug=_unique_slug(space, title), content=content or "", order=(max_order or 0) + 1,
    )


def update_page(*, actor, project, page_id, title=None, content=None, parent_id=_UNSET, order=None):
    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    page = _get_page(space, page_id)
    if title is not None:
        if not title.strip():
            raise DocsValidationError("Le titre est obligatoire.")
        page.title = title.strip()
    if content is not None:
        page.content = content
    if order is not None:
        page.order = order
    if parent_id is not _UNSET:
        if parent_id is None:
            page.parent = None
        else:
            new_parent = _get_page(space, parent_id)
            if str(new_parent.id) == str(page.id):
                raise DocsValidationError("Une page ne peut pas être son propre parent.")
            if new_parent.parent_id is not None:
                raise DocsValidationError("La documentation est limitée à 2 niveaux de pages.")
            if DocPage.all_objects.filter(parent=page).exclude(status="archive").exists():
                raise DocsValidationError("Cette page a des sous-pages : elle ne peut pas devenir elle-même une sous-page.")
            page.parent = new_parent
    page.save()
    return page


def _set_page_status(actor, project, page_id, status):
    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    page = _get_page(space, page_id)
    page.status = status
    page.save(update_fields=["status", "updated_at"])
    return page


def publish_page(*, actor, project, page_id):
    return _set_page_status(actor, project, page_id, "publie")


def unpublish_page(*, actor, project, page_id):
    return _set_page_status(actor, project, page_id, "brouillon")


def archive_page(*, actor, project, page_id):
    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    page = _get_page(space, page_id)
    DocPage.all_objects.filter(parent=page).update(parent=page.parent)
    page.status = "archive"
    page.save(update_fields=["status", "updated_at"])
```

- [ ] **Step 4: Lancer — passent.** `python manage.py test apps.documentation.tests.test_services -v 2`

- [ ] **Step 5: Suite complète + commit**

```bash
git add apps/documentation/services.py apps/documentation/tests/test_services.py
git commit -m "feat(documentation): page CRUD services (2-level tree, publish, archive)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: Services — fiches (fonctionnalités + résolutions), CRUD, publier, archiver, amorçage cahier des charges

**Files:** `apps/documentation/services.py`, `apps/documentation/tests/test_services.py`

**Interfaces (gardées chef de projet) :**
- `create_entry(*, actor, project, kind, title, description="", source="manuelle", source_task=None, source_incident=None) -> DocEntry`
- `update_entry(*, actor, project, entry_id, title=None, description=None, order=None) -> DocEntry`
- `publish_entry` / `unpublish_entry` / `archive_entry(*, actor, project, entry_id) -> DocEntry`
- `list_entries(*, actor, project, kind) -> QuerySet[DocEntry]` (non archivées, garde membre)
- `seed_features_from_spec(*, actor, project) -> list[DocEntry]` — `kind="fonctionnalite"`, `source="cahier_des_charges"`, à partir de `SpecSection(section_key="exigences_fonctionnelles")`. Découpe `content` en blocs (ligne vide = séparateur ; une puce `- `/`* `/`1. ` démarre un bloc). `title` = 1re ligne (puce retirée, max 200) ; `description` = reste. Ignore un `title` déjà présent (parmi les fiches `kind=fonctionnalite`, `source=cahier_des_charges`, non archivées, comparaison `lower()`). Section absente/vide → `DocsValidationError`.

- [ ] **Step 1: Tests qui échouent** — ajouter à `test_services.py` :

```python
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
```

- [ ] **Step 2: Lancer — échoue.**

- [ ] **Step 3: Implémenter** (ajouter à `services.py`)

```python
import re

from apps.projects.models import SpecSection

_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")


def _get_entry(space, entry_id):
    try:
        return DocEntry.all_objects.get(space=space, id=entry_id)
    except DocEntry.DoesNotExist:
        raise DocsValidationError("Fiche introuvable.")


def create_entry(*, actor, project, kind, title, description="", source="manuelle",
                 source_task=None, source_incident=None):
    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    if kind not in dict(DocEntry.KIND_CHOICES):
        raise DocsValidationError("Type de fiche invalide.")
    if not title or not title.strip():
        raise DocsValidationError("Le titre est obligatoire.")
    max_order = (
        DocEntry.all_objects.filter(space=space, kind=kind).order_by("-order")
        .values_list("order", flat=True).first()
    )
    return DocEntry.objects.create(
        space=space, kind=kind, title=title.strip()[:200], description=description or "",
        source=source, source_task=source_task, source_incident=source_incident,
        order=(max_order or 0) + 1,
    )


def update_entry(*, actor, project, entry_id, title=None, description=None, order=None):
    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    e = _get_entry(space, entry_id)
    if title is not None:
        if not title.strip():
            raise DocsValidationError("Le titre est obligatoire.")
        e.title = title.strip()[:200]
    if description is not None:
        e.description = description
    if order is not None:
        e.order = order
    e.save()
    return e


def _set_entry_status(actor, project, entry_id, status):
    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    e = _get_entry(space, entry_id)
    e.status = status
    e.save(update_fields=["status", "updated_at"])
    return e


def publish_entry(*, actor, project, entry_id):
    return _set_entry_status(actor, project, entry_id, "publie")


def unpublish_entry(*, actor, project, entry_id):
    return _set_entry_status(actor, project, entry_id, "brouillon")


def archive_entry(*, actor, project, entry_id):
    return _set_entry_status(actor, project, entry_id, "archive")


def list_entries(*, actor, project, kind):
    _require_member(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    return DocEntry.all_objects.filter(space=space, kind=kind).exclude(status="archive")


def _split_spec_blocks(content):
    blocks, current = [], []
    for line in content.splitlines():
        if not line.strip():
            if current:
                blocks.append("\n".join(current)); current = []
            continue
        if _BULLET_RE.match(line) and current:
            blocks.append("\n".join(current)); current = []
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def seed_features_from_spec(*, actor, project):
    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    section = SpecSection.objects.filter(project=project, section_key="exigences_fonctionnelles").first()
    if not section or not section.content.strip():
        raise DocsValidationError("La section « Exigences fonctionnelles » du cahier des charges est vide.")
    existing = {
        t.strip().lower()
        for t in DocEntry.all_objects.filter(space=space, kind="fonctionnalite", source="cahier_des_charges")
        .exclude(status="archive").values_list("title", flat=True)
    }
    created = []
    for block in _split_spec_blocks(section.content):
        lines = block.splitlines()
        title = _BULLET_RE.sub("", lines[0]).strip()[:200]
        if not title or title.lower() in existing:
            continue
        created.append(create_entry(
            actor=actor, project=project, kind="fonctionnalite", title=title,
            description="\n".join(lines[1:]).strip(), source="cahier_des_charges",
        ))
        existing.add(title.lower())
    return created
```

- [ ] **Step 4: Lancer — passent.**

- [ ] **Step 5: Suite complète + commit**

```bash
git add apps/documentation/services.py apps/documentation/tests/test_services.py
git commit -m "feat(documentation): doc entry services + seed features from cahier des charges

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: Signaux `task_completed` + `incident_resolved` → file « À documenter », services from-pending / ignore

**Files:**
- Modify: `apps/tasks/signals.py`, `apps/tasks/services.py`, `apps/incidents/signals.py`, `apps/incidents/services.py`, `apps/documentation/signals.py`, `apps/documentation/services.py`
- Test: `apps/documentation/tests/test_signals.py`, `test_services.py` (classe `PendingDocEntryServiceTests`)

**Interfaces:**
- `apps.tasks.signals.task_completed` — `Signal()`, kwargs `task`, `actor`. Émis en fin de `complete_task`.
- `apps.incidents.signals.incident_resolved` — `Signal()`, kwargs `incident`, `actor`. Émis en fin de `resolve_incident`.
- Récepteurs `apps/documentation/signals.py` :
  - `task_completed` : si `task.task_type in {"ajout","evolution"}` et `DocSpace` existe pour `task.project` → `PendingDocEntry.objects.get_or_create(task=task, defaults={"space": space, "kind": "fonctionnalite"})`.
  - `incident_resolved` : si `incident.project_id` est renseigné et `DocSpace` existe pour ce projet → `PendingDocEntry.objects.get_or_create(incident=incident, defaults={"space": space, "kind": "resolution"})`. (Incident rattaché à une `Team` sans projet : ignoré — pas de `DocSpace`.)
- `list_pending_entries(*, actor, project, kind=None) -> QuerySet[PendingDocEntry]` (statut `en_attente`, garde membre)
- `create_entry_from_pending(*, actor, project, pending_id) -> DocEntry` (garde chef de projet) : crée une `DocEntry` du bon `kind`, `title`/`description` copiés de la tâche ou de l'incident (`incident.title` / `incident.description`), `source="tache"` ou `"incident"`, lie `source_task`/`source_incident`, passe le pending à `traitee` + `entry=...`.
- `ignore_pending(*, actor, project, pending_id) -> None` (garde chef de projet).

- [ ] **Step 1: Tests qui échouent** — `apps/documentation/tests/test_signals.py`

```python
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.documentation.models import DocSpace, PendingDocEntry
from apps.incidents import services as incident_services
from apps.incidents.models import Incident
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks import services as task_services
from apps.tasks.models import Task


class DocQueueSignalTests(TestCase):
    def setUp(self):
        self.mgr = User.objects.create(username="mgr")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.mgr, role="chef_de_projet")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)

    def _complete_task(self, task_type):
        t = Task.objects.create(project=self.project, version=self.version, title=f"T {task_type}",
                                task_type=task_type, status="en_cours", assignee=self.mgr)
        task_services.complete_task(actor=self.mgr, task=t, time_spent=Decimal("1"))
        return t

    def test_no_space_no_pending(self):
        self._complete_task("ajout")
        self.assertEqual(PendingDocEntry.objects.count(), 0)

    def test_ajout_creates_feature_pending(self):
        DocSpace.objects.create(project=self.project)
        t = self._complete_task("ajout")
        self.assertEqual(PendingDocEntry.objects.filter(task=t, kind="fonctionnalite", status="en_attente").count(), 1)

    def test_correction_creates_nothing(self):
        DocSpace.objects.create(project=self.project)
        self._complete_task("correction")
        self.assertEqual(PendingDocEntry.objects.count(), 0)

    def test_resolved_incident_creates_resolution_pending(self):
        DocSpace.objects.create(project=self.project)
        inc = Incident.objects.create(project=self.project, title="Panne export", status="en_cours")
        incident_services.resolve_incident(actor=self.mgr, incident=inc)
        self.assertEqual(PendingDocEntry.objects.filter(incident=inc, kind="resolution", status="en_attente").count(), 1)
```
*(Adapter la création d'`Incident` / le passage en `en_cours` aux contraintes réelles du modèle — voir `apps/incidents/tests/`.)*

Ajouter à `test_services.py` :

```python
class PendingDocEntryServiceTests(TestCase):
    def setUp(self):
        from apps.projects.models import ProjectVersion
        from apps.tasks.models import Task
        self.mgr = User.objects.create(username="mgr")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.mgr, role="chef_de_projet")
        v = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.space = services.get_or_create_space(actor=self.mgr, project=self.project)
        self.task = Task.objects.create(project=self.project, version=v, title="Export Excel",
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

    def test_ignore_pending(self):
        services.ignore_pending(actor=self.mgr, project=self.project, pending_id=self.pending.id)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "ignoree")
```

- [ ] **Step 2: Lancer — échoue.**

- [ ] **Step 3: Signaux tasks** — `apps/tasks/signals.py` :
```python
# kwargs: task (Task), actor (User) — émis quand une tâche passe en statut
# terminal "archivee" via complete_task. Consommé par apps.documentation.
task_completed = django.dispatch.Signal()
```
`apps/tasks/services.py` — dans `complete_task`, juste avant `return task` :
```python
    task_completed.send(sender=Task, task=task, actor=actor)
```
(vérifier l'import en tête, à côté de `task_assigned`).

- [ ] **Step 4: Signaux incidents** — `apps/incidents/signals.py` :
```python
# kwargs: incident (Incident), actor (User) — émis quand un incident passe
# en statut "resolu" via resolve_incident. Consommé par apps.documentation.
incident_resolved = django.dispatch.Signal()
```
`apps/incidents/services.py` — dans `resolve_incident`, juste avant `return incident` :
```python
    incident_resolved.send(sender=Incident, incident=incident, actor=actor)
```
(ajouter l'import `from .signals import incident_commented, incident_resolved`).

- [ ] **Step 5: Récepteurs** — `apps/documentation/signals.py` :
```python
from django.dispatch import receiver

from apps.incidents.signals import incident_resolved
from apps.tasks.signals import task_completed

from .models import DocSpace, PendingDocEntry

_DOCUMENTABLE_TASK_TYPES = {"ajout", "evolution"}


@receiver(task_completed)
def _on_task_completed(sender, task, actor, **kwargs):
    if task.task_type not in _DOCUMENTABLE_TASK_TYPES:
        return
    space = DocSpace.objects.filter(project=task.project).first()
    if space is None:
        return
    PendingDocEntry.objects.get_or_create(
        task=task, defaults={"space": space, "kind": "fonctionnalite"}
    )


@receiver(incident_resolved)
def _on_incident_resolved(sender, incident, actor, **kwargs):
    if not incident.project_id:
        return
    space = DocSpace.objects.filter(project_id=incident.project_id).first()
    if space is None:
        return
    PendingDocEntry.objects.get_or_create(
        incident=incident, defaults={"space": space, "kind": "resolution"}
    )
```

- [ ] **Step 6: Services from-pending / ignore / list** — ajouter à `apps/documentation/services.py` :
```python
def list_pending_entries(*, actor, project, kind=None):
    _require_member(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    qs = PendingDocEntry.objects.filter(space=space, status="en_attente").select_related("task", "incident")
    return qs.filter(kind=kind) if kind else qs


def _get_pending(space, pending_id):
    try:
        return PendingDocEntry.all_objects.get(space=space, id=pending_id)
    except PendingDocEntry.DoesNotExist:
        raise DocsValidationError("Entrée introuvable.")


def create_entry_from_pending(*, actor, project, pending_id):
    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    pending = _get_pending(space, pending_id)
    if pending.status != "en_attente":
        raise DocsValidationError("Cette entrée a déjà été traitée.")
    src = pending.task or pending.incident
    entry = create_entry(
        actor=actor, project=project, kind=pending.kind,
        title=src.title, description=getattr(src, "description", "") or "",
        source="tache" if pending.task_id else "incident",
        source_task=pending.task, source_incident=pending.incident,
    )
    pending.status = "traitee"
    pending.entry = entry
    pending.save(update_fields=["status", "entry", "updated_at"])
    return entry


def ignore_pending(*, actor, project, pending_id):
    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    pending = _get_pending(space, pending_id)
    pending.status = "ignoree"
    pending.save(update_fields=["status", "updated_at"])
```

- [ ] **Step 7: Lancer — passent.** `python manage.py test apps.documentation -v 2`

- [ ] **Step 8: Suite complète + commit**

```bash
git add apps/documentation apps/tasks/signals.py apps/tasks/services.py apps/incidents/signals.py apps/incidents/services.py
git commit -m "feat(documentation): task_completed + incident_resolved feed the 'to document' queue

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 6: API authentifiée — serializers, `DocSpaceViewSet`, routage

**Files:** `apps/documentation/serializers.py`, `views.py`, `urls.py` (créer) ; `config/urls.py` (modifier) ; `apps/documentation/tests/test_api.py`

**Interfaces — endpoints sous `/api/v1/docs/`, `lookup_url_kwarg = "project_id"` (UUID du projet) :**
- `GET /api/v1/docs/{project_id}/` → `{ space:{id,is_public,public_token,public_url}, pages:[<arbre>], features:[...], resolutions:[...], pending_features:[...], pending_resolutions:[...] }`
- `POST /api/v1/docs/{project_id}/pages/` `{title, parent_id?, content?}` · `PATCH .../pages/{page_id}/` · `POST .../pages/{page_id}/publish/` · `.../unpublish/` · `DELETE .../pages/{page_id}/` (archive)
- `POST /api/v1/docs/{project_id}/entries/` `{kind, title, description?}` · `PATCH .../entries/{entry_id}/` · `.../publish/` · `.../unpublish/` · `DELETE` (archive)
- `POST /api/v1/docs/{project_id}/entries/seed-from-spec/` → `{created:[...]}`
- `POST /api/v1/docs/{project_id}/pending/{pending_id}/create-entry/` → entry
- `POST /api/v1/docs/{project_id}/pending/{pending_id}/ignore/`
- `POST /api/v1/docs/{project_id}/public-link/` (enable) · `POST .../public-link/rotate/` · `DELETE .../public-link/`
- Erreurs : `DocsPermissionError` → 403, `DocsValidationError` → 400 (méthode `handle_exception` sur le viewset, cf. `apps/projects/views.py`).

**Implémentation :** `DocSpaceViewSet(viewsets.ViewSet)` (ressources imbriquées custom, pas `ModelViewSet`). `_project(request, project_id)` = `get_object_or_404(accessible_projects(request.user), id=project_id)`. `retrieve()` = l'agrégat `GET`. Serializers de sortie `ModelSerializer` (`DocPageSerializer` + `DocPageTreeSerializer` récursif avec `children`, `DocEntrySerializer`, `PendingDocEntrySerializer` avec `task`/`incident` résumés), serializers d'entrée `Serializer` explicites. `public_url` = `request.build_absolute_uri(f"/docs/{token}")` si `is_public and public_token` sinon `None`.

- [ ] **Step 1: Tests qui échouent** — `apps/documentation/tests/test_api.py` (entête `@override_settings` calquée sur `apps/incidents/tests/test_api.py`)

```python
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership


@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.DebugUserIdAuthentication"],
    },
)
class DocsApiAuthedTests(APITestCase):
    def setUp(self):
        self.mgr = User.objects.create(username="mgr")
        self.member = User.objects.create(username="mbr")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.mgr, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def _as(self, u):
        self.client.credentials(HTTP_X_DEBUG_USER_ID=str(u.id))

    def test_get_bootstraps_empty(self):
        self._as(self.member)
        r = self.client.get(f"/api/v1/docs/{self.project.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["pages"], [])
        self.assertIsNone(r.data["space"]["public_url"])

    def test_member_cannot_create_page(self):
        self._as(self.member)
        r = self.client.post(f"/api/v1/docs/{self.project.id}/pages/", {"title": "X"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_manager_page_lifecycle(self):
        self._as(self.mgr)
        r = self.client.post(f"/api/v1/docs/{self.project.id}/pages/", {"title": "Prise en main"}, format="json")
        self.assertEqual(r.status_code, 201)
        pid = r.data["id"]
        r = self.client.post(f"/api/v1/docs/{self.project.id}/pages/{pid}/publish/")
        self.assertEqual(r.data["status"], "publie")

    def test_enable_and_revoke_public_link(self):
        self._as(self.mgr)
        r = self.client.post(f"/api/v1/docs/{self.project.id}/public-link/")
        self.assertTrue(r.data["space"]["public_url"])
        r = self.client.delete(f"/api/v1/docs/{self.project.id}/public-link/")
        self.assertIsNone(r.data["space"]["public_url"])

    def test_create_resolution_entry(self):
        self._as(self.mgr)
        r = self.client.post(f"/api/v1/docs/{self.project.id}/entries/",
                             {"kind": "resolution", "title": "Panne export résolue"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["kind"], "resolution")
```

- [ ] **Step 2: Lancer — échoue (404).**
- [ ] **Step 3: Serializers** (`serializers.py`).
- [ ] **Step 4: `views.py`** (`DocSpaceViewSet` + `handle_exception`).
- [ ] **Step 5: Routage** — `apps/documentation/urls.py` :
```python
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import DocSpaceViewSet, PublicDocsView

router = SimpleRouter(trailing_slash=True)
router.register("", DocSpaceViewSet, basename="doc-space")

urlpatterns = [
    path("public/<str:token>/", PublicDocsView.as_view(), name="doc-public"),
    *router.urls,
]
```
`config/urls.py` — dans `api_v1_patterns` : `path("docs/", include("apps.documentation.urls")),`.
*(Enchaîner Task 6 et 7 sans commit intermédiaire : `PublicDocsView` est référencé ici.)*

- [ ] **Step 6: Lancer les tests — passent.**
- [ ] **Step 7: Schéma OpenAPI** : `python manage.py spectacular --file /tmp/schema.yml` — pas de NOUVEAU warning `apps.documentation` (annoter `@extend_schema` si besoin).
- [ ] **Step 8: Commit groupé avec Task 7.**

---

## Task 7: API publique — `PublicDocsView` (`AllowAny`), agrégat lecture seule

**Files:** `apps/documentation/views.py`, `serializers.py`, `services.py` ; `tests/test_api.py` (classe `DocsApiPublicTests`)

**Interfaces:**
- `get_public_docs(token) -> dict | None` — `None` si token vide/inconnu ou `is_public=False`. Sinon `{ project_name, pages:[<arbre pages status=publie, parent non publié => remonté racine>], features:[{id,title,description}], resolutions:[{id,title,description}] }` (entrées `status=publie` triées `order`).
- `PublicDocsView(APIView)` : `authentication_classes = []`, `permission_classes = [AllowAny]`. `GET` → 200 ou `Http404`.

- [ ] **Step 1: Tests qui échouent** — ajouter à `test_api.py` :

```python
@override_settings(DEBUG=True)
class DocsApiPublicTests(APITestCase):
    def setUp(self):
        from apps.documentation import services
        self.mgr = User.objects.create(username="mgr")
        self.project = Project.objects.create(name="Mon Produit", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.mgr, role="chef_de_projet")
        self.space = services.enable_public_link(actor=self.mgr, project=self.project)
        p = services.create_page(actor=self.mgr, project=self.project, title="Publiee", content="# Bonjour")
        services.publish_page(actor=self.mgr, project=self.project, page_id=p.id)
        services.create_page(actor=self.mgr, project=self.project, title="Brouillon")

    def test_only_published(self):
        r = self.client.get(f"/api/v1/docs/public/{self.space.public_token}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["project_name"], "Mon Produit")
        self.assertEqual([p["title"] for p in r.data["pages"]], ["Publiee"])

    def test_unknown_token_404(self):
        self.assertEqual(self.client.get("/api/v1/docs/public/nope/").status_code, 404)

    def test_revoked_token_404(self):
        from apps.documentation import services
        tok = self.space.public_token
        services.revoke_public_link(actor=self.mgr, project=self.project)
        self.assertEqual(self.client.get(f"/api/v1/docs/public/{tok}/").status_code, 404)
```

- [ ] **Step 2: Lancer — échoue.**
- [ ] **Step 3: `get_public_docs`** dans `services.py` :
```python
def _public_pages(space):
    pages = list(DocPage.all_objects.filter(space=space, status="publie").order_by("order", "created_at"))
    ids = {p.id for p in pages}
    def node(pg):
        return {"id": str(pg.id), "title": pg.title, "slug": pg.slug, "content": pg.content,
                "children": [node(c) for c in pages if c.parent_id == pg.id]}
    return [node(p) for p in pages if p.parent_id is None or p.parent_id not in ids]


def _public_entries(space, kind):
    return [
        {"id": str(e.id), "title": e.title, "description": e.description}
        for e in DocEntry.all_objects.filter(space=space, kind=kind, status="publie").order_by("order", "created_at")
    ]


def get_public_docs(token):
    if not token:
        return None
    space = DocSpace.objects.filter(public_token=token, is_public=True).select_related("project").first()
    if space is None:
        return None
    return {
        "project_name": space.project.name,
        "pages": _public_pages(space),
        "features": _public_entries(space, "fonctionnalite"),
        "resolutions": _public_entries(space, "resolution"),
    }
```
- [ ] **Step 4: `PublicDocsView`** dans `views.py` :
```python
from django.http import Http404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import get_public_docs


class PublicDocsView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        data = get_public_docs(token)
        if data is None:
            raise Http404
        return Response(data)
```
- [ ] **Step 5: Lancer — passent.** `python manage.py test apps.documentation -v 2`
- [ ] **Step 6: Suite complète** : `python manage.py test`.
- [ ] **Step 7: Commit (Tasks 6+7)**

```bash
git add apps/documentation config/urls.py
git commit -m "feat(documentation): REST API (authed viewset + public read-only endpoint)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 8: Frontend — types + fonctions API client

**Files:** `frontend/src/types/watodo.ts`, `frontend/src/api/client.ts`

**Types :**
```ts
export type DocStatus = "brouillon" | "publie" | "archive";
export type DocEntryKind = "fonctionnalite" | "resolution";
export interface DocPage { id: string; parent_id: string | null; title: string; slug: string; content: string; order: number; status: DocStatus; status_display: string; children: DocPage[]; }
export interface DocEntry { id: string; kind: DocEntryKind; title: string; description: string; order: number; source: string; source_task_id: string | null; source_incident_id: string | null; status: DocStatus; status_display: string; }
export interface PendingDocEntry { id: string; kind: DocEntryKind; source_label: string; source_title: string; created_at: string; }
export interface DocSpace { id: string; is_public: boolean; public_token: string | null; public_url: string | null; }
export interface DocumentationBundle { space: DocSpace; pages: DocPage[]; features: DocEntry[]; resolutions: DocEntry[]; pending_features: PendingDocEntry[]; pending_resolutions: PendingDocEntry[]; }
export interface PublicDocsNode { id: string; title: string; slug: string; content: string; children: PublicDocsNode[]; }
export interface PublicDocs { project_name: string; pages: PublicDocsNode[]; features: { id: string; title: string; description: string }[]; resolutions: { id: string; title: string; description: string }[]; }
```
Ajouter `can_edit_documentation: boolean;` aux `permissions` de `Project`.

**Client :** `getDocumentation(projectId)`, `createDocPage`, `updateDocPage`, `publishDocPage`, `unpublishDocPage`, `archiveDocPage`, `createDocEntry`, `updateDocEntry`, `publishDocEntry`, `unpublishDocEntry`, `archiveDocEntry`, `seedFeaturesFromSpec`, `createEntryFromPending`, `ignorePending`, `enablePublicLink`, `rotatePublicLink`, `revokePublicLink`, `getPublicDocs(token)` (SANS en-tête d'auth).

- [ ] **Step 1-2:** types + fonctions (style existant).
- [ ] **Step 3:** `npm --prefix frontend run lint`.
- [ ] **Step 4:** `npm --prefix frontend run build`.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/watodo.ts frontend/src/api/client.ts
git commit -m "feat(documentation): frontend types + API client

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 9: Frontend — onglet « Documentation » dans le hub projet

**Files:** `frontend/src/features/projects/DocumentationTab.tsx` / `.css` (créer) ; `ProjectDetailView.tsx` (modifier)

**Contenu :**
- `ProjectDetailView.tsx` : `type Tab` += `"documentation"` ; `TABS` += `{ id: "documentation", label: "Documentation" }` **filtré** si `!project.permissions.can_edit_documentation` ; `{tab === "documentation" && <DocumentationTab project={project} />}`.
- `DocumentationTab` : `getDocumentation(project.id)` au montage. Sous-navigation : **Pages · Fonctionnalités · Résolution d'incidents · À documenter (badge = pending_features + pending_resolutions) · Lien public**.
  - **Pages** : arbre 2 niveaux, sélection → éditeur `textarea` Markdown + aperçu `MarkdownView` (pattern `SpecTab.tsx:80-104`). Actions : Nouvelle page / Nouvelle sous-page (désactivé si la page courante est déjà une sous-page), Renommer, Publier/Dépublier, Archiver (confirm), monter/descendre.
  - **Fonctionnalités** / **Résolution d'incidents** : même composant liste paramétré par `kind`. Cartes `DocEntry` (titre + `MarkdownView(description)` + pastille statut). Éditer inline, Publier/Dépublier, Archiver, Nouvelle fiche. Sur l'onglet Fonctionnalités seulement : bouton **« Amorcer depuis le cahier des charges »** (`seedFeaturesFromSpec` → toast « N fiche(s) créée(s) » / message d'erreur si section vide).
  - **À documenter** : deux sous-listes (Fonctionnalités / Résolutions). Par entrée : `source_label` + `source_title` + date, bouton **« Créer la fiche »** (`createEntryFromPending` → bascule sur l'onglet correspondant, fiche en édition) + **« Ignorer »** (confirm).
  - **Lien public** : si `space.public_url` → URL en lecture seule + Copier + « Régénérer » (confirm : « l'ancien lien cessera de fonctionner ») + « Révoquer » (confirm). Sinon → « Activer le lien public » + phrase : « Toute personne disposant du lien pourra lire les pages publiées, sans compte Awtodo. »
- Styles charte (brique, `--font-display`/`--font-mono`, formes existantes ; pas de gradient/carte imbriquée gratuite).

- [ ] **Step 1:** créer `DocumentationTab.tsx` + `.css`.
- [ ] **Step 2:** câbler `ProjectDetailView.tsx`.
- [ ] **Step 3:** `npm --prefix frontend run lint && npm --prefix frontend run build`.
- [ ] **Step 4: Vérif manuelle** — `python manage.py runserver` + `npm --prefix frontend run dev` ; chef de projet : créer/publier une page, activer le lien public, amorcer depuis le cahier des charges, résoudre un incident et le voir apparaître dans « À documenter ». Un membre non-chef ne voit pas l'onglet.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/projects/DocumentationTab.tsx frontend/src/features/projects/DocumentationTab.css frontend/src/features/projects/ProjectDetailView.tsx
git commit -m "feat(documentation): Documentation tab in project hub

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 10: Frontend — page publique `/docs/<token>`

**Files:** `frontend/src/features/docs/PublicDocsPage.tsx` / `.css` (créer) ; `App.tsx` (modifier)

**Contenu :**
- `App.tsx` : `const PUBLIC_DOCS_PATH_PATTERN = /^\/docs\/([^/]+)\/?$/;` près de `INVITATION_PATH_PATTERN`. **Avant** `if (isRestoring)` et `if (!currentUser)` :
  ```tsx
  const publicDocsToken = window.location.pathname.match(PUBLIC_DOCS_PATH_PATTERN)?.[1];
  if (publicDocsToken) return <PublicDocsPage token={publicDocsToken} />;
  ```
- `PublicDocsPage` : `getPublicDocs(token)`. États chargement / 404 (« Cette documentation n'existe pas ou n'est plus partagée. ») / OK. Entête `project_name` + mention « Documentation propulsée par Awtodo ». Sommaire gauche : pages (2 niveaux) + « Fonctionnalités » / « Résolution d'incidents » si non vides. Contenu : `MarkdownView` de la page ou liste des fiches. Suit le thème clair/sombre (comme `HomePage`). Pas d'`AppShell`/`Topbar`/`CommandPalette`.
- `PublicDocsPage.css` : `@media print` — masquer la nav, contenu pleine largeur, typo sobre (permet Ctrl+P → PDF).

- [ ] **Step 1:** créer `PublicDocsPage.tsx` + `.css`.
- [ ] **Step 2:** câbler `App.tsx` (avant les gardes d'auth).
- [ ] **Step 3:** `npm --prefix frontend run lint && npm --prefix frontend run build`.
- [ ] **Step 4: Vérif manuelle** — ouvrir l'URL publique en navigation privée : pages publiées visibles, brouillons non ; Ctrl+P lisible ; token bidon → 404.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/docs/PublicDocsPage.tsx frontend/src/features/docs/PublicDocsPage.css frontend/src/App.tsx
git commit -m "feat(documentation): public documentation page at /docs/<token>

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 11: Frontend — export `.docx`

**Files:** `frontend/src/features/docs/exportDocx.ts` (créer) ; `DocumentationTab.tsx` (modifier)

**Interface :** `exportDocsToDocx(projectName, pages: PublicDocsNode[]-like, features, resolutions): Promise<void>` — mêmes primitives que `SpecTab.exportSpecToDocx` (`HEADING_1` page racine, `HEADING_2` sous-page, paragraphes par ligne ; sections « Fonctionnalités » puis « Résolution d'incidents » en fin, `HEADING_2` par fiche). Fichier `${sanitizeFilename(projectName)} — Documentation.docx`.

- [ ] **Step 1:** créer `exportDocx.ts` (calquer `SpecTab.tsx:11-40`).
- [ ] **Step 2:** bouton « Exporter en .docx » dans la barre d'outils de `DocumentationTab` (exporte publié + brouillon — outil interne du chef de projet).
- [ ] **Step 3:** `npm --prefix frontend run lint && npm --prefix frontend run build`.
- [ ] **Step 4: Vérif manuelle** — ouvrir le `.docx` dans Word, vérifier structure + éditabilité.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/docs/exportDocx.ts frontend/src/features/projects/DocumentationTab.tsx
git commit -m "feat(documentation): .docx export of project documentation

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 12: Documentation interne

**Files:** `CLAUDE.md`, `docs/modeles-et-api.md`, `docs/charte-graphique.md`

- [ ] **Step 1: `CLAUDE.md`**
  - Section « Stack technique » > Auth : nouvelle puce —
    > **Exception à « la connexion est la porte d'entrée obligatoire »** (session 2026-09-03) : les pages de documentation de projet *publiées* sont accessibles sans compte via `/docs/<token>` (token non devinable, révocable, porté par `DocSpace.public_token`). Seul le contenu publié est exposé — aucune donnée de gestion (tâches, membres, budget, incidents bruts). Seul contournement autorisé du garde-fou d'`App.tsx`.
  - « Hors périmètre v1 » : note « Documentation utilisateur par projet : implémentée le 2026-09-03 ».
  - Roadmap macro, nouvelle entrée en tête : app `apps/documentation/`, onglet hub réservé au chef de projet, page publique token clair/sombre, onglets Fonctionnalités (amorçable cahier des charges + tâches `ajout`/`evolution` livrées via `task_completed`) et Résolution d'incidents (incidents `resolu` d'un projet via `incident_resolved`), arbre de pages 2 niveaux, export `.docx` frontend + PDF par impression.
- [ ] **Step 2: `docs/modeles-et-api.md`** — section « Documentation de projet » : 4 modèles, cycle de vie des statuts, endpoints `/api/v1/docs/...` (authentifiés + public), mécanisme file « À documenter » (deux signaux, conditions).
- [ ] **Step 3: `docs/charte-graphique.md`** — section « Onglet Documentation + page publique » (traitement visuel, `@media print`).
- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/modeles-et-api.md docs/charte-graphique.md
git commit -m "docs: project documentation module (models, API, charte, CLAUDE.md exception)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Vérification finale** : `python manage.py test` (tout vert) + `npm --prefix frontend run lint && npm --prefix frontend run build`.

---

## Self-Review

**1. Spec coverage :**
- Documentation hébergée sur Awtodo → Tasks 1, 6, 9. ✅
- Lien public envoyable à n'importe qui, révocable → Tasks 2, 7, 10. ✅
- Onglet Fonctionnalités → `DocEntry(kind=fonctionnalite)`, Tasks 4, 9. ✅
- Onglet Résolution d'incidents → `DocEntry(kind=resolution)`, alimenté par incidents résolus, Tasks 4, 5, 9. ✅
- « MàJ temps réel » nouvelles fonctionnalités → `task_completed` + file, Task 5. ✅
- Amorçage cahier des charges → `seed_features_from_spec`, Task 4. ✅
- Rédaction réservée au chef de projet → `_require_manager` partout, `can_edit_documentation`, Tasks 2, 9. ✅
- Export `.docx` + PDF → Task 11 + `@media print` Task 10. ✅
- Aucune suppression physique → `StatusLifecycleModel` + `archive`, Task 1. ✅
- Arbre 2 niveaux → garde `create_page`/`update_page`, Task 3. ✅
- Page publique clair/sombre → Task 10. ✅
- App `apps.documentation` → toutes tasks. ✅
- Exception règle auth dans CLAUDE.md → Task 12. ✅

**2. Placeholder scan :** steps frontend (9-11) décrivent le contenu sans coller chaque ligne JSX — acceptable : pas de framework de test frontend dans ce repo, et le pattern est celui de `SpecTab.tsx`/`NotesTab.tsx` (référencés avec numéros de ligne). Aucun « TODO » dans les steps backend.

**3. Type consistency :** `DocPage.status`/`DocEntry.status` partagent `brouillon`/`publie`/`archive` → type TS `DocStatus`. `DocEntryKind` = `fonctionnalite`/`resolution` cohérent modèle ↔ API ↔ TS. `create_entry_from_pending -> DocEntry` (Task 5 ↔ Task 6). `lookup_url_kwarg = "project_id"` cohérent `urls.py` ↔ `views.py`. Agrégat `GET` : clés `features`/`resolutions`/`pending_features`/`pending_resolutions` cohérentes entre Task 6 et le type `DocumentationBundle` (Task 8).

**4. Points à vérifier à l'exécution (non bloquants) :**
- Contraintes réelles du modèle `Incident` (champs requis à la création, transition `signale`→`en_cours`→`resolu`) — s'aligner sur `apps/incidents/tests/`.
- `PendingDocEntry.CheckConstraint` (exactly-one task/incident) : SQLite la supporte (Django 5.2). Vérifier au `migrate`.
- Un test projet existant pourrait figer l'ensemble des clés de `get_project_permissions` → ajouter `can_edit_documentation` à l'attendu.
