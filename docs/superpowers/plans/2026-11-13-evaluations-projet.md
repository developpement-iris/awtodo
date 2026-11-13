# Fiches d'évaluation de projet — plan d'implémentation

> **Pour les agents :** sous-skill requis : `superpowers:subagent-driven-development` (recommandé) ou `superpowers:executing-plans`. Les étapes utilisent des cases à cocher (`- [ ]`).

**Objectif :** permettre à un chef de projet de créer, pour un projet, des **fiches d'évaluation** en deux parties : une **satisfaction client**, remplie via un lien public, et une **évaluation chef de projet**, remplie dans Awtodo. Les réponses sont consultables, exportables en CSV, imprimables en PDF (un document par répondant, avec la partie chef de projet) et agrégées dans les statistiques.

**Architecture :** nouvelle app Django `apps/evaluations` (dépend de `common`, `accounts` et `projects` ; seule `dashboards` en dépend). Un **catalogue de questions génériques** par groupe (ou par projet sans groupe, même règle que les types de tâche) est **copié dans la fiche à sa création**. Ces copies figent les questions de la fiche : modifier le catalogue ensuite ne change rien aux fiches existantes. Chaque fiche peut ajouter ses propres questions. Une question peut dépendre d'une autre (« afficher si la réponse est l'une de… »). La même logique de validation et de visibilité tourne côté serveur (`answers.py`) et dans le navigateur (`visibility.ts`).

**Stack :** Django/DRF, drf-spectacular, React/TS. **Aucune nouvelle dépendance**, ni Python ni npm. Le PDF passe par l'impression du navigateur (« Enregistrer au format PDF »), comme la page de doc publique.

## Décisions de cadrage (validées avec l'utilisateur le 2026-11-13)

| Sujet | Décision |
|---|---|
| Accès client | **Lien public** (jeton non devinable, révocable, régénérable). **Nom du répondant obligatoire**, pas d'email. C'est la **2ᵉ exception** au garde-fou « connexion obligatoire » : à acter dans CLAUDE.md (tâche 15). |
| Questions génériques | **Catalogue par groupe**, avec deux sections : `client` et `interne`. Projet sans groupe : catalogue propre au projet, géré par son chef de projet. |
| Droit de modifier le catalogue d'un groupe | **Tout administrateur du groupe** (`can_manage_team` : créateur, rôle `administrateur`, admin d'organisation ou de plateforme). **Pas** de capacité de profil supplémentaire. |
| Nombre de fiches | **Plusieurs fiches par projet** (une par vague, par livraison…). |
| Types de réponse | Choisis **question par question** : `note_5`, `nps_10`, `oui_non`, `choix_unique`, `choix_multiple`, `texte_court`, `texte_long`. |
| Partie chef de projet | **Une seule réponse commune par fiche**, que n'importe quel chef de projet du projet peut remplir ou modifier. |
| Questions conditionnelles | Autorisées **dans les deux parties**. Une seule condition par question : la réponse à une question `oui_non` ou `choix_unique` de la **même partie** doit figurer dans une liste de valeurs. |
| Visibilité | Partie client et partie chef de projet : chefs de projet du projet, admins du groupe et admins d'organisation. Les deux parties figurent dans l'export CSV et dans les statistiques. |
| Statistiques | **Pas de comparaison entre groupes.** On agrège par question générique : comme le catalogue est par groupe, chaque ligne reste à l'intérieur d'un groupe. |
| Export | **CSV** (même mécanisme que l'export d'historique). |
| PDF | **Un document par répondant client**, qui reprend ses réponses puis la partie chef de projet de la fiche. |

### Choix pris sans validation explicite (à signaler à l'utilisateur)

- **PDF par impression du navigateur**, plutôt qu'une lib (jsPDF, WeasyPrint) : zéro dépendance, comme la doc publique. Si un vrai fichier téléchargé sans boîte d'impression est exigé, il faudra une nouvelle dépendance, donc une validation.
- **Les questions d'une fiche se figent à l'ouverture** du lien. Elles restent modifiables tant que la fiche est en `brouillon`.
- **Les questions génériques copiées dans une fiche ne sont ni modifiables ni retirables** depuis la fiche. C'est la condition pour que les statistiques restent comparables. On agit sur le catalogue pour les fiches suivantes.
- **Le type de réponse d'une question du catalogue est figé à la création**, faute de quoi les statistiques mélangeraient des échelles. Le libellé, l'aide, les options, le caractère obligatoire et la condition restent modifiables.
- La partie chef de projet se remplit une fois la fiche **ouverte** (questions figées), y compris après clôture, tant qu'elle n'est pas archivée. Son enregistrement est partiel : aucun champ obligatoire n'est imposé.
- Une réponse client indésirable (spam, test) est **écartée**, pas supprimée. Elle sort des résultats, de l'export, du PDF et des stats, et reste restaurable.
- Envoi public limité à **10 réponses par heure et par IP** (`ScopedRateThrottle`).

## Contraintes globales

- **Aucune suppression physique** : statuts terminaux uniquement. Tout modèle basé sur `StatusLifecycleModel` déclare `default_manager_name = "all_objects"` et `base_manager_name = "all_objects"` dans son propre `Meta`.
- PK en UUID (`UUIDModel`). API sous `/api/v1/evaluations/`.
- Toute logique métier dans `services.py` / `catalog.py` / `answers.py` / `results.py`, jamais dans les vues ou les serializers.
- `apps/evaluations` n'importe **que** `apps.common`, `apps.accounts` et `apps.projects`. `apps.dashboards` importe `apps.evaluations`, jamais l'inverse.
- Tout endpoint est décrit dans `apps/evaluations/schema.py`. Les endpoints publics déclarent `security: [{}]`.
- La page publique n'expose **que** le titre de la fiche, l'intro, le nom du projet et les questions **client**. Jamais la partie interne, les autres réponses ni des données de gestion.
- Textes UI en français, tokens de `theme/tokens.css`, composants existants (`Combobox`, `Checkbox`, `ConfirmDialog`, `PromptDialog`, `StatCard`, `DonutChart`, `BarChart`). **Aucun `<select>` natif.**
- Tests backend : `.venv/Scripts/python.exe manage.py test apps.evaluations` (unittest). Frontend : `npm --prefix frontend run lint`, `npm --prefix frontend run build`.
- Ne pas commiter sans demande de l'utilisateur. Les étapes « Commit » ci-dessous ne s'exécutent que si l'utilisateur a validé le commit pour cette session.

## Structure des fichiers

```
apps/evaluations/
├── __init__.py
├── apps.py                 # EvaluationsConfig, importe receivers dans ready()
├── models.py               # CatalogQuestion, EvaluationSheet, SheetQuestion, ClientResponse, InternalEvaluation, Answer
├── defaults.py             # DEFAULT_CATALOG (questions livrées par défaut)
├── answers.py              # normalisation des réponses + visibilité conditionnelle (pur, sans ORM)
├── definitions.py          # validation des définitions de question (libellé, options, condition)
├── catalog.py              # services du catalogue + amorçage
├── services.py             # services des fiches, réponses publiques, partie interne
├── results.py              # agrégation, CSV, lignes pour le dashboard
├── receivers.py            # post_save Team/Project -> seed_default_catalog
├── serializers.py
├── throttles.py            # EvaluationSubmitThrottle
├── views.py
├── schema.py
├── urls.py
├── admin.py
├── migrations/0001_initial.py, 0002_seed_default_catalog.py
└── tests/
    ├── __init__.py
    ├── factories.py
    ├── test_answers.py
    ├── test_catalog.py
    ├── test_sheets.py
    ├── test_public.py
    ├── test_results.py
    └── test_api.py

frontend/src/
├── types/watodo.ts                       # + types Evaluation*
├── api/client.ts                         # + fonctions evaluations
├── features/evaluations/
│   ├── visibility.ts                     # miroir de answers.visible_question_ids
│   ├── answerFormat.ts                   # affichage lisible d'une valeur
│   ├── AnswerField.tsx/.css              # saisie d'une réponse selon son type
│   ├── QuestionDefinitionForm.tsx/.css   # création/édition d'une question (catalogue + fiche)
│   ├── CatalogEditor.tsx/.css            # catalogue d'un groupe / projet sans groupe
│   ├── EvaluationsTab.tsx/.css           # onglet du hub projet : liste des fiches
│   ├── SheetEditor.tsx                   # questions d'une fiche (brouillon), lien, transitions
│   ├── InternalEvaluationForm.tsx        # partie chef de projet
│   ├── SheetResults.tsx/.css             # synthèse + réponses + export CSV
│   ├── SheetPrintView.tsx/.css           # impression PDF : un document par répondant
│   └── PublicEvaluationPage.tsx/.css     # /evaluation/<token>
├── App.tsx                               # + route publique
├── features/projects/ProjectDetailView.tsx   # + onglet « Évaluations »
├── features/projects/ProjectAdminTab.tsx     # + CatalogEditor (projet sans groupe)
└── features/administration/GroupsSection.tsx # + CatalogEditor (groupe)
```

---

### Tâche 1 : app, modèles, catalogue par défaut et amorçage

**Fichiers :**
- Créer : `apps/evaluations/__init__.py`, `apps.py`, `models.py`, `defaults.py`, `catalog.py` (amorçage seulement dans cette tâche), `receivers.py`, `admin.py`, `tests/__init__.py`, `tests/factories.py`, `tests/test_catalog.py`
- Modifier : `config/settings/base.py` (`INSTALLED_APPS` : ajouter `"apps.evaluations"` après `"apps.communication"`)
- Migrations : `0001_initial.py` (générée), `0002_seed_default_catalog.py` (données)

**Interfaces produites :**
- Modèles `CatalogQuestion`, `EvaluationSheet`, `SheetQuestion`, `ClientResponse`, `InternalEvaluation`, `Answer`
- Constantes `SECTIONS = ("client", "interne")`, `ANSWER_TYPES`, `CONDITIONABLE_TYPES`, `CHOICE_TYPES`, `NUMERIC_TYPES`
- `catalog.catalog_scope(project) -> Team | Project`, `catalog.scope_filter(scope) -> dict`, `catalog.get_catalog(scope, section=None, include_archived=False) -> QuerySet`, `catalog.seed_default_catalog(scope) -> None`

- [ ] **Étape 1 : écrire les tests d'amorçage qui échouent**

`apps/evaluations/tests/factories.py` :

```python
from apps.accounts.models import Team, TeamMembership, User
from apps.projects.models import Project, ProjectMembership


def make_user(username, **kwargs):
    return User.objects.create_user(username=username, **kwargs)


def make_team_project(name="Collab"):
    """Groupe + projet collaboratif + un chef de projet, un membre, un admin de groupe."""
    manager = make_user(f"{name.lower()}-cp")
    member = make_user(f"{name.lower()}-membre")
    team_admin = make_user(f"{name.lower()}-admin-groupe")
    team = Team.objects.create(name=f"Groupe {name}", created_by=team_admin)
    TeamMembership.objects.create(team=team, user=team_admin, role="administrateur")
    TeamMembership.objects.create(team=team, user=manager)
    TeamMembership.objects.create(team=team, user=member)
    project = Project.objects.create(name=name, team=team)
    ProjectMembership.objects.create(project=project, user=manager, role="chef_de_projet")
    ProjectMembership.objects.create(project=project, user=member, role="membre")
    return {"team": team, "project": project, "manager": manager, "member": member, "team_admin": team_admin}


def make_individual_project(name="Perso"):
    manager = make_user(f"{name.lower()}-cp")
    project = Project.objects.create(name=name, project_type="individuel")
    ProjectMembership.objects.create(project=project, user=manager, role="chef_de_projet")
    return {"project": project, "manager": manager}
```

`apps/evaluations/tests/test_catalog.py` (premier bloc) :

```python
from django.test import TestCase

from apps.accounts.models import Team
from apps.evaluations import catalog
from apps.evaluations.defaults import DEFAULT_CATALOG
from apps.evaluations.models import CatalogQuestion
from apps.projects.models import Project

from .factories import make_individual_project, make_team_project


class CatalogSeedingTests(TestCase):
    def test_new_team_gets_default_catalog_in_both_sections(self):
        team = Team.objects.create(name="Dev")
        questions = CatalogQuestion.all_objects.filter(team=team)
        self.assertEqual(questions.count(), len(DEFAULT_CATALOG))
        self.assertEqual(set(questions.values_list("section", flat=True)), {"client", "interne"})

    def test_project_without_team_gets_its_own_catalog(self):
        project = make_individual_project()["project"]
        self.assertEqual(CatalogQuestion.all_objects.filter(project=project).count(), len(DEFAULT_CATALOG))

    def test_project_with_team_uses_team_catalog(self):
        data = make_team_project()
        self.assertEqual(CatalogQuestion.all_objects.filter(project=data["project"]).count(), 0)
        self.assertEqual(catalog.catalog_scope(data["project"]), data["team"])

    def test_default_conditions_point_to_the_realisation_question(self):
        team = Team.objects.create(name="Dev")
        realisation = CatalogQuestion.all_objects.get(team=team, label="Le projet a été réalisé")
        dependents = CatalogQuestion.all_objects.filter(team=team, condition_on=realisation)
        self.assertEqual(dependents.count(), 4)

    def test_seeding_is_idempotent(self):
        team = Team.objects.create(name="Dev")
        catalog.seed_default_catalog(team)
        self.assertEqual(CatalogQuestion.all_objects.filter(team=team).count(), len(DEFAULT_CATALOG))
```

- [ ] **Étape 2 : lancer les tests, constater l'échec**

Run : `.venv/Scripts/python.exe manage.py test apps.evaluations`
Attendu : ERREUR (`No module named 'apps.evaluations'`).

- [ ] **Étape 3 : écrire l'app**

`apps/evaluations/apps.py` :

```python
from django.apps import AppConfig


class EvaluationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.evaluations"
    label = "evaluations"
    verbose_name = "Évaluations de projet"

    def ready(self):
        from . import receivers  # noqa: F401
```

`apps/evaluations/models.py` :

```python
from django.conf import settings
from django.db import models

from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel

SECTION_CHOICES = [("client", "Satisfaction client"), ("interne", "Évaluation chef de projet")]
SECTIONS = tuple(key for key, _ in SECTION_CHOICES)

ANSWER_TYPE_CHOICES = [
    ("note_5", "Note de 1 à 5"),
    ("nps_10", "Recommandation de 0 à 10"),
    ("oui_non", "Oui / Non"),
    ("choix_unique", "Choix unique"),
    ("choix_multiple", "Choix multiple"),
    ("texte_court", "Texte court"),
    ("texte_long", "Texte long"),
]
ANSWER_TYPES = tuple(key for key, _ in ANSWER_TYPE_CHOICES)
CONDITIONABLE_TYPES = frozenset({"oui_non", "choix_unique"})
CHOICE_TYPES = frozenset({"choix_unique", "choix_multiple"})
NUMERIC_TYPES = frozenset({"note_5", "nps_10", "oui_non"})


class QuestionDefinition(models.Model):
    """Champs communs à une question du catalogue et à sa copie dans une fiche.
    `condition_on` est déclaré dans chaque sous-classe (FK vers son propre modèle)."""

    section = models.CharField(max_length=10, choices=SECTION_CHOICES)
    label = models.CharField(max_length=300)
    help_text = models.CharField(max_length=500, blank=True, default="")
    answer_type = models.CharField(max_length=20, choices=ANSWER_TYPE_CHOICES)
    # Options d'un choix unique/multiple : liste de chaînes, vide sinon.
    options = models.JSONField(default=list, blank=True)
    required = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    # Valeurs de la question `condition_on` qui affichent celle-ci ("oui"/"non"
    # ou options d'un choix unique). Vide si pas de condition.
    condition_values = models.JSONField(default=list, blank=True)

    class Meta:
        abstract = True


class CatalogQuestion(UUIDModel, TimeStampedModel, StatusLifecycleModel, QuestionDefinition):
    """Question générique d'un groupe (`team`) ou d'un projet sans groupe
    (`project`), exactement l'un des deux (garanti par le service, comme
    `TaskType`). Copiée dans chaque nouvelle fiche (`SheetQuestion`)."""

    STATUS_CHOICES = [("active", "Active"), ("archived", "Archivée")]
    ACTIVE_STATUSES = frozenset({"active"})

    team = models.ForeignKey(
        "accounts.Team", null=True, blank=True, on_delete=models.PROTECT, related_name="evaluation_questions"
    )
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT, related_name="evaluation_questions"
    )
    condition_on = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="dependents"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["section", "position", "created_at"]

    def __str__(self):
        return self.label


class EvaluationSheet(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Fiche d'évaluation d'un projet. Cycle de vie :
    brouillon -> ouverte <-> close -> archivee."""

    STATUS_CHOICES = [
        ("brouillon", "Brouillon"),
        ("ouverte", "Ouverte"),
        ("close", "Close"),
        ("archivee", "Archivée"),
    ]
    ACTIVE_STATUSES = frozenset({"brouillon", "ouverte", "close"})

    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="evaluation_sheets")
    title = models.CharField(max_length=200)
    client_intro = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="brouillon")
    public_token = models.CharField(max_length=64, null=True, blank=True, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class SheetQuestion(UUIDModel, TimeStampedModel, StatusLifecycleModel, QuestionDefinition):
    """Copie figée d'une question dans une fiche. `catalog_question` renseigné
    = question générique (non modifiable, sert à agréger les stats) ; vide =
    question propre à la fiche."""

    STATUS_CHOICES = [("active", "Active"), ("archived", "Archivée")]
    ACTIVE_STATUSES = frozenset({"active"})

    sheet = models.ForeignKey(EvaluationSheet, on_delete=models.PROTECT, related_name="questions")
    catalog_question = models.ForeignKey(
        CatalogQuestion, null=True, blank=True, on_delete=models.PROTECT, related_name="sheet_copies"
    )
    condition_on = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="dependents"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["section", "position", "created_at"]

    def __str__(self):
        return self.label


class ClientResponse(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Une réponse reçue via le lien public. `ecartee` = retirée des
    résultats (spam, test), jamais supprimée."""

    STATUS_CHOICES = [("retenue", "Retenue"), ("ecartee", "Écartée")]
    ACTIVE_STATUSES = frozenset({"retenue"})

    sheet = models.ForeignKey(EvaluationSheet, on_delete=models.PROTECT, related_name="client_responses")
    respondent_name = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="retenue")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["-created_at"]


class InternalEvaluation(UUIDModel, TimeStampedModel):
    """Partie chef de projet : une seule par fiche, partagée par les chefs de projet."""

    sheet = models.OneToOneField(EvaluationSheet, on_delete=models.PROTECT, related_name="internal_evaluation")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")


class Answer(UUIDModel, TimeStampedModel):
    """Réponse à une question : rattachée à une réponse client **ou** à la
    partie interne. Jamais supprimée ; une réponse effacée garde `value=None`."""

    question = models.ForeignKey(SheetQuestion, on_delete=models.PROTECT, related_name="answers")
    client_response = models.ForeignKey(
        ClientResponse, null=True, blank=True, on_delete=models.PROTECT, related_name="answers"
    )
    internal_evaluation = models.ForeignKey(
        InternalEvaluation, null=True, blank=True, on_delete=models.PROTECT, related_name="answers"
    )
    value = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["client_response", "question"],
                condition=models.Q(client_response__isnull=False),
                name="unique_answer_per_client_response",
            ),
            models.UniqueConstraint(
                fields=["internal_evaluation", "question"],
                condition=models.Q(internal_evaluation__isnull=False),
                name="unique_answer_per_internal_evaluation",
            ),
        ]
```

`apps/evaluations/defaults.py` :

```python
"""Questions génériques livrées à chaque nouveau groupe / projet sans groupe.
`condition` = (index dans cette liste de la question cible, valeurs)."""

_PRESTA = ["Par un prestataire", "Mixte"]
_INTERNE = ["En interne", "Mixte"]

DEFAULT_CATALOG = [
    # --- Satisfaction client ---
    {"section": "client", "label": "Globalement, êtes-vous satisfait de la façon dont le projet a été mené ?",
     "answer_type": "note_5", "required": True},
    {"section": "client", "label": "Le résultat livré répond-il à votre besoin ?",
     "answer_type": "note_5", "required": True},
    {"section": "client", "label": "Les délais annoncés ont-ils été respectés ?",
     "answer_type": "oui_non", "required": True},
    {"section": "client", "label": "Comment jugez-vous la communication pendant le projet ?",
     "answer_type": "note_5", "required": True},
    {"section": "client", "label": "Recommanderiez-vous l'équipe projet à un collègue ?",
     "answer_type": "nps_10", "required": True},
    {"section": "client", "label": "Remarques ou suggestions", "answer_type": "texte_long"},
    # --- Évaluation chef de projet ---
    {"section": "interne", "label": "Le projet a été réalisé", "answer_type": "choix_unique",
     "options": ["En interne", "Par un prestataire", "Mixte"], "required": True},
    {"section": "interne", "label": "Nom du prestataire", "answer_type": "texte_court",
     "condition": (6, _PRESTA)},
    {"section": "interne", "label": "Comment la prestation a-t-elle été gérée (suivi, qualité, respect du contrat) ?",
     "answer_type": "texte_long", "condition": (6, _PRESTA)},
    {"section": "interne", "label": "Note de la prestation", "answer_type": "note_5", "condition": (6, _PRESTA)},
    {"section": "interne", "label": "Difficultés rencontrées en interne", "answer_type": "texte_long",
     "condition": (6, _INTERNE)},
    {"section": "interne", "label": "Le budget prévu a-t-il été respecté ?", "answer_type": "oui_non"},
    {"section": "interne", "label": "Le planning prévu a-t-il été respecté ?", "answer_type": "oui_non"},
    {"section": "interne", "label": "Points forts du projet", "answer_type": "texte_long"},
    {"section": "interne", "label": "Axes d'amélioration, retours d'expérience", "answer_type": "texte_long"},
]
```

`apps/evaluations/catalog.py` (partie amorçage ; la tâche 3 ajoute les services) :

```python
from apps.accounts.models import Team

from .defaults import DEFAULT_CATALOG
from .models import CatalogQuestion


def catalog_scope(project):
    """`Team` ou `Project` portant le catalogue de `project`."""
    return project.team if project.team_id else project


def scope_filter(scope):
    return {"team": scope} if isinstance(scope, Team) else {"project": scope}


def get_catalog(scope, section=None, include_archived=False):
    qs = CatalogQuestion.all_objects.filter(**scope_filter(scope))
    if section is not None:
        qs = qs.filter(section=section)
    if not include_archived:
        qs = qs.filter(status="active")
    return qs.order_by("section", "position", "created_at")


def seed_default_catalog(scope, question_model=CatalogQuestion):
    """Idempotent : rien si la portée a déjà au moins une question (même
    archivée). `question_model` permet l'appel depuis une migration de données
    (manager historique non filtré) ; au runtime on passe par `all_objects`."""
    manager = getattr(question_model, "all_objects", question_model.objects)
    if manager.filter(**scope_filter_for(question_model, scope)).exists():
        return
    created = []
    for index, spec in enumerate(DEFAULT_CATALOG):
        created.append(
            manager.create(
                section=spec["section"],
                label=spec["label"],
                answer_type=spec["answer_type"],
                options=list(spec.get("options", [])),
                required=spec.get("required", False),
                position=index,
                **scope_filter_for(question_model, scope),
            )
        )
    for index, spec in enumerate(DEFAULT_CATALOG):
        if "condition" in spec:
            target_index, values = spec["condition"]
            question = created[index]
            question.condition_on = created[target_index]
            question.condition_values = list(values)
            question.save(update_fields=["condition_on", "condition_values"])


def scope_filter_for(question_model, scope):
    # Dans une migration, `scope` est une instance du modèle historique : on
    # se fie au nom du modèle plutôt qu'à `isinstance(scope, Team)`.
    return {"team_id": scope.pk} if type(scope).__name__ == "Team" else {"project_id": scope.pk}
```

`apps/evaluations/receivers.py` :

```python
"""Amorce le catalogue par défaut à la naissance d'une portée. Même schéma que
`apps.tasks.receivers` : `evaluations` dépend déjà d'`accounts`/`projects`."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import Team
from apps.projects.models import Project

from .catalog import seed_default_catalog


@receiver(post_save, sender=Team)
def _seed_team_catalog(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        seed_default_catalog(instance)


@receiver(post_save, sender=Project)
def _seed_project_catalog(sender, instance, created, raw=False, **kwargs):
    if created and not raw and instance.team_id is None:
        seed_default_catalog(instance)
```

`apps/evaluations/admin.py` : enregistrer `CatalogQuestion`, `EvaluationSheet`, `ClientResponse` (`list_display` : libellé ou titre, statut, portée ou projet).

- [ ] **Étape 4 : générer les migrations**

Run : `.venv/Scripts/python.exe manage.py makemigrations evaluations`
puis `.venv/Scripts/python.exe manage.py makemigrations evaluations --empty -n seed_default_catalog`. Contenu de la seconde :

```python
from django.db import migrations


def seed(apps, schema_editor):
    from apps.evaluations.catalog import seed_default_catalog

    CatalogQuestion = apps.get_model("evaluations", "CatalogQuestion")
    Team = apps.get_model("accounts", "Team")
    Project = apps.get_model("projects", "Project")
    for team in Team.objects.all():
        seed_default_catalog(team, question_model=CatalogQuestion)
    for project in Project.objects.filter(team__isnull=True):
        seed_default_catalog(project, question_model=CatalogQuestion)


class Migration(migrations.Migration):
    dependencies = [("evaluations", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
```

- [ ] **Étape 5 : lancer les tests**

Run : `.venv/Scripts/python.exe manage.py test apps.evaluations apps.common`
Attendu : tout passe (dont `apps/common/tests/test_models.py`, qui contrôle les `Meta` des managers).

- [ ] **Étape 6 : commit** (si autorisé) — `feat(evaluations): add models and default question catalog`

---

### Tâche 2 : réponses et visibilité conditionnelle (logique pure)

**Fichiers :**
- Créer : `apps/evaluations/answers.py`, `apps/evaluations/tests/test_answers.py`

**Interfaces produites :**
- `class AnswerError(ValueError)` avec `.question_id: str | None` et `.message: str`
- `normalize_answer(question, raw) -> int | str | list[str] | None`
- `visible_question_ids(questions, answers: dict[str, object]) -> set[str]`
- `clean_answers(questions, raw_answers: dict, *, enforce_required: bool) -> dict[str, object]` : une valeur normalisée par question (`None` si vide ou masquée)

`question` est tout objet qui porte `id`, `label`, `answer_type`, `options`, `required`, `condition_on_id` et `condition_values` (`SheetQuestion` en pratique, un `SimpleNamespace` dans les tests).

- [ ] **Étape 1 : tests qui échouent**

```python
from types import SimpleNamespace
from django.test import SimpleTestCase

from apps.evaluations.answers import AnswerError, clean_answers, normalize_answer, visible_question_ids


def q(id, answer_type, *, options=(), required=False, condition_on=None, values=()):
    return SimpleNamespace(id=id, label=f"Q{id}", answer_type=answer_type, options=list(options),
                           required=required, condition_on_id=condition_on, condition_values=list(values))


class NormalizeTests(SimpleTestCase):
    def test_note_bounds(self):
        self.assertEqual(normalize_answer(q("a", "note_5"), 5), 5)
        for bad in (0, 6, "3", True, 2.5):
            with self.assertRaises(AnswerError):
                normalize_answer(q("a", "note_5"), bad)

    def test_nps_bounds(self):
        self.assertEqual(normalize_answer(q("a", "nps_10"), 0), 0)
        with self.assertRaises(AnswerError):
            normalize_answer(q("a", "nps_10"), 11)

    def test_yes_no_accepts_bool_and_text(self):
        self.assertEqual(normalize_answer(q("a", "oui_non"), True), "oui")
        self.assertEqual(normalize_answer(q("a", "oui_non"), "non"), "non")
        with self.assertRaises(AnswerError):
            normalize_answer(q("a", "oui_non"), "peut-être")

    def test_choices_must_be_known_options(self):
        single = q("a", "choix_unique", options=["A", "B"])
        multi = q("b", "choix_multiple", options=["A", "B"])
        self.assertEqual(normalize_answer(single, "B"), "B")
        self.assertEqual(normalize_answer(multi, ["A", "B"]), ["A", "B"])
        for question, bad in ((single, "C"), (multi, ["A", "A"]), (multi, ["Z"]), (multi, "A")):
            with self.assertRaises(AnswerError):
                normalize_answer(question, bad)

    def test_text_is_trimmed_and_limited(self):
        self.assertEqual(normalize_answer(q("a", "texte_court"), "  ok "), "ok")
        self.assertIsNone(normalize_answer(q("a", "texte_court"), "   "))
        with self.assertRaises(AnswerError):
            normalize_answer(q("a", "texte_court"), "x" * 201)
        with self.assertRaises(AnswerError):
            normalize_answer(q("a", "texte_long"), "x" * 5001)

    def test_empty_values_are_none(self):
        for empty in (None, "", []):
            self.assertIsNone(normalize_answer(q("a", "choix_multiple", options=["A"]), empty))


class VisibilityTests(SimpleTestCase):
    def setUp(self):
        self.root = q("r", "choix_unique", options=["Interne", "Presta", "Mixte"])
        self.presta = q("p", "texte_court", condition_on="r", values=["Presta", "Mixte"])
        self.sub = q("s", "note_5", condition_on="p", values=[])  # dépend d'une question masquable
        self.questions = [self.root, self.presta, self.sub]

    def test_condition_met(self):
        self.assertEqual(visible_question_ids([self.root, self.presta], {"r": "Mixte"}), {"r", "p"})

    def test_condition_not_met(self):
        self.assertEqual(visible_question_ids([self.root, self.presta], {"r": "Interne"}), {"r"})

    def test_hidden_parent_hides_child(self):
        self.assertNotIn("s", visible_question_ids(self.questions, {"r": "Interne", "p": "x"}))

    def test_missing_target_keeps_question_visible(self):
        self.assertEqual(visible_question_ids([self.presta], {}), {"p"})


class CleanAnswersTests(SimpleTestCase):
    def setUp(self):
        self.root = q("r", "oui_non", required=True)
        self.detail = q("d", "texte_long", required=True, condition_on="r", values=["oui"])
        self.questions = [self.root, self.detail]

    def test_hidden_answers_are_dropped(self):
        cleaned = clean_answers(self.questions, {"r": False, "d": "texte"}, enforce_required=True)
        self.assertEqual(cleaned, {"r": "non", "d": None})

    def test_required_visible_question_is_enforced(self):
        with self.assertRaises(AnswerError) as ctx:
            clean_answers(self.questions, {"r": True}, enforce_required=True)
        self.assertEqual(ctx.exception.question_id, "d")

    def test_required_not_enforced_for_drafts(self):
        self.assertEqual(clean_answers(self.questions, {}, enforce_required=False), {"r": None, "d": None})

    def test_unknown_question_is_rejected(self):
        with self.assertRaises(AnswerError):
            clean_answers(self.questions, {"zzz": 1}, enforce_required=False)
```

- [ ] **Étape 2 : lancer et constater l'échec** — `.venv/Scripts/python.exe manage.py test apps.evaluations.tests.test_answers` → ImportError.

- [ ] **Étape 3 : implémenter `answers.py`**

```python
"""Normalisation des réponses et visibilité conditionnelle. Aucune dépendance
ORM : utilisé par les services et miroir exact de
`frontend/src/features/evaluations/visibility.ts`."""

TEXT_LIMITS = {"texte_court": 200, "texte_long": 5000}
_EMPTY = (None, "", [])


class AnswerError(ValueError):
    def __init__(self, question_id, message):
        super().__init__(message)
        self.question_id = question_id
        self.message = message


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def normalize_answer(question, raw):
    """Valeur normalisée (`int`, `"oui"`/`"non"`, chaîne, liste) ou `None` si vide."""
    if any(raw is empty or raw == empty for empty in _EMPTY):
        return None
    qid = str(question.id)
    kind = question.answer_type
    if kind in ("note_5", "nps_10"):
        low, high = (1, 5) if kind == "note_5" else (0, 10)
        if not _is_int(raw) or not low <= raw <= high:
            raise AnswerError(qid, f"Réponse attendue entre {low} et {high} : {question.label}")
        return raw
    if kind == "oui_non":
        if raw is True or raw == "oui":
            return "oui"
        if raw is False or raw == "non":
            return "non"
        raise AnswerError(qid, f"Réponse oui/non attendue : {question.label}")
    if kind == "choix_unique":
        if raw not in question.options:
            raise AnswerError(qid, f"Choix inconnu : {question.label}")
        return raw
    if kind == "choix_multiple":
        if (
            not isinstance(raw, list)
            or len(set(raw)) != len(raw)
            or any(value not in question.options for value in raw)
        ):
            raise AnswerError(qid, f"Choix inconnu : {question.label}")
        return raw
    if not isinstance(raw, str):
        raise AnswerError(qid, f"Texte attendu : {question.label}")
    text = raw.strip()
    if len(text) > TEXT_LIMITS[kind]:
        raise AnswerError(qid, f"Texte trop long ({TEXT_LIMITS[kind]} caractères maximum) : {question.label}")
    return text or None


def visible_question_ids(questions, answers):
    """Une question est visible si elle n'a pas de condition, ou si sa
    question cible est visible et que la réponse à la cible figure dans
    `condition_values`. Une cible absente (archivée) laisse la question visible.
    Les cycles sont interdits à l'écriture (`definitions.clean_condition`)."""
    by_id = {str(question.id): question for question in questions}
    memo = {}

    def is_visible(qid):
        if qid not in memo:
            question = by_id[qid]
            target = str(question.condition_on_id) if question.condition_on_id else None
            if target is None or target not in by_id:
                memo[qid] = True
            else:
                memo[qid] = is_visible(target) and answers.get(target) in question.condition_values
        return memo[qid]

    return {qid for qid in by_id if is_visible(qid)}


def clean_answers(questions, raw_answers, *, enforce_required):
    by_id = {str(question.id): question for question in questions}
    raw_answers = {str(key): value for key, value in (raw_answers or {}).items()}
    if set(raw_answers) - set(by_id):
        raise AnswerError(None, "Réponse à une question inconnue.")
    normalized = {qid: normalize_answer(question, raw_answers.get(qid)) for qid, question in by_id.items()}
    visible = visible_question_ids(questions, normalized)
    cleaned = {qid: (value if qid in visible else None) for qid, value in normalized.items()}
    if enforce_required:
        for question in questions:
            qid = str(question.id)
            if qid in visible and question.required and cleaned[qid] is None:
                raise AnswerError(qid, f"Réponse obligatoire : {question.label}")
    return cleaned
```

- [ ] **Étape 4 : lancer les tests** → PASS.
- [ ] **Étape 5 : commit** (si autorisé) — `feat(evaluations): validate answers and conditional visibility`

---

### Tâche 3 : services et API du catalogue

**Fichiers :**
- Créer : `apps/evaluations/definitions.py`, `serializers.py`, `views.py`, `urls.py`
- Modifier : `apps/evaluations/catalog.py`, `config/urls.py` (ajouter `path("evaluations/", include("apps.evaluations.urls")),` dans `api_v1_patterns`), `apps/evaluations/tests/test_catalog.py`
- Créer : `apps/evaluations/tests/test_api.py`

**Interfaces produites :**
- `class EvaluationPermissionError(Exception)`, `class EvaluationValidationError(Exception)` dans `definitions.py`
- `definitions.clean_definition(*, siblings, current, section, label, help_text, answer_type, options, required, condition_on, condition_values) -> dict` : `siblings` sont les questions actives de la même portée (catalogue ou fiche), `current` est l'objet modifié ou `None`
- `definitions.ensure_no_dependents(question) -> None`
- `catalog.can_view_catalog(user, scope) -> bool`, `catalog.can_manage_catalog(user, scope) -> bool`
- `catalog.list_catalog(*, actor, scope, include_archived=False)`
- `catalog.create_catalog_question(*, actor, scope, **definition) -> CatalogQuestion`
- `catalog.update_catalog_question(*, actor, question, **changes) -> CatalogQuestion` (`answer_type` refusé)
- `catalog.archive_catalog_question(*, actor, question)`, `catalog.restore_catalog_question(*, actor, question)`
- `catalog.move_catalog_question(*, actor, question, direction: "up" | "down")`
- Endpoints : `GET/POST /api/v1/evaluations/catalog/?team=<uuid>|project=<uuid>[&include_archived=1]`, `PATCH /catalog/{id}/`, `POST /catalog/{id}/archive/`, `/restore/`, `/move/` (`{"direction": "up"|"down"}`)

- [ ] **Étape 1 : tests de service qui échouent** (à ajouter dans `test_catalog.py`)

```python
from apps.evaluations.definitions import EvaluationPermissionError, EvaluationValidationError
from apps.accounts.models import User


class CatalogServiceTests(TestCase):
    def setUp(self):
        self.data = make_team_project()
        self.team = self.data["team"]

    def _create(self, actor, **overrides):
        payload = {"section": "client", "label": "Accueil ?", "answer_type": "note_5"}
        payload.update(overrides)
        return catalog.create_catalog_question(actor=actor, scope=self.team, **payload)

    def test_team_admin_creates_question(self):
        question = self._create(self.data["team_admin"])
        self.assertEqual(question.team, self.team)

    def test_project_manager_is_not_team_admin(self):
        with self.assertRaises(EvaluationPermissionError):
            self._create(self.data["manager"])

    def test_member_can_view_but_not_manage(self):
        self.assertTrue(catalog.can_view_catalog(self.data["member"], self.team))
        self.assertFalse(catalog.can_manage_catalog(self.data["member"], self.team))

    def test_individual_project_catalog_is_managed_by_its_manager(self):
        perso = make_individual_project()
        question = catalog.create_catalog_question(
            actor=perso["manager"], scope=perso["project"], section="interne", label="Bilan", answer_type="texte_long"
        )
        self.assertEqual(question.project, perso["project"])

    def test_choice_question_requires_two_distinct_options(self):
        with self.assertRaises(EvaluationValidationError):
            self._create(self.data["team_admin"], answer_type="choix_unique", options=["A"])
        with self.assertRaises(EvaluationValidationError):
            self._create(self.data["team_admin"], answer_type="choix_unique", options=["A", "a"])

    def test_condition_must_target_a_conditionable_question_of_same_section(self):
        admin = self.data["team_admin"]
        text = self._create(admin, answer_type="texte_court")
        with self.assertRaises(EvaluationValidationError):
            self._create(admin, label="Détail", condition_on=text.id, condition_values=["x"])
        interne = self._create(admin, section="interne", answer_type="oui_non", label="Budget ok ?")
        with self.assertRaises(EvaluationValidationError):
            self._create(admin, label="Détail", condition_on=interne.id, condition_values=["oui"])

    def test_condition_values_must_exist(self):
        admin = self.data["team_admin"]
        root = self._create(admin, answer_type="choix_unique", options=["A", "B"])
        with self.assertRaises(EvaluationValidationError):
            self._create(admin, label="Détail", condition_on=root.id, condition_values=["C"])

    def test_condition_cycle_is_refused(self):
        admin = self.data["team_admin"]
        a = self._create(admin, label="A", answer_type="oui_non")
        b = self._create(admin, label="B", answer_type="oui_non", condition_on=a.id, condition_values=["oui"])
        with self.assertRaises(EvaluationValidationError):
            catalog.update_catalog_question(actor=admin, question=a, condition_on=b.id, condition_values=["oui"])

    def test_answer_type_is_frozen(self):
        question = self._create(self.data["team_admin"])
        with self.assertRaises(EvaluationValidationError):
            catalog.update_catalog_question(actor=self.data["team_admin"], question=question, answer_type="nps_10")

    def test_cannot_archive_a_condition_target(self):
        admin = self.data["team_admin"]
        realisation = CatalogQuestion.all_objects.get(team=self.team, label="Le projet a été réalisé")
        with self.assertRaises(EvaluationValidationError):
            catalog.archive_catalog_question(actor=admin, question=realisation)

    def test_options_still_used_by_a_condition_cannot_be_removed(self):
        admin = self.data["team_admin"]
        realisation = CatalogQuestion.all_objects.get(team=self.team, label="Le projet a été réalisé")
        with self.assertRaises(EvaluationValidationError):
            catalog.update_catalog_question(actor=admin, question=realisation, options=["En interne", "Mixte"])

    def test_move_swaps_positions_within_section(self):
        admin = self.data["team_admin"]
        first, second = list(catalog.get_catalog(self.team, section="client"))[:2]
        catalog.move_catalog_question(actor=admin, question=second, direction="up")
        ordered = list(catalog.get_catalog(self.team, section="client"))
        self.assertEqual(ordered[0].pk, second.pk)
        self.assertEqual(ordered[1].pk, first.pk)
```

- [ ] **Étape 2 : lancer et constater l'échec.**

- [ ] **Étape 3 : `definitions.py`**

```python
from .models import ANSWER_TYPES, CHOICE_TYPES, CONDITIONABLE_TYPES, SECTIONS


class EvaluationPermissionError(Exception):
    pass


class EvaluationValidationError(Exception):
    pass


def _clean_label(label):
    label = (label or "").strip()
    if not label:
        raise EvaluationValidationError("Le libellé de la question ne peut pas être vide.")
    if len(label) > 300:
        raise EvaluationValidationError("Le libellé ne peut pas dépasser 300 caractères.")
    return label


def _clean_options(answer_type, options):
    if answer_type not in CHOICE_TYPES:
        return []
    cleaned = [str(option).strip() for option in (options or []) if str(option).strip()]
    if len(cleaned) < 2:
        raise EvaluationValidationError("Un choix demande au moins deux options.")
    if len({option.casefold() for option in cleaned}) != len(cleaned):
        raise EvaluationValidationError("Deux options portent le même libellé.")
    if any(len(option) > 150 for option in cleaned):
        raise EvaluationValidationError("Une option ne peut pas dépasser 150 caractères.")
    return cleaned


def allowed_condition_values(target):
    return ["oui", "non"] if target.answer_type == "oui_non" else list(target.options)


def _creates_cycle(current, target, by_id):
    node = target
    while node is not None:
        if current is not None and node.pk == current.pk:
            return True
        node = by_id.get(node.condition_on_id)
    return False


def clean_definition(*, siblings, current, section, label, help_text, answer_type, options, required,
                     condition_on, condition_values):
    """Valide une définition complète de question et renvoie les champs à
    enregistrer. `condition_on` : UUID (ou `None`) d'une question de `siblings`."""
    if section not in SECTIONS:
        raise EvaluationValidationError("Partie inconnue.")
    if answer_type not in ANSWER_TYPES:
        raise EvaluationValidationError("Type de réponse inconnu.")
    help_text = (help_text or "").strip()
    if len(help_text) > 500:
        raise EvaluationValidationError("L'aide ne peut pas dépasser 500 caractères.")
    cleaned = {
        "section": section,
        "label": _clean_label(label),
        "help_text": help_text,
        "answer_type": answer_type,
        "options": _clean_options(answer_type, options),
        "required": bool(required),
        "condition_on": None,
        "condition_values": [],
    }
    by_id = {sibling.pk: sibling for sibling in siblings}
    if condition_on:
        target = next((s for s in siblings if str(s.pk) == str(condition_on)), None)
        if target is None:
            raise EvaluationValidationError("La question dont dépend celle-ci est introuvable.")
        if current is not None and target.pk == current.pk:
            raise EvaluationValidationError("Une question ne peut pas dépendre d'elle-même.")
        if target.section != section:
            raise EvaluationValidationError("Une condition porte sur une question de la même partie.")
        if target.answer_type not in CONDITIONABLE_TYPES:
            raise EvaluationValidationError("Une condition porte sur une question oui/non ou à choix unique.")
        if _creates_cycle(current, target, by_id):
            raise EvaluationValidationError("Cette condition créerait une boucle entre questions.")
        values = [str(v) for v in (condition_values or [])]
        if not values or any(v not in allowed_condition_values(target) for v in values):
            raise EvaluationValidationError("Choisissez au moins une réponse qui affiche la question.")
        cleaned["condition_on"] = target
        cleaned["condition_values"] = values
    # Une question dont d'autres dépendent garde des réponses compatibles.
    if current is not None:
        for dependent in current.dependents.filter(status="active"):
            if cleaned["answer_type"] not in CONDITIONABLE_TYPES:
                raise EvaluationValidationError("D'autres questions dépendent de celle-ci.")
            allowed = ["oui", "non"] if cleaned["answer_type"] == "oui_non" else cleaned["options"]
            if any(value not in allowed for value in dependent.condition_values):
                raise EvaluationValidationError(
                    f"La question « {dependent.label} » dépend d'une option que vous retirez."
                )
    return cleaned


def ensure_no_dependents(question):
    if question.dependents.filter(status="active").exists():
        raise EvaluationValidationError("D'autres questions dépendent de celle-ci : retirez d'abord leur condition.")


def definition_of(question):
    """Champs actuels d'une question, pour fusionner une modification partielle."""
    return {
        "section": question.section,
        "label": question.label,
        "help_text": question.help_text,
        "answer_type": question.answer_type,
        "options": question.options,
        "required": question.required,
        "condition_on": question.condition_on_id,
        "condition_values": question.condition_values,
    }
```

- [ ] **Étape 4 : services du catalogue (`catalog.py`, à la suite de l'amorçage)**

```python
from apps.accounts.services import can_manage_team, is_active_team_member
from apps.projects.services import is_project_manager, is_project_member

from .definitions import (
    EvaluationPermissionError,
    EvaluationValidationError,
    clean_definition,
    definition_of,
    ensure_no_dependents,
)

_EDITABLE = {"label", "help_text", "options", "required", "condition_on", "condition_values"}


def can_view_catalog(user, scope):
    if isinstance(scope, Team):
        return is_active_team_member(user, scope) or can_manage_team(user, scope)
    return is_project_member(user, scope)


def can_manage_catalog(user, scope):
    """Groupe : tout administrateur du groupe (décision du 2026-11-13, sans
    capacité de profil). Projet sans groupe : son chef de projet."""
    if isinstance(scope, Team):
        return can_manage_team(user, scope)
    return is_project_manager(user, scope)


def _ensure_manage(actor, scope):
    if not can_manage_catalog(actor, scope):
        raise EvaluationPermissionError("Réservé à un administrateur du groupe (ou au chef de projet).")


def scope_of(question):
    return question.team if question.team_id else question.project


def list_catalog(*, actor, scope, include_archived=False):
    if not can_view_catalog(actor, scope):
        raise EvaluationPermissionError("Réservé aux membres du groupe ou du projet.")
    return get_catalog(scope, include_archived=include_archived)


def create_catalog_question(*, actor, scope, section, label, answer_type, help_text="", options=None,
                            required=False, condition_on=None, condition_values=None):
    _ensure_manage(actor, scope)
    fields = clean_definition(
        siblings=list(get_catalog(scope)), current=None, section=section, label=label, help_text=help_text,
        answer_type=answer_type, options=options, required=required, condition_on=condition_on,
        condition_values=condition_values,
    )
    last = get_catalog(scope, section=section, include_archived=True).order_by("-position").first()
    return CatalogQuestion.all_objects.create(
        position=(last.position + 1) if last else 0, **fields, **scope_filter(scope)
    )


def update_catalog_question(*, actor, question, **changes):
    scope = scope_of(question)
    _ensure_manage(actor, scope)
    if "answer_type" in changes and changes["answer_type"] != question.answer_type:
        raise EvaluationValidationError("Le type de réponse d'une question ne change pas après sa création.")
    unknown = set(changes) - _EDITABLE - {"answer_type"}
    if unknown:
        raise EvaluationValidationError("Champ non modifiable.")
    merged = definition_of(question)
    merged.update({key: value for key, value in changes.items() if key in _EDITABLE})
    fields = clean_definition(siblings=list(get_catalog(scope)), current=question, **merged)
    for key, value in fields.items():
        setattr(question, key, value)
    question.save()
    return question


def archive_catalog_question(*, actor, question):
    _ensure_manage(actor, scope_of(question))
    if question.status != "active":
        raise EvaluationValidationError("Cette question est déjà archivée.")
    ensure_no_dependents(question)
    question.status = "archived"
    question.save(update_fields=["status", "updated_at"])
    return question


def restore_catalog_question(*, actor, question):
    _ensure_manage(actor, scope_of(question))
    if question.status != "archived":
        raise EvaluationValidationError("Cette question n'est pas archivée.")
    if question.condition_on_id and question.condition_on.status != "active":
        raise EvaluationValidationError("La question dont elle dépend est archivée : restaurez-la d'abord.")
    question.status = "active"
    question.save(update_fields=["status", "updated_at"])
    return question


def move_catalog_question(*, actor, question, direction):
    _ensure_manage(actor, scope_of(question))
    swap_position(list(get_catalog(scope_of(question), section=question.section)), question, direction)
    return question


def swap_position(ordered, question, direction):
    """Échange `question` avec sa voisine dans `ordered` (même section) et
    renumérote toute la section. Partagé avec les questions de fiche."""
    if direction not in ("up", "down"):
        raise EvaluationValidationError("Direction inconnue.")
    index = next(i for i, item in enumerate(ordered) if item.pk == question.pk)
    other = index - 1 if direction == "up" else index + 1
    if not 0 <= other < len(ordered):
        return
    ordered[index], ordered[other] = ordered[other], ordered[index]
    for position, item in enumerate(ordered):
        if item.position != position:
            item.position = position
            item.save(update_fields=["position", "updated_at"])
```

- [ ] **Étape 5 : serializers, vues, URLs**

`serializers.py` (partie catalogue ; la tâche 4 complète) :

```python
from rest_framework import serializers

from .models import ANSWER_TYPES, SECTIONS, CatalogQuestion


class QuestionDefinitionInputSerializer(serializers.Serializer):
    section = serializers.ChoiceField(choices=SECTIONS)
    label = serializers.CharField(max_length=300)
    help_text = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    answer_type = serializers.ChoiceField(choices=ANSWER_TYPES)
    options = serializers.ListField(child=serializers.CharField(max_length=150), required=False, default=list)
    required = serializers.BooleanField(required=False, default=False)
    condition_on = serializers.UUIDField(required=False, allow_null=True, default=None)
    condition_values = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class CatalogQuestionCreateSerializer(QuestionDefinitionInputSerializer):
    team = serializers.UUIDField(required=False, allow_null=True, default=None)
    project = serializers.UUIDField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        if bool(attrs.get("team")) == bool(attrs.get("project")):
            raise serializers.ValidationError("Indiquez soit un groupe, soit un projet.")
        return attrs


class QuestionDefinitionUpdateSerializer(serializers.Serializer):
    """Mise à jour partielle : seuls les champs envoyés changent."""

    label = serializers.CharField(max_length=300, required=False)
    help_text = serializers.CharField(max_length=500, required=False, allow_blank=True)
    answer_type = serializers.ChoiceField(choices=ANSWER_TYPES, required=False)
    options = serializers.ListField(child=serializers.CharField(max_length=150), required=False)
    required = serializers.BooleanField(required=False)
    condition_on = serializers.UUIDField(required=False, allow_null=True)
    condition_values = serializers.ListField(child=serializers.CharField(), required=False)


class MoveSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(choices=["up", "down"])


QUESTION_FIELDS = [
    "id", "section", "label", "help_text", "answer_type", "options", "required",
    "position", "condition_on", "condition_values", "status",
]


class CatalogQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogQuestion
        fields = QUESTION_FIELDS + ["team", "project"]
```

`views.py` (partie catalogue) :

```python
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import Team
from apps.projects.models import Project

from . import catalog
from .answers import AnswerError
from .definitions import EvaluationPermissionError, EvaluationValidationError
from .models import CatalogQuestion
from .schema import catalog_schema
from .serializers import (
    CatalogQuestionCreateSerializer,
    CatalogQuestionSerializer,
    MoveSerializer,
    QuestionDefinitionUpdateSerializer,
)


class EvaluationErrorsMixin:
    def handle_exception(self, exc):
        if isinstance(exc, EvaluationPermissionError):
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        if isinstance(exc, AnswerError):
            return Response({"detail": exc.message, "question": exc.question_id}, status=status.HTTP_400_BAD_REQUEST)
        if isinstance(exc, EvaluationValidationError):
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().handle_exception(exc)


def _scope_from(team_id, project_id):
    if team_id:
        return get_object_or_404(Team, pk=team_id)
    return get_object_or_404(Project.all_objects, pk=project_id)


@catalog_schema
class CatalogQuestionViewSet(EvaluationErrorsMixin, viewsets.GenericViewSet):
    queryset = CatalogQuestion.all_objects.all()
    serializer_class = CatalogQuestionSerializer

    def list(self, request):
        team_id, project_id = request.query_params.get("team"), request.query_params.get("project")
        if bool(team_id) == bool(project_id):
            return Response({"detail": "Paramètre team ou project requis."}, status=400)
        scope = _scope_from(team_id, project_id)
        questions = catalog.list_catalog(
            actor=request.user, scope=scope, include_archived=request.query_params.get("include_archived") == "1"
        )
        return Response({
            "can_manage": catalog.can_manage_catalog(request.user, scope),
            "questions": CatalogQuestionSerializer(questions, many=True).data,
        })

    def create(self, request):
        serializer = CatalogQuestionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        scope = _scope_from(data.pop("team"), data.pop("project"))
        question = catalog.create_catalog_question(actor=request.user, scope=scope, **data)
        return Response(CatalogQuestionSerializer(question).data, status=201)

    def partial_update(self, request, pk=None):
        serializer = QuestionDefinitionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        question = catalog.update_catalog_question(
            actor=request.user, question=self.get_object(), **serializer.validated_data
        )
        return Response(CatalogQuestionSerializer(question).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        question = catalog.archive_catalog_question(actor=request.user, question=self.get_object())
        return Response(CatalogQuestionSerializer(question).data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        question = catalog.restore_catalog_question(actor=request.user, question=self.get_object())
        return Response(CatalogQuestionSerializer(question).data)

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        serializer = MoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = catalog.move_catalog_question(
            actor=request.user, question=self.get_object(), direction=serializer.validated_data["direction"]
        )
        return Response(CatalogQuestionSerializer(question).data)
```

> `get_object()` passe par `queryset` sans filtrage de portée : c'est le service qui refuse (403). Pour un objet hors de toute portée accessible, le service lève `EvaluationPermissionError`. Pas de fuite : seuls l'existence et le refus sont observables, même comportement que `TaskTypeViewSet`.

`schema.py` : créer le fichier dès cette tâche avec `catalog_schema = extend_schema_view(...)` (contenu en tâche 8). Provisoirement, `catalog_schema = extend_schema_view()`.

`urls.py` :

```python
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import CatalogQuestionViewSet

router = SimpleRouter(trailing_slash=True)
router.register("catalog", CatalogQuestionViewSet, basename="evaluation-catalog")

urlpatterns = [*router.urls]
```

- [ ] **Étape 6 : test d'API** (`tests/test_api.py`)

```python
from rest_framework.test import APITestCase

from .factories import make_team_project


class CatalogApiTests(APITestCase):
    def setUp(self):
        self.data = make_team_project()

    def test_member_lists_team_catalog(self):
        self.client.force_authenticate(self.data["member"])
        r = self.client.get(f"/api/v1/evaluations/catalog/?team={self.data['team'].id}")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["can_manage"])
        self.assertGreater(len(r.data["questions"]), 0)

    def test_member_cannot_create(self):
        self.client.force_authenticate(self.data["member"])
        r = self.client.post("/api/v1/evaluations/catalog/", {
            "team": str(self.data["team"].id), "section": "client", "label": "X", "answer_type": "note_5",
        }, format="json")
        self.assertEqual(r.status_code, 403)

    def test_team_admin_creates_and_archives(self):
        self.client.force_authenticate(self.data["team_admin"])
        r = self.client.post("/api/v1/evaluations/catalog/", {
            "team": str(self.data["team"].id), "section": "client", "label": "Accueil", "answer_type": "note_5",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        r = self.client.post(f"/api/v1/evaluations/catalog/{r.data['id']}/archive/")
        self.assertEqual(r.data["status"], "archived")

    def test_invalid_definition_returns_400(self):
        self.client.force_authenticate(self.data["team_admin"])
        r = self.client.post("/api/v1/evaluations/catalog/", {
            "team": str(self.data["team"].id), "section": "client", "label": "X",
            "answer_type": "choix_unique", "options": ["seule"],
        }, format="json")
        self.assertEqual(r.status_code, 400)
```

- [ ] **Étape 7 : lancer les tests** — `.venv/Scripts/python.exe manage.py test apps.evaluations` → PASS.
- [ ] **Étape 8 : commit** (si autorisé) — `feat(evaluations): manage the generic question catalog`

---

### Tâche 4 : fiches, questions propres, cycle de vie et lien public (côté gestion)

**Fichiers :**
- Créer : `apps/evaluations/services.py`, `apps/evaluations/tests/test_sheets.py`
- Modifier : `serializers.py`, `views.py`, `urls.py`, `apps/projects/services.py` (flags de permission), `apps/evaluations/tests/test_api.py`

**Interfaces produites :**
- `services.can_manage_sheets(user, project) -> bool` (chef de projet)
- `services.can_view_sheets(user, project) -> bool` (chef de projet, admin du groupe du projet, admin d'organisation)
- `services.list_sheets(*, actor, project)`, `services.create_sheet(*, actor, project, title, client_intro="")`
- `services.update_sheet(*, actor, sheet, title=None, client_intro=None)`
- `services.add_sheet_question(*, actor, sheet, **definition)`, `services.update_sheet_question(*, actor, question, **changes)`, `services.archive_sheet_question(*, actor, question)`, `services.move_sheet_question(*, actor, question, direction)`
- `services.open_sheet`, `close_sheet`, `reopen_sheet`, `archive_sheet`, `rotate_sheet_link` (tous `(*, actor, sheet) -> EvaluationSheet`)
- `services.sheet_questions(sheet, section=None) -> QuerySet[SheetQuestion]` (actives, triées)
- `services.public_path(sheet) -> str | None` : `"/evaluation/<token>"` si la fiche est ouverte
- Flags projet : `permissions.can_manage_evaluations`, `permissions.can_view_evaluations`
- Endpoints : `GET/POST /api/v1/evaluations/sheets/?project=<uuid>`, `GET/PATCH /sheets/{id}/`, `POST /sheets/{id}/questions/`, `PATCH /sheets/{id}/questions/{question_id}/`, `POST /sheets/{id}/questions/{question_id}/archive/`, `POST /sheets/{id}/questions/{question_id}/move/`, `POST /sheets/{id}/open|close|reopen|archive|rotate-link/`

- [ ] **Étape 1 : tests de service qui échouent** (`test_sheets.py`)

```python
from django.test import TestCase

from apps.accounts.models import User
from apps.evaluations import catalog, services
from apps.evaluations.definitions import EvaluationPermissionError, EvaluationValidationError
from apps.evaluations.models import SheetQuestion

from .factories import make_team_project


class SheetLifecycleTests(TestCase):
    def setUp(self):
        self.data = make_team_project()
        self.manager = self.data["manager"]
        self.sheet = services.create_sheet(actor=self.manager, project=self.data["project"], title="Bilan v1")

    def test_creation_copies_the_catalog_with_conditions(self):
        copies = SheetQuestion.all_objects.filter(sheet=self.sheet)
        self.assertEqual(copies.count(), catalog.get_catalog(self.data["team"]).count())
        presta = copies.get(label="Nom du prestataire")
        self.assertEqual(presta.condition_on.sheet_id, self.sheet.id)
        self.assertEqual(presta.condition_on.label, "Le projet a été réalisé")

    def test_catalog_changes_do_not_alter_existing_sheets(self):
        question = catalog.get_catalog(self.data["team"], section="client").first()
        catalog.update_catalog_question(actor=self.data["team_admin"], question=question, label="Nouveau libellé")
        self.assertFalse(services.sheet_questions(self.sheet).filter(label="Nouveau libellé").exists())

    def test_only_project_manager_creates(self):
        with self.assertRaises(EvaluationPermissionError):
            services.create_sheet(actor=self.data["member"], project=self.data["project"], title="X")

    def test_team_admin_can_view_but_not_manage(self):
        self.assertTrue(services.can_view_sheets(self.data["team_admin"], self.data["project"]))
        self.assertFalse(services.can_manage_sheets(self.data["team_admin"], self.data["project"]))
        self.assertFalse(services.can_view_sheets(self.data["member"], self.data["project"]))

    def test_custom_question_in_draft(self):
        question = services.add_sheet_question(
            actor=self.manager, sheet=self.sheet, section="client", label="Spécifique ?", answer_type="oui_non"
        )
        self.assertIsNone(question.catalog_question)

    def test_generic_question_is_locked(self):
        generic = services.sheet_questions(self.sheet).exclude(catalog_question=None).first()
        with self.assertRaises(EvaluationValidationError):
            services.update_sheet_question(actor=self.manager, question=generic, label="Autre")
        with self.assertRaises(EvaluationValidationError):
            services.archive_sheet_question(actor=self.manager, question=generic)

    def test_custom_question_can_depend_on_a_generic_one(self):
        root = services.sheet_questions(self.sheet).get(label="Le projet a été réalisé")
        question = services.add_sheet_question(
            actor=self.manager, sheet=self.sheet, section="interne", label="Contrat signé ?",
            answer_type="oui_non", condition_on=root.id, condition_values=["Par un prestataire"],
        )
        self.assertEqual(question.condition_on, root)

    def test_open_generates_token_and_freezes_questions(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        self.assertEqual(self.sheet.status, "ouverte")
        self.assertTrue(self.sheet.public_token)
        with self.assertRaises(EvaluationValidationError):
            services.add_sheet_question(
                actor=self.manager, sheet=self.sheet, section="client", label="Tard", answer_type="oui_non"
            )

    def test_open_requires_a_client_question(self):
        empty_scope = make_team_project("Vide")
        for question in catalog.get_catalog(empty_scope["team"], section="client"):
            question.status = "archived"
            question.save()
        sheet = services.create_sheet(actor=empty_scope["manager"], project=empty_scope["project"], title="X")
        with self.assertRaises(EvaluationValidationError):
            services.open_sheet(actor=empty_scope["manager"], sheet=sheet)

    def test_close_reopen_archive(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        token = self.sheet.public_token
        services.close_sheet(actor=self.manager, sheet=self.sheet)
        self.assertEqual(self.sheet.status, "close")
        services.reopen_sheet(actor=self.manager, sheet=self.sheet)
        self.assertEqual(self.sheet.public_token, token)
        services.close_sheet(actor=self.manager, sheet=self.sheet)
        services.archive_sheet(actor=self.manager, sheet=self.sheet)
        self.assertEqual(self.sheet.status, "archivee")
        self.assertIsNone(services.public_path(self.sheet))

    def test_rotate_link_changes_token(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        token = self.sheet.public_token
        services.rotate_sheet_link(actor=self.manager, sheet=self.sheet)
        self.assertNotEqual(self.sheet.public_token, token)

    def test_project_permissions_expose_flags(self):
        from apps.projects.services import get_project_permissions
        perms = get_project_permissions(self.manager, self.data["project"])
        self.assertTrue(perms["can_manage_evaluations"])
        self.assertTrue(perms["can_view_evaluations"])
        self.assertFalse(get_project_permissions(self.data["member"], self.data["project"])["can_view_evaluations"])
```

> Vérifier le nom exact de la fonction qui construit le dict de permissions dans `apps/projects/services.py` (autour de la ligne 330, celle qui renvoie `"can_view_history"`). Si elle ne s'appelle pas `get_project_permissions`, adapter l'import du test.

- [ ] **Étape 2 : lancer et constater l'échec.**

- [ ] **Étape 3 : `services.py`**

```python
import secrets

from django.db import transaction
from django.utils import timezone

from apps.accounts.services import can_manage_team, is_organisation_admin
from apps.common.audit import record_event
from apps.projects.services import is_project_manager

from .catalog import catalog_scope, get_catalog, swap_position
from .definitions import (
    EvaluationPermissionError,
    EvaluationValidationError,
    clean_definition,
    definition_of,
    ensure_no_dependents,
)
from .models import EvaluationSheet, SheetQuestion

_EDITABLE = {"label", "help_text", "options", "required", "condition_on", "condition_values"}


# --- Droits --------------------------------------------------------------

def can_manage_sheets(user, project):
    return is_project_manager(user, project)


def can_view_sheets(user, project):
    if is_project_manager(user, project):
        return True
    if project.team_id and can_manage_team(user, project.team):
        return True
    return is_organisation_admin(user, project.organisation)


def _ensure_manage(actor, project):
    if not can_manage_sheets(actor, project):
        raise EvaluationPermissionError("Réservé aux chefs de projet.")


def _ensure_view(actor, project):
    if not can_view_sheets(actor, project):
        raise EvaluationPermissionError("Réservé aux chefs de projet et aux administrateurs.")


# --- Lecture -------------------------------------------------------------

def sheet_questions(sheet, section=None):
    qs = SheetQuestion.all_objects.filter(sheet=sheet, status="active")
    if section is not None:
        qs = qs.filter(section=section)
    return qs.order_by("section", "position", "created_at")


def public_path(sheet):
    if sheet.status == "ouverte" and sheet.public_token:
        return f"/evaluation/{sheet.public_token}"
    return None


def list_sheets(*, actor, project):
    _ensure_view(actor, project)
    return EvaluationSheet.all_objects.filter(project=project).order_by("-created_at")


def get_sheet(*, actor, sheet):
    _ensure_view(actor, sheet.project)
    return sheet


# --- Création / édition --------------------------------------------------

@transaction.atomic
def create_sheet(*, actor, project, title, client_intro=""):
    _ensure_manage(actor, project)
    title = (title or "").strip()
    if not title:
        raise EvaluationValidationError("Le titre de la fiche ne peut pas être vide.")
    sheet = EvaluationSheet.all_objects.create(
        project=project, title=title[:200], client_intro=(client_intro or "").strip(), created_by=actor
    )
    catalog_questions = list(get_catalog(catalog_scope(project)))
    copies = {}
    for position, source in enumerate(catalog_questions):
        copies[source.pk] = SheetQuestion.all_objects.create(
            sheet=sheet, catalog_question=source, section=source.section, label=source.label,
            help_text=source.help_text, answer_type=source.answer_type, options=list(source.options),
            required=source.required, position=position, condition_values=list(source.condition_values),
        )
    for source in catalog_questions:
        if source.condition_on_id:
            copy = copies[source.pk]
            copy.condition_on = copies.get(source.condition_on_id)
            if copy.condition_on is None:
                copy.condition_values = []
            copy.save(update_fields=["condition_on", "condition_values"])
    record_event(sheet, actor=actor, verb="created", description=f"Fiche d'évaluation créée : {sheet.title}",
                 project=project)
    return sheet


def update_sheet(*, actor, sheet, title=None, client_intro=None):
    _ensure_manage(actor, sheet.project)
    if sheet.status == "archivee":
        raise EvaluationValidationError("Cette fiche est archivée.")
    if title is not None:
        title = title.strip()
        if not title:
            raise EvaluationValidationError("Le titre de la fiche ne peut pas être vide.")
        sheet.title = title[:200]
    if client_intro is not None:
        sheet.client_intro = client_intro.strip()
    sheet.save()
    return sheet


def _ensure_draft(sheet):
    if sheet.status != "brouillon":
        raise EvaluationValidationError("Les questions ne se modifient plus une fois la fiche ouverte.")


def _ensure_custom(question):
    if question.catalog_question_id:
        raise EvaluationValidationError(
            "Question générique : modifiez-la dans le catalogue du groupe, elle s'appliquera aux prochaines fiches."
        )


def add_sheet_question(*, actor, sheet, section, label, answer_type, help_text="", options=None,
                       required=False, condition_on=None, condition_values=None):
    _ensure_manage(actor, sheet.project)
    _ensure_draft(sheet)
    fields = clean_definition(
        siblings=list(sheet_questions(sheet)), current=None, section=section, label=label, help_text=help_text,
        answer_type=answer_type, options=options, required=required, condition_on=condition_on,
        condition_values=condition_values,
    )
    last = SheetQuestion.all_objects.filter(sheet=sheet, section=section).order_by("-position").first()
    return SheetQuestion.all_objects.create(sheet=sheet, position=(last.position + 1) if last else 0, **fields)


def update_sheet_question(*, actor, question, **changes):
    sheet = question.sheet
    _ensure_manage(actor, sheet.project)
    _ensure_draft(sheet)
    _ensure_custom(question)
    # Contrairement au catalogue, le type reste modifiable : une question
    # propre à une fiche en brouillon n'a encore aucune réponse.
    merged = definition_of(question)
    merged.update({key: value for key, value in changes.items() if key in _EDITABLE | {"answer_type"}})
    fields = clean_definition(siblings=list(sheet_questions(sheet)), current=question, **merged)
    for key, value in fields.items():
        setattr(question, key, value)
    question.save()
    return question


def archive_sheet_question(*, actor, question):
    _ensure_manage(actor, question.sheet.project)
    _ensure_draft(question.sheet)
    _ensure_custom(question)
    ensure_no_dependents(question)
    question.status = "archived"
    question.save(update_fields=["status", "updated_at"])
    return question


def move_sheet_question(*, actor, question, direction):
    _ensure_manage(actor, question.sheet.project)
    _ensure_draft(question.sheet)
    swap_position(list(sheet_questions(question.sheet, section=question.section)), question, direction)
    return question


# --- Cycle de vie --------------------------------------------------------

def _transition(sheet, allowed_from, target, actor, message):
    _ensure_manage(actor, sheet.project)
    if sheet.status not in allowed_from:
        raise EvaluationValidationError(message)
    sheet.status = target
    return sheet


def open_sheet(*, actor, sheet):
    _transition(sheet, {"brouillon"}, "ouverte", actor, "Seule une fiche en brouillon s'ouvre.")
    if not sheet_questions(sheet, section="client").exists():
        raise EvaluationValidationError("Ajoutez au moins une question client avant d'ouvrir la fiche.")
    sheet.public_token = sheet.public_token or secrets.token_urlsafe(24)
    sheet.opened_at = timezone.now()
    sheet.save()
    record_event(sheet, actor=actor, verb="sent", description=f"Fiche d'évaluation ouverte : {sheet.title}",
                 project=sheet.project)
    return sheet


def close_sheet(*, actor, sheet):
    _transition(sheet, {"ouverte"}, "close", actor, "Seule une fiche ouverte se clôt.")
    sheet.closed_at = timezone.now()
    sheet.save()
    return sheet


def reopen_sheet(*, actor, sheet):
    _transition(sheet, {"close"}, "ouverte", actor, "Seule une fiche close se rouvre.")
    sheet.closed_at = None
    sheet.save()
    return sheet


def archive_sheet(*, actor, sheet):
    _transition(sheet, {"brouillon", "close"}, "archivee", actor, "Clôturez la fiche avant de l'archiver.")
    sheet.save()
    record_event(sheet, actor=actor, verb="archived", description=f"Fiche d'évaluation archivée : {sheet.title}",
                 project=sheet.project)
    return sheet


def rotate_sheet_link(*, actor, sheet):
    _ensure_manage(actor, sheet.project)
    if sheet.status != "ouverte":
        raise EvaluationValidationError("Le lien ne se régénère que sur une fiche ouverte.")
    sheet.public_token = secrets.token_urlsafe(24)
    sheet.save(update_fields=["public_token", "updated_at"])
    return sheet
```

- [ ] **Étape 4 : flags projet** — dans `apps/projects/services.py`, dans le dict qui contient `"can_view_history"` :

```python
        # Fiches d'évaluation (session du 2026-11-13) : création/gestion par le
        # chef de projet ; consultation aussi par les admins du groupe et de
        # l'organisation. Logique dupliquée à dessein (2 lignes) plutôt
        # qu'importée : `projects` ne doit pas dépendre d'`evaluations`.
        "can_manage_evaluations": is_project_manager(user, project),
        "can_view_evaluations": is_project_manager(user, project)
        or bool(project.team_id and can_manage_team(user, project.team))
        or is_organisation_admin(user, project.organisation),
```

Importer `can_manage_team` / `is_organisation_admin` depuis `apps.accounts.services` s'ils ne le sont pas déjà. Lancer `apps/projects/tests/test_list_performance.py` : `can_manage_team` peut ajouter une requête par projet en liste. Si le budget de requêtes casse, évaluer `can_view_evaluations` paresseusement (seulement en détail, via `self.action != "list"` dans le serializer) ou utiliser le cache `prefetched_team_memberships`. **Ne pas relever le budget du test.**

- [ ] **Étape 5 : serializers / vues / URLs**

Ajouter à `serializers.py` :

```python
from . import services
from .models import EvaluationSheet, SheetQuestion


class SheetCreateSerializer(serializers.Serializer):
    project = serializers.UUIDField()
    title = serializers.CharField(max_length=200)
    client_intro = serializers.CharField(required=False, allow_blank=True, default="")


class SheetUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    client_intro = serializers.CharField(required=False, allow_blank=True)


class SheetQuestionSerializer(serializers.ModelSerializer):
    is_generic = serializers.SerializerMethodField()

    class Meta:
        model = SheetQuestion
        fields = QUESTION_FIELDS + ["is_generic"]

    def get_is_generic(self, obj):
        return obj.catalog_question_id is not None


class SheetSummarySerializer(serializers.ModelSerializer):
    response_count = serializers.IntegerField(read_only=True)
    public_path = serializers.SerializerMethodField()

    class Meta:
        model = EvaluationSheet
        fields = ["id", "project", "title", "client_intro", "status", "created_at", "opened_at", "closed_at",
                  "response_count", "public_path"]

    def get_public_path(self, obj):
        return services.public_path(obj)
```

Vue `SheetViewSet(EvaluationErrorsMixin, viewsets.GenericViewSet)` :
- `queryset = EvaluationSheet.all_objects.select_related("project")`
- `list` : `?project=<uuid>` obligatoire, puis `services.list_sheets(...)` annoté de `response_count=Count("client_responses", filter=Q(client_responses__status="retenue"))`
- `create` : `SheetCreateSerializer`, projet via `get_object_or_404(Project.all_objects, pk=...)`, renvoie le détail (201)
- `retrieve` : `services.get_sheet`, puis `_detail(request, sheet)` = résumé + `questions` (`SheetQuestionSerializer(services.sheet_questions(sheet), many=True)`) + `internal` (tâche 6) + `permissions: {"can_manage": services.can_manage_sheets(request.user, sheet.project)}`
- `partial_update` : `SheetUpdateSerializer` → `services.update_sheet`
- `@action(detail=True, methods=["post"], url_path="questions")` → `add_sheet_question` (`QuestionDefinitionInputSerializer`)
- `@action(detail=True, methods=["patch"], url_path=r"questions/(?P<question_id>[^/.]+)")` → `update_sheet_question` (`QuestionDefinitionUpdateSerializer`, avec `answer_type` accepté)
- `@action(detail=True, methods=["post"], url_path=r"questions/(?P<question_id>[^/.]+)/archive")` et `.../move` (`MoveSerializer`)
- `open`, `close`, `reopen`, `archive`, `rotate-link` (`url_path="rotate-link"`) : `@action(detail=True, methods=["post"])`, réponse `_detail`

Question d'une fiche : `get_object_or_404(SheetQuestion.all_objects, pk=question_id, sheet=sheet)`.

`urls.py` : `router.register("sheets", SheetViewSet, basename="evaluation-sheet")`.

- [ ] **Étape 6 : tests d'API** (à ajouter) : création par le chef de projet (201, questions présentes) ; membre → 403 en liste ; admin du groupe → 200 en lecture, 403 en création ; `open` → `public_path` commence par `/evaluation/`.

```python
class SheetApiTests(APITestCase):
    def setUp(self):
        self.data = make_team_project()

    def _create(self):
        self.client.force_authenticate(self.data["manager"])
        return self.client.post("/api/v1/evaluations/sheets/", {
            "project": str(self.data["project"].id), "title": "Bilan",
        }, format="json")

    def test_manager_creates_and_opens(self):
        r = self._create()
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["questions"])
        r = self.client.post(f"/api/v1/evaluations/sheets/{r.data['id']}/open/")
        self.assertTrue(r.data["public_path"].startswith("/evaluation/"))

    def test_member_cannot_list(self):
        self.client.force_authenticate(self.data["member"])
        r = self.client.get(f"/api/v1/evaluations/sheets/?project={self.data['project'].id}")
        self.assertEqual(r.status_code, 403)

    def test_team_admin_reads_but_cannot_create(self):
        sheet_id = self._create().data["id"]
        self.client.force_authenticate(self.data["team_admin"])
        self.assertEqual(self.client.get(f"/api/v1/evaluations/sheets/{sheet_id}/").status_code, 200)
        r = self.client.post("/api/v1/evaluations/sheets/", {
            "project": str(self.data["project"].id), "title": "X",
        }, format="json")
        self.assertEqual(r.status_code, 403)
```

- [ ] **Étape 7 : lancer** `.venv/Scripts/python.exe manage.py test apps.evaluations apps.projects` → PASS.
- [ ] **Étape 8 : commit** (si autorisé) — `feat(evaluations): create evaluation sheets with frozen questions`

---

### Tâche 5 : formulaire public (lecture + envoi)

**Fichiers :**
- Créer : `apps/evaluations/throttles.py`, `apps/evaluations/tests/test_public.py`
- Modifier : `services.py`, `serializers.py`, `views.py`, `urls.py`, `config/settings/base.py` (`DEFAULT_THROTTLE_RATES` : `"evaluation_submit": "10/hour"`)

**Interfaces produites :**
- `services.get_public_sheet(token) -> dict | None` (`None` = inconnu ou archivé ; `{"closed": True, ...}` si clos ou brouillon)
- `services.submit_client_response(*, token, respondent_name, answers) -> ClientResponse`
- Endpoints `AllowAny`, sans authentification : `GET /api/v1/evaluations/public/<token>/`, `POST /api/v1/evaluations/public/<token>/responses/` (`{"respondent_name", "answers": {question_id: valeur}}`)

- [ ] **Étape 1 : tests qui échouent**

```python
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.evaluations import services
from apps.evaluations.models import Answer, ClientResponse

from .factories import make_team_project


class PublicEvaluationTests(APITestCase):
    def setUp(self):
        cache.clear()  # throttle anonyme partagé entre tests
        self.data = make_team_project()
        self.sheet = services.create_sheet(actor=self.data["manager"], project=self.data["project"], title="Bilan")
        services.open_sheet(actor=self.data["manager"], sheet=self.sheet)
        self.url = f"/api/v1/evaluations/public/{self.sheet.public_token}/"
        self.client_questions = list(services.sheet_questions(self.sheet, section="client"))

    def _valid_answers(self):
        values = {"note_5": 4, "nps_10": 9, "oui_non": "oui", "texte_long": "Très bien"}
        return {str(q.id): values[q.answer_type] for q in self.client_questions}

    def test_get_exposes_only_client_questions(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual({q["id"] for q in r.data["questions"]}, {str(q.id) for q in self.client_questions})
        self.assertNotIn("internal", r.data)
        self.assertEqual(r.data["project_name"], self.data["project"].name)

    def test_unknown_token_is_404(self):
        self.assertEqual(self.client.get("/api/v1/evaluations/public/inconnu/").status_code, 404)

    def test_submit_stores_answers(self):
        r = self.client.post(f"{self.url}responses/", {
            "respondent_name": "Mme Martin", "answers": self._valid_answers(),
        }, format="json")
        self.assertEqual(r.status_code, 201)
        response = ClientResponse.all_objects.get(sheet=self.sheet)
        self.assertEqual(response.respondent_name, "Mme Martin")
        self.assertEqual(Answer.objects.filter(client_response=response).count(), len(self.client_questions))

    def test_name_is_required(self):
        r = self.client.post(f"{self.url}responses/", {"respondent_name": " ", "answers": self._valid_answers()},
                             format="json")
        self.assertEqual(r.status_code, 400)

    def test_required_answer_is_enforced(self):
        answers = self._valid_answers()
        answers.pop(str(self.client_questions[0].id))
        r = self.client.post(f"{self.url}responses/", {"respondent_name": "A", "answers": answers}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["question"], str(self.client_questions[0].id))

    def test_internal_question_cannot_be_answered_publicly(self):
        internal = services.sheet_questions(self.sheet, section="interne").first()
        answers = {**self._valid_answers(), str(internal.id): "En interne"}
        r = self.client.post(f"{self.url}responses/", {"respondent_name": "A", "answers": answers}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_closed_sheet_refuses_answers(self):
        services.close_sheet(actor=self.data["manager"], sheet=self.sheet)
        self.assertTrue(self.client.get(self.url).data["closed"])
        r = self.client.post(f"{self.url}responses/", {"respondent_name": "A", "answers": self._valid_answers()},
                             format="json")
        self.assertEqual(r.status_code, 410)

    def test_rotated_token_invalidates_old_link(self):
        services.rotate_sheet_link(actor=self.data["manager"], sheet=self.sheet)
        self.assertEqual(self.client.get(self.url).status_code, 404)
```

- [ ] **Étape 2 : lancer et constater l'échec.**

- [ ] **Étape 3 : implémenter**

`services.py` (à la suite) :

```python
from .answers import AnswerError, clean_answers
from .models import Answer, ClientResponse


class SheetClosedError(Exception):
    pass


def _public_question(question):
    return {
        "id": str(question.id), "label": question.label, "help_text": question.help_text,
        "answer_type": question.answer_type, "options": question.options, "required": question.required,
        "condition_on": str(question.condition_on_id) if question.condition_on_id else None,
        "condition_values": question.condition_values,
    }


def _sheet_by_token(token):
    return (
        EvaluationSheet.all_objects.select_related("project")
        .filter(public_token=token).exclude(status="archivee").first()
    )


def get_public_sheet(token):
    """Seul contenu exposé sans compte : titre, intro, nom du projet, questions client."""
    sheet = _sheet_by_token(token)
    if sheet is None:
        return None
    if sheet.status != "ouverte":
        return {"closed": True, "title": sheet.title, "project_name": sheet.project.name}
    return {
        "closed": False,
        "title": sheet.title,
        "client_intro": sheet.client_intro,
        "project_name": sheet.project.name,
        "questions": [_public_question(q) for q in sheet_questions(sheet, section="client")],
    }


@transaction.atomic
def submit_client_response(*, token, respondent_name, answers):
    sheet = _sheet_by_token(token)
    if sheet is None:
        return None
    if sheet.status != "ouverte":
        raise SheetClosedError("Ce formulaire n'accepte plus de réponses.")
    name = (respondent_name or "").strip()
    if not name:
        raise AnswerError(None, "Indiquez votre nom.")
    if len(name) > 150:
        raise AnswerError(None, "Le nom ne peut pas dépasser 150 caractères.")
    questions = list(sheet_questions(sheet, section="client"))
    cleaned = clean_answers(questions, answers, enforce_required=True)
    response = ClientResponse.all_objects.create(sheet=sheet, respondent_name=name)
    Answer.objects.bulk_create(
        Answer(question=question, client_response=response, value=cleaned[str(question.id)])
        for question in questions
    )
    return response
```

`throttles.py` :

```python
from rest_framework.throttling import ScopedRateThrottle


class EvaluationSubmitThrottle(ScopedRateThrottle):
    """10 réponses / heure / IP sur l'envoi public (réglage `evaluation_submit`)."""

    scope_attr = "throttle_scope"
```

`serializers.py` :

```python
class PublicSubmitSerializer(serializers.Serializer):
    respondent_name = serializers.CharField(max_length=150, allow_blank=True)
    answers = serializers.DictField(child=serializers.JSONField(), required=False, default=dict)
```

`views.py` :

```python
from django.http import Http404
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .serializers import PublicSubmitSerializer
from .throttles import EvaluationSubmitThrottle


class PublicEvaluationView(EvaluationErrorsMixin, APIView):
    """Formulaire client public — 2ᵉ exception au garde-fou « connexion
    obligatoire » (CLAUDE.md > Stack technique > Auth). N'expose que les
    questions client d'une fiche ouverte."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        data = services.get_public_sheet(token)
        if data is None:
            raise Http404
        return Response(data)


class PublicEvaluationSubmitView(EvaluationErrorsMixin, APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, EvaluationSubmitThrottle]
    throttle_scope = "evaluation_submit"

    def post(self, request, token):
        serializer = PublicSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            response = services.submit_client_response(token=token, **serializer.validated_data)
        except services.SheetClosedError as exc:
            return Response({"detail": str(exc)}, status=410)
        if response is None:
            raise Http404
        return Response({"detail": "Merci, votre réponse a bien été enregistrée."}, status=201)
```

`urls.py` :

```python
urlpatterns = [
    path("public/<str:token>/", PublicEvaluationView.as_view(), name="evaluation-public"),
    path("public/<str:token>/responses/", PublicEvaluationSubmitView.as_view(), name="evaluation-public-submit"),
    *router.urls,
]
```

- [ ] **Étape 4 : test du throttle** (dans `test_public.py`) : 10 envois valides puis un 11ᵉ → 429. Utiliser `@override_settings` sur `REST_FRAMEWORK` seulement si le réglage n'est pas pris (il est lu à l'import par `ScopedRateThrottle.THROTTLE_RATES`) : dans ce cas, patcher `EvaluationSubmitThrottle.THROTTLE_RATES = {"evaluation_submit": "2/hour"}` avec `mock.patch.object` et tester le 3ᵉ envoi.

- [ ] **Étape 5 : lancer** → PASS. **Étape 6 : commit** (si autorisé) — `feat(evaluations): public client form with throttled submission`

---

### Tâche 6 : partie chef de projet, résultats, réponses, export CSV

**Fichiers :**
- Créer : `apps/evaluations/results.py`, `apps/evaluations/tests/test_results.py`
- Modifier : `services.py`, `serializers.py`, `views.py`

**Interfaces produites :**
- `services.save_internal_evaluation(*, actor, sheet, answers) -> InternalEvaluation`
- `services.internal_answers(sheet) -> dict[str, object]` (`{}` si rien de saisi)
- `services.discard_response(*, actor, response)`, `services.restore_response(*, actor, response)`
- `services.list_responses(*, actor, sheet) -> list[dict]` : `{"id", "respondent_name", "created_at", "status", "answers": {question_id: valeur}}`, toutes réponses (retenues et écartées)
- `results.summarize(question, values: list) -> dict`
- `results.sheet_results(sheet) -> dict` : `{"response_count", "client": [{"question", "summary"}], "interne": [{"question", "value"}]}`
- `results.export_csv_rows(sheet) -> (header: list[str], rows: list[list[str]])`
- `results.format_value(question, value) -> str`
- Endpoints : `PUT /sheets/{id}/internal/` (`{"answers": {...}}`), `GET /sheets/{id}/results/`, `GET /sheets/{id}/responses/`, `POST /sheets/{id}/responses/{response_id}/discard|restore/`, `GET /sheets/{id}/export/` (CSV)

Format de `summarize` selon le type :
- `note_5` : `{"kind": "note", "count", "average": float|None, "distribution": {"1": n, …, "5": n}}`
- `nps_10` : `{"kind": "nps", "count", "score": int|None, "promoters", "passives", "detractors", "distribution": {"0": n … "10": n}}` avec score = round(100 × (promoteurs − détracteurs) / count)
- `oui_non` : `{"kind": "yes_no", "count", "yes", "no", "yes_rate": float|None}`
- `choix_unique` / `choix_multiple` : `{"kind": "choices", "count", "counts": {option: n}}` (pour un choix multiple, `count` = nombre de répondants)
- texte : `{"kind": "text", "count", "values": [str]}`

- [ ] **Étape 1 : tests qui échouent** (`test_results.py`)

```python
from types import SimpleNamespace
from django.test import SimpleTestCase, TestCase

from apps.evaluations import results, services
from apps.evaluations.definitions import EvaluationPermissionError, EvaluationValidationError

from .factories import make_team_project


def q(answer_type, options=()):
    return SimpleNamespace(id="x", label="Q", answer_type=answer_type, options=list(options))


class SummarizeTests(SimpleTestCase):
    def test_note(self):
        s = results.summarize(q("note_5"), [5, 4, 3])
        self.assertEqual(s["average"], 4.0)
        self.assertEqual(s["distribution"]["5"], 1)

    def test_nps(self):
        s = results.summarize(q("nps_10"), [10, 9, 8, 3])
        self.assertEqual((s["promoters"], s["passives"], s["detractors"]), (2, 1, 1))
        self.assertEqual(s["score"], 25)

    def test_yes_no(self):
        s = results.summarize(q("oui_non"), ["oui", "oui", "non"])
        self.assertAlmostEqual(s["yes_rate"], 2 / 3)

    def test_multiple_choice(self):
        s = results.summarize(q("choix_multiple", ["A", "B"]), [["A", "B"], ["A"]])
        self.assertEqual(s["counts"], {"A": 2, "B": 1})
        self.assertEqual(s["count"], 2)

    def test_empty(self):
        self.assertIsNone(results.summarize(q("note_5"), [])["average"])

    def test_format_value(self):
        self.assertEqual(results.format_value(q("choix_multiple", ["A", "B"]), ["A", "B"]), "A | B")
        self.assertEqual(results.format_value(q("note_5"), None), "")


class InternalAndResultsTests(TestCase):
    def setUp(self):
        self.data = make_team_project()
        self.manager = self.data["manager"]
        self.sheet = services.create_sheet(actor=self.manager, project=self.data["project"], title="Bilan")
        self.realisation = services.sheet_questions(self.sheet).get(label="Le projet a été réalisé")
        self.presta = services.sheet_questions(self.sheet).get(label="Nom du prestataire")

    def test_internal_requires_open_sheet(self):
        with self.assertRaises(EvaluationValidationError):
            services.save_internal_evaluation(actor=self.manager, sheet=self.sheet, answers={})

    def test_internal_save_is_partial_and_overwrites(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        services.save_internal_evaluation(actor=self.manager, sheet=self.sheet, answers={
            str(self.realisation.id): "Par un prestataire", str(self.presta.id): "ACME",
        })
        services.save_internal_evaluation(actor=self.manager, sheet=self.sheet, answers={
            str(self.realisation.id): "En interne", str(self.presta.id): "ACME",
        })
        answers = services.internal_answers(self.sheet)
        self.assertEqual(answers[str(self.realisation.id)], "En interne")
        self.assertIsNone(answers[str(self.presta.id)])  # masquée par la condition

    def test_only_managers_fill_internal_part(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        with self.assertRaises(EvaluationPermissionError):
            services.save_internal_evaluation(actor=self.data["team_admin"], sheet=self.sheet, answers={})

    def test_discarded_responses_leave_results_and_export(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        questions = list(services.sheet_questions(self.sheet, section="client"))
        values = {"note_5": 5, "nps_10": 10, "oui_non": "oui", "texte_long": "ok"}
        answers = {str(x.id): values[x.answer_type] for x in questions}
        kept = services.submit_client_response(token=self.sheet.public_token, respondent_name="A", answers=answers)
        spam = services.submit_client_response(token=self.sheet.public_token, respondent_name="B", answers=answers)
        services.discard_response(actor=self.manager, response=spam)
        self.assertEqual(results.sheet_results(self.sheet)["response_count"], 1)
        header, rows = results.export_csv_rows(self.sheet)
        self.assertEqual([row[1] for row in rows], ["A"])
        self.assertIn("Chef de projet — Le projet a été réalisé", header)
        services.restore_response(actor=self.manager, response=spam)
        self.assertEqual(results.sheet_results(self.sheet)["response_count"], 2)
        self.assertEqual(kept.status, "retenue")
```

- [ ] **Étape 2 : lancer et constater l'échec.**

- [ ] **Étape 3 : `services.py` (suite)**

```python
from .models import InternalEvaluation


def internal_answers(sheet):
    evaluation = InternalEvaluation.objects.filter(sheet=sheet).first()
    if evaluation is None:
        return {}
    return {str(a.question_id): a.value for a in evaluation.answers.all()}


@transaction.atomic
def save_internal_evaluation(*, actor, sheet, answers):
    """Partie chef de projet : une seule par fiche, enregistrement partiel
    (pas de champ obligatoire imposé), écrase la saisie précédente. Les
    réponses ne sont jamais supprimées : une réponse vidée garde `value=None`."""
    _ensure_manage(actor, sheet.project)
    if sheet.status not in ("ouverte", "close"):
        raise EvaluationValidationError("La partie chef de projet se remplit une fois la fiche ouverte.")
    questions = list(sheet_questions(sheet, section="interne"))
    cleaned = clean_answers(questions, answers, enforce_required=False)
    evaluation, _ = InternalEvaluation.objects.get_or_create(sheet=sheet, defaults={"updated_by": actor})
    evaluation.updated_by = actor
    evaluation.save()
    for question in questions:
        Answer.objects.update_or_create(
            internal_evaluation=evaluation, question=question, defaults={"value": cleaned[str(question.id)]}
        )
    return evaluation


def _set_response_status(actor, response, from_status, to_status, message):
    _ensure_manage(actor, response.sheet.project)
    if response.status != from_status:
        raise EvaluationValidationError(message)
    response.status = to_status
    response.save(update_fields=["status", "updated_at"])
    return response


def discard_response(*, actor, response):
    return _set_response_status(actor, response, "retenue", "ecartee", "Cette réponse est déjà écartée.")


def restore_response(*, actor, response):
    return _set_response_status(actor, response, "ecartee", "retenue", "Cette réponse n'est pas écartée.")


def list_responses(*, actor, sheet):
    _ensure_view(actor, sheet.project)
    responses = ClientResponse.all_objects.filter(sheet=sheet).prefetch_related("answers").order_by("-created_at")
    return [
        {
            "id": str(r.id), "respondent_name": r.respondent_name, "created_at": r.created_at,
            "status": r.status, "answers": {str(a.question_id): a.value for a in r.answers.all()},
        }
        for r in responses
    ]
```

- [ ] **Étape 4 : `results.py`**

```python
from collections import Counter

from .models import Answer, ClientResponse, InternalEvaluation, SheetQuestion

TEXT_TYPES = {"texte_court", "texte_long"}


def summarize(question, values):
    values = [v for v in values if v is not None]
    count = len(values)
    kind = question.answer_type
    if kind == "note_5":
        distribution = {str(n): values.count(n) for n in range(1, 6)}
        return {"kind": "note", "count": count, "average": round(sum(values) / count, 2) if count else None,
                "distribution": distribution}
    if kind == "nps_10":
        promoters = sum(1 for v in values if v >= 9)
        detractors = sum(1 for v in values if v <= 6)
        return {"kind": "nps", "count": count,
                "score": round(100 * (promoters - detractors) / count) if count else None,
                "promoters": promoters, "passives": count - promoters - detractors, "detractors": detractors,
                "distribution": {str(n): values.count(n) for n in range(0, 11)}}
    if kind == "oui_non":
        yes = values.count("oui")
        return {"kind": "yes_no", "count": count, "yes": yes, "no": count - yes,
                "yes_rate": yes / count if count else None}
    if kind in ("choix_unique", "choix_multiple"):
        counter = Counter()
        for value in values:
            counter.update(value if isinstance(value, list) else [value])
        return {"kind": "choices", "count": count, "counts": {o: counter.get(o, 0) for o in question.options}}
    return {"kind": "text", "count": count, "values": values}


def format_value(question, value):
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(value)
    return str(value)


def _active_questions(sheet, section):
    return list(SheetQuestion.all_objects.filter(sheet=sheet, section=section, status="active")
                .order_by("position", "created_at"))


def _kept_responses(sheet):
    return list(ClientResponse.all_objects.filter(sheet=sheet, status="retenue")
                .prefetch_related("answers").order_by("created_at"))


def sheet_results(sheet):
    responses = _kept_responses(sheet)
    by_question = {}
    for response in responses:
        for answer in response.answers.all():
            by_question.setdefault(answer.question_id, []).append(answer.value)
    internal = InternalEvaluation.objects.filter(sheet=sheet).first()
    internal_values = {a.question_id: a.value for a in internal.answers.all()} if internal else {}
    return {
        "response_count": len(responses),
        "client": [
            {"question_id": str(q.id), "summary": summarize(q, by_question.get(q.id, []))}
            for q in _active_questions(sheet, "client")
        ],
        "interne": [
            {"question_id": str(q.id), "value": internal_values.get(q.id)}
            for q in _active_questions(sheet, "interne")
        ],
    }


def export_csv_rows(sheet):
    client_questions = _active_questions(sheet, "client")
    internal_questions = _active_questions(sheet, "interne")
    internal = InternalEvaluation.objects.filter(sheet=sheet).first()
    internal_values = {a.question_id: a.value for a in internal.answers.all()} if internal else {}
    internal_cells = [format_value(q, internal_values.get(q.id)) for q in internal_questions]
    header = (["Date", "Répondant"] + [q.label for q in client_questions]
              + [f"Chef de projet — {q.label}" for q in internal_questions])
    rows = []
    for response in _kept_responses(sheet):
        values = {a.question_id: a.value for a in response.answers.all()}
        rows.append(
            [response.created_at.strftime("%Y-%m-%d %H:%M"), response.respondent_name]
            + [format_value(q, values.get(q.id)) for q in client_questions]
            + internal_cells
        )
    return header, rows
```

> Une fiche sans réponse client exporte quand même la partie chef de projet : si `rows` est vide et que la partie interne contient au moins une valeur, ajouter une ligne `["", "(aucune réponse client)", "", …] + internal_cells`. Ajouter le cas au test.

- [ ] **Étape 5 : vues**

Dans `SheetViewSet` :
- `@action(detail=True, methods=["put"]) internal` : `AnswersSerializer` (`answers = DictField(child=JSONField())`) → `save_internal_evaluation` → `_detail`
- `@action(detail=True, methods=["get"]) results` : `services.get_sheet` (contrôle de visibilité) puis `Response(results.sheet_results(sheet))`
- `@action(detail=True, methods=["get"]) responses` : `services.list_responses`
- `@action(detail=True, methods=["post"], url_path=r"responses/(?P<response_id>[^/.]+)/discard")` et `/restore`
- `@action(detail=True, methods=["get"]) export` : CSV avec BOM UTF-8 pour Excel

```python
    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        sheet = services.get_sheet(actor=request.user, sheet=self.get_object())
        header, rows = results.export_csv_rows(sheet)
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="evaluation-{slugify(sheet.title) or sheet.id}.csv"'
        response.write("﻿")  # BOM : accents corrects à l'ouverture dans Excel
        writer = csv.writer(response, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)
        return response
```

Le séparateur `;` correspond à l'ouverture directe dans un Excel français. Vérifier ce qu'utilise l'export d'historique (`apps/projects/views.py:385`, séparateur par défaut `,`) et **aligner les deux exports** si l'utilisateur le préfère : à signaler, ne pas modifier l'historique dans cette tâche.

Dans `_detail` : ajouter `"internal": services.internal_answers(sheet)` et `"internal_updated_at"` / `"internal_updated_by"` (nom affiché) si présents.

- [ ] **Étape 6 : tests d'API** : `PUT internal` par le chef de projet (200) et par l'admin du groupe (403) ; `GET export` → `Content-Type` commence par `text/csv`, première ligne contenant `Répondant` ; `GET results` par l'admin du groupe → 200.

- [ ] **Étape 7 : lancer** → PASS. **Étape 8 : commit** (si autorisé) — `feat(evaluations): internal evaluation, results and CSV export`

---

### Tâche 7 : statistiques (widgets du dashboard)

**Fichiers :**
- Modifier : `apps/evaluations/results.py`, `apps/dashboards/catalog.py`, `apps/dashboards/services.py`
- Test : `apps/evaluations/tests/test_results.py` (agrégation), `apps/dashboards/tests/` (ajouter un test dans le fichier qui couvre déjà les métriques par défaut ; le trouver avec `grep -rn "DEFAULT_METRICS" apps/dashboards/tests`)

**Interfaces produites :**
- `results.evaluation_insights(project_ids: list) -> {"generic_rows": list[dict], "response_count": int}`
- Métriques : `evaluation_generic_results` (table) et `evaluation_response_count` (stat_card), portées `{"projet", "global"}`, visibilité `"groupe"`

Chaque ligne de `generic_rows` correspond à **une question générique du catalogue**, qui appartient à un seul groupe (ou projet sans groupe). Les lignes ne mélangent donc jamais deux groupes :

```python
{"groupe": "Groupe Dev", "partie": "Client", "question": "...", "resultat": "4,2 / 5", "reponses": 12}
```

`resultat` : `note_5` → `"4,2 / 5"`, `nps_10` → `"NPS +35"`, `oui_non` → `"78 % oui"`. Seuls ces trois types sont agrégés. Côté client, `reponses` compte les réponses client retenues. Côté chef de projet, il compte les fiches (une évaluation par fiche). Les fiches archivées restent comptées : l'archivage range une fiche, il n'invalide pas ses résultats.

- [ ] **Étape 1 : test qui échoue**

```python
class EvaluationInsightsTests(TestCase):
    def test_rows_group_by_catalog_question_and_skip_custom(self):
        data = make_team_project()
        manager = data["manager"]
        for title in ("Vague 1", "Vague 2"):
            sheet = services.create_sheet(actor=manager, project=data["project"], title=title)
            services.add_sheet_question(actor=manager, sheet=sheet, section="client",
                                        label="Perso", answer_type="note_5")
            services.open_sheet(actor=manager, sheet=sheet)
            questions = list(services.sheet_questions(sheet, section="client"))
            values = {"note_5": 4, "nps_10": 10, "oui_non": "oui", "texte_long": "ok"}
            services.submit_client_response(token=sheet.public_token, respondent_name="A",
                                            answers={str(x.id): values[x.answer_type] for x in questions})
        insights = results.evaluation_insights([data["project"].id])
        satisfaction = next(r for r in insights["generic_rows"] if r["question"].startswith("Globalement"))
        self.assertEqual(satisfaction["reponses"], 2)
        self.assertEqual(satisfaction["resultat"], "4,0 / 5")
        self.assertFalse(any(r["question"] == "Perso" for r in insights["generic_rows"]))
        self.assertEqual(insights["response_count"], 2)
```

- [ ] **Étape 2 : implémenter**

```python
SECTION_LABELS = {"client": "Client", "interne": "Chef de projet"}


def _format_result(answer_type, values):
    summary = summarize(SimpleNamespace(answer_type=answer_type, options=[]), values)
    if summary["count"] == 0:
        return "—"
    if answer_type == "note_5":
        return f"{summary['average']:.1f} / 5".replace(".", ",")
    if answer_type == "nps_10":
        return f"NPS {summary['score']:+d}"
    return f"{round(summary['yes_rate'] * 100)} % oui"


def evaluation_insights(project_ids):
    answers = (
        Answer.objects.filter(
            question__sheet__project_id__in=project_ids,
            question__catalog_question__isnull=False,
            question__answer_type__in=("note_5", "nps_10", "oui_non"),
            value__isnull=False,
        )
        .exclude(client_response__status="ecartee")
        .select_related("question__catalog_question__team", "question__catalog_question__project")
    )
    grouped = {}
    for answer in answers:
        source = answer.question.catalog_question
        grouped.setdefault(source, []).append(answer.value)
    rows = [
        {
            "groupe": source.team.name if source.team_id else source.project.name,
            "partie": SECTION_LABELS[source.section],
            "question": source.label,
            "resultat": _format_result(source.answer_type, values),
            "reponses": len(values),
        }
        for source, values in grouped.items()
    ]
    rows.sort(key=lambda r: (r["groupe"], r["partie"], r["question"]))
    response_count = ClientResponse.all_objects.filter(
        sheet__project_id__in=project_ids, status="retenue"
    ).count()
    return {"generic_rows": rows, "response_count": response_count}
```

> `value__isnull=False` sur un `JSONField` : sous Postgres, un JSON `null` stocké n'est pas un SQL `NULL`. Utiliser `.exclude(value=None)` **et** vérifier en Python (`if answer.value is None: continue`) pour être correct sous SQLite comme sous Postgres. Importer `SimpleNamespace` depuis `types`.

`apps/dashboards/catalog.py`, dans `DEFAULT_METRICS` :

```python
    "evaluation_generic_results": {
        "label": "Évaluations — questions génériques",
        "loader": "evaluation_insights",
        "data_key": "generic_rows",
        "scope": {"projet", "global"},
        "visibility": "groupe",
        "render_hint": "table",
    },
    "evaluation_response_count": {
        "label": "Réponses clients reçues",
        "loader": "evaluation_insights",
        "data_key": "response_count",
        "scope": {"projet", "global"},
        "visibility": "groupe",
        "render_hint": "stat_card",
    },
```

`apps/dashboards/services.py` :

```python
from apps.evaluations.results import evaluation_insights


def _load_evaluation_insights(actor, project, project_ids):
    if project is not None:
        return evaluation_insights([project.id])
    return evaluation_insights(project_ids or [])
```

Ajouter `"evaluation_insights": _load_evaluation_insights` à `_LOADERS`. Dans `_normalize_default_data`, **avant** le cas `render_hint == "feed"` :

```python
    if render_hint == "table" and metric["loader"] == "evaluation_insights":
        return {"type": "table", "rows": raw[data_key]}
```

La portée « groupe » globale réutilise `_group_scope_project_ids` (projets dirigés, ou tous les projets de l'organisation pour un admin). C'est la règle commune à tous les widgets « groupe ». Un admin de groupe qui n'est pas chef de projet n'y voit donc pas ces widgets : c'est cohérent avec le reste du dashboard, à signaler à l'utilisateur.

- [ ] **Étape 3 : test dashboard** : un chef de projet pose `evaluation_generic_results` en portée globale ; `compute_widget_data` renvoie `{"type": "table", "rows": [...]}`. Un membre simple → `{"restricted": True}`.

- [ ] **Étape 4 : lancer** `.venv/Scripts/python.exe manage.py test apps.evaluations apps.dashboards` → PASS.
- [ ] **Étape 5 : commit** (si autorisé) — `feat(dashboards): evaluation widgets`

---

### Tâche 8 : Swagger

**Fichiers :**
- Modifier : `apps/evaluations/schema.py`, `apps/evaluations/views.py` (décorateurs), `apps/integrations/tests/test_openapi.py`

- [ ] **Étape 1 : écrire `schema.py`** sur le modèle de `apps/documentation/schema.py` (helpers `no_body`, `_OBJECT`, `extend_schema_view`) :
  - `catalog_schema` : `list` (paramètres `team`, `project`, `include_archived` déclarés via `OpenApiParameter`), `create` (`CatalogQuestionCreateSerializer`, 201), `partial_update` (`QuestionDefinitionUpdateSerializer`), `archive`/`restore` (`no_body`), `move` (`MoveSerializer`)
  - `sheet_schema` : `list` (`project`), `create`, `retrieve`, `partial_update`, `add_question`, `question_detail`, `question_archive` (`no_body`), `question_move`, `open`/`close`/`reopen`/`archive`/`rotate_link` (`no_body`), `internal` (`AnswersSerializer`), `results`, `responses`, `response_discard`/`response_restore` (`no_body`), `export` (`{(200, "text/csv"): OpenApiTypes.STR}`)
  - Vues publiques : `@extend_schema(responses=OpenApiTypes.OBJECT, auth=[])` sur `get` ; `@extend_schema(request=PublicSubmitSerializer, responses={201: OpenApiTypes.OBJECT, 410: OpenApiTypes.OBJECT}, auth=[])` sur `post`. Vérifier comment `PublicDocsView` obtient `security: [{}]` (test `test_public_documentation_requires_no_authentication`) et reproduire le même mécanisme.

- [ ] **Étape 2 : étendre `test_openapi.py`**
  - ajouter à `NO_BODY` : `("post", "evaluations/catalog/{id}/archive/")`, `("post", "evaluations/catalog/{id}/restore/")`, `("post", "evaluations/sheets/{id}/open/")`, `close`, `reopen`, `archive`, `rotate-link`, et les chemins `questions/{question_id}/archive/`, `responses/{response_id}/discard/`, `responses/{response_id}/restore/` (copier le gabarit exact affiché par le schéma)
  - ajouter au dict des corps attendus : `("post", "evaluations/sheets/")`: `{"project", "title", "client_intro"}`, `("post", "evaluations/public/{token}/responses/")`: `{"respondent_name", "answers"}`, `("put", "evaluations/sheets/{id}/internal/")`: `{"answers"}`, `("post", "evaluations/catalog/{id}/move/")`: `{"direction"}`
  - nouveau test :

```python
    def test_public_evaluation_requires_no_authentication(self):
        self.assertEqual(self._op("get", "evaluations/public/{token}/")["security"], [{}])
        self.assertEqual(self._op("post", "evaluations/public/{token}/responses/")["security"], [{}])
```

  - dans `test_anonymous_schema_only_describes_public_endpoints`, ajouter les deux chemins publics aux chemins attendus.

- [ ] **Étape 3 : lancer** `.venv/Scripts/python.exe manage.py test apps.integrations.tests.test_openapi apps.evaluations` → PASS, 0 erreur de génération (`test_generation_has_no_error`).
- [ ] **Étape 4 : commit** (si autorisé) — `docs(api): describe evaluation endpoints`

---

### Tâche 9 : types et client API frontend

**Fichiers :**
- Modifier : `frontend/src/types/watodo.ts`, `frontend/src/api/client.ts`
- Créer : `frontend/src/features/evaluations/visibility.ts`, `frontend/src/features/evaluations/answerFormat.ts`

- [ ] **Étape 1 : types** (`types/watodo.ts`) ; ajouter aussi `can_manage_evaluations` et `can_view_evaluations` à `ProjectPermissions`

```ts
export type EvaluationSection = "client" | "interne";
export type EvaluationAnswerType =
  | "note_5" | "nps_10" | "oui_non" | "choix_unique" | "choix_multiple" | "texte_court" | "texte_long";
export type EvaluationAnswerValue = number | string | string[] | null;

export interface EvaluationQuestion {
  id: string;
  section: EvaluationSection;
  label: string;
  help_text: string;
  answer_type: EvaluationAnswerType;
  options: string[];
  required: boolean;
  position: number;
  condition_on: string | null;
  condition_values: string[];
  status: "active" | "archived";
  is_generic?: boolean; // questions de fiche seulement
}

export interface EvaluationQuestionInput {
  section: EvaluationSection;
  label: string;
  help_text?: string;
  answer_type: EvaluationAnswerType;
  options?: string[];
  required?: boolean;
  condition_on?: string | null;
  condition_values?: string[];
}

export type EvaluationSheetStatus = "brouillon" | "ouverte" | "close" | "archivee";

export interface EvaluationSheetSummary {
  id: string;
  project: string;
  title: string;
  client_intro: string;
  status: EvaluationSheetStatus;
  created_at: string;
  opened_at: string | null;
  closed_at: string | null;
  response_count: number;
  public_path: string | null;
}

export interface EvaluationSheetDetail extends EvaluationSheetSummary {
  questions: EvaluationQuestion[];
  internal: Record<string, EvaluationAnswerValue>;
  internal_updated_at: string | null;
  internal_updated_by: string | null;
  permissions: { can_manage: boolean };
}

export type EvaluationSummary =
  | { kind: "note"; count: number; average: number | null; distribution: Record<string, number> }
  | { kind: "nps"; count: number; score: number | null; promoters: number; passives: number;
      detractors: number; distribution: Record<string, number> }
  | { kind: "yes_no"; count: number; yes: number; no: number; yes_rate: number | null }
  | { kind: "choices"; count: number; counts: Record<string, number> }
  | { kind: "text"; count: number; values: string[] };

export interface EvaluationResults {
  response_count: number;
  client: { question_id: string; summary: EvaluationSummary }[];
  interne: { question_id: string; value: EvaluationAnswerValue }[];
}

export interface EvaluationClientResponse {
  id: string;
  respondent_name: string;
  created_at: string;
  status: "retenue" | "ecartee";
  answers: Record<string, EvaluationAnswerValue>;
}

export interface PublicEvaluation {
  closed: boolean;
  title: string;
  project_name: string;
  client_intro?: string;
  questions?: EvaluationQuestion[];
}
```

- [ ] **Étape 2 : fonctions API** (`api/client.ts`), en suivant le style de `getTaskTypes` / `downloadHistoryExport` (`authFetch` + erreurs typées). Signatures :

```ts
getEvaluationCatalog(scope: { team: string } | { project: string }, includeArchived = false):
  Promise<{ can_manage: boolean; questions: EvaluationQuestion[] }>
createCatalogQuestion(scope: { team: string } | { project: string }, input: EvaluationQuestionInput): Promise<EvaluationQuestion>
updateCatalogQuestion(id: string, changes: Partial<EvaluationQuestionInput>): Promise<EvaluationQuestion>
archiveCatalogQuestion(id: string): Promise<EvaluationQuestion>
restoreCatalogQuestion(id: string): Promise<EvaluationQuestion>
moveCatalogQuestion(id: string, direction: "up" | "down"): Promise<EvaluationQuestion>

getEvaluationSheets(projectId: string): Promise<EvaluationSheetSummary[]>
createEvaluationSheet(projectId: string, title: string, clientIntro?: string): Promise<EvaluationSheetDetail>
getEvaluationSheet(id: string): Promise<EvaluationSheetDetail>
updateEvaluationSheet(id: string, changes: { title?: string; client_intro?: string }): Promise<EvaluationSheetDetail>
addSheetQuestion(sheetId: string, input: EvaluationQuestionInput): Promise<EvaluationQuestion>
updateSheetQuestion(sheetId: string, questionId: string, changes: Partial<EvaluationQuestionInput>): Promise<EvaluationQuestion>
archiveSheetQuestion(sheetId: string, questionId: string): Promise<EvaluationQuestion>
moveSheetQuestion(sheetId: string, questionId: string, direction: "up" | "down"): Promise<EvaluationQuestion>
transitionEvaluationSheet(id: string, action: "open" | "close" | "reopen" | "archive" | "rotate-link"): Promise<EvaluationSheetDetail>
saveInternalEvaluation(id: string, answers: Record<string, EvaluationAnswerValue>): Promise<EvaluationSheetDetail>
getEvaluationResults(id: string): Promise<EvaluationResults>
getEvaluationResponses(id: string): Promise<EvaluationClientResponse[]>
setEvaluationResponseStatus(sheetId: string, responseId: string, action: "discard" | "restore"): Promise<EvaluationClientResponse>
downloadEvaluationExport(id: string, title: string): Promise<void>   // fetch + blob, comme downloadHistoryExport

// Publics : fetch nu, SANS en-tête Authorization (comme getPublicDocs)
getPublicEvaluation(token: string): Promise<PublicEvaluation>
submitPublicEvaluation(token: string, respondentName: string, answers: Record<string, EvaluationAnswerValue>):
  Promise<{ detail: string }>
```

Les erreurs 400 du backend portent `{"detail", "question"}` : faire remonter `question` dans l'erreur levée (`class ApiFieldError extends Error { questionId?: string }`, ou le mécanisme d'erreur existant de `client.ts`) pour que les formulaires surlignent la bonne question.

- [ ] **Étape 3 : `visibility.ts`**, miroir exact de `answers.visible_question_ids`

```ts
import type { EvaluationAnswerValue, EvaluationQuestion } from "../../types/watodo";

/** Miroir de apps/evaluations/answers.py::visible_question_ids — garder les deux alignés. */
export function visibleQuestionIds(
  questions: Pick<EvaluationQuestion, "id" | "condition_on" | "condition_values">[],
  answers: Record<string, EvaluationAnswerValue>,
): Set<string> {
  const byId = new Map(questions.map((q) => [q.id, q]));
  const memo = new Map<string, boolean>();
  const isVisible = (id: string): boolean => {
    const cached = memo.get(id);
    if (cached !== undefined) return cached;
    const question = byId.get(id)!;
    const target = question.condition_on;
    let visible = true;
    if (target && byId.has(target)) {
      const value = answers[target];
      visible = isVisible(target) && typeof value === "string" && question.condition_values.includes(value);
    }
    memo.set(id, visible);
    return visible;
  };
  return new Set(questions.filter((q) => isVisible(q.id)).map((q) => q.id));
}
```

- [ ] **Étape 4 : `answerFormat.ts`**

```ts
import type { EvaluationAnswerType, EvaluationAnswerValue } from "../../types/watodo";

export const ANSWER_TYPE_LABELS: Record<EvaluationAnswerType, string> = {
  note_5: "Note de 1 à 5",
  nps_10: "Recommandation de 0 à 10",
  oui_non: "Oui / Non",
  choix_unique: "Choix unique",
  choix_multiple: "Choix multiple",
  texte_court: "Texte court",
  texte_long: "Texte long",
};

export function formatAnswer(value: EvaluationAnswerValue | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (value === "oui") return "Oui";
  if (value === "non") return "Non";
  return String(value);
}
```

- [ ] **Étape 5 : `npm --prefix frontend run lint` puis `npm --prefix frontend run build`** → OK.
- [ ] **Étape 6 : commit** (si autorisé) — `feat(evaluations): frontend types and API client`

---

### Tâche 10 : saisie d'une réponse et édition d'une question (composants partagés)

**Fichiers :**
- Créer : `features/evaluations/AnswerField.tsx/.css`, `features/evaluations/QuestionDefinitionForm.tsx/.css`

**Interfaces produites :**
- `<AnswerField question={EvaluationQuestion} value={EvaluationAnswerValue} onChange={(v) => void} error?: string disabled?: boolean />`
- `<QuestionDefinitionForm section={EvaluationSection} siblings={EvaluationQuestion[]} initial?={EvaluationQuestion} lockType?={boolean} onSubmit={(input: EvaluationQuestionInput) => Promise<void>} onCancel={() => void} />`

Comportement de `AnswerField` selon `answer_type` :
- `note_5` : 5 boutons-pastilles 1 à 5 (`role="radiogroup"`, chaque bouton `role="radio"` + `aria-checked`), libellés « Pas du tout » / « Tout à fait » aux extrémités. Recliquer la valeur choisie l'efface, sauf si la question est obligatoire.
- `nps_10` : 11 pastilles 0 à 10, libellés « Peu probable » / « Très probable ».
- `oui_non` : 2 boutons segmentés « Oui » / « Non », valeur `"oui"` / `"non"`.
- `choix_unique` : liste de boutons radio stylés (pas de `<select>`). Au-delà de 7 options, `Combobox` recherchable.
- `choix_multiple` : liste de `Checkbox` (composant existant).
- `texte_court` : `<input>` (`maxLength=200`) ; `texte_long` : `<textarea>` (`maxLength=5000`, compteur visible au-delà de 4 500).
- Libellé avec astérisque si `required`, `help_text` dessous, `error` affiché en `--color-error` avec `aria-describedby`.
- Tokens uniquement (`--color-accent` pour la sélection), cibles tactiles d'au moins 40 px, pastilles qui passent à la ligne sous 480 px.

Comportement de `QuestionDefinitionForm` :
- Champs : libellé (obligatoire), aide (facultative), type de réponse (`Combobox` sur `ANSWER_TYPE_LABELS`, désactivé si `lockType`), options (liste éditable : ajouter, retirer, au moins 2) seulement pour les choix, `Checkbox` « Réponse obligatoire ».
- Bloc « Afficher seulement si… » : `Combobox` des `siblings` de la même `section` dont le type est `oui_non` ou `choix_unique` (en excluant la question en cours d'édition), puis cases à cocher des valeurs possibles (`Oui`/`Non` ou les options de la cible). « Aucune condition » remet `condition_on` à `null`.
- La validation côté client reprend les règles du serveur (libellé non vide, au moins 2 options distinctes, au moins une valeur cochée si une condition est choisie). Les erreurs serveur (`detail`) s'affichent sous le formulaire.

- [ ] **Étape 1 : écrire les deux composants** (patron visuel de `TaskTypesEditor` pour l'édition en ligne).
- [ ] **Étape 2 : lint + build** → OK.
- [ ] **Étape 3 : commit** (si autorisé) — `feat(evaluations): answer field and question editor`

---

### Tâche 11 : catalogue (Administration > Groupes et projet sans groupe)

**Fichiers :**
- Créer : `features/evaluations/CatalogEditor.tsx/.css`
- Modifier : `features/administration/GroupsSection.tsx` (sous `<TaskTypesEditor scope={{ team: team.id }} collapsible />`), `features/projects/ProjectAdminTab.tsx` (sous `<TaskTypesEditor scope={{ project: project.id }} />`, même condition d'affichage : projet sans groupe)

**Interface :** `<CatalogEditor scope={{ team: string } | { project: string }} collapsible?: boolean />`

Comportement :
- Titre « Questions d'évaluation », replié par défaut si `collapsible` (même patron que `TaskTypesEditor`).
- Deux sous-listes : **Satisfaction client** et **Évaluation chef de projet**. Chaque ligne affiche le libellé, un badge neutre du type, « obligatoire » le cas échéant, et une mention « Affichée si « <cible> » = <valeurs> » pour une question conditionnelle (indentée sous sa cible quand celle-ci la précède).
- Si `can_manage` : boutons monter/descendre, modifier (ouvre `QuestionDefinitionForm` avec `lockType`), archiver (`ConfirmDialog`). « Ajouter une question » en bas de chaque section. Bascule « Afficher les questions archivées » avec restauration.
- Rappel discret sous le titre : « Ces questions sont copiées dans chaque nouvelle fiche. Les fiches déjà créées ne changent pas. »
- Erreur serveur (ex. « D'autres questions dépendent de celle-ci ») en toast.

- [ ] **Étape 1 : écrire `CatalogEditor` et le brancher aux deux endroits.**
- [ ] **Étape 2 : lint + build** → OK.
- [ ] **Étape 3 : commit** (si autorisé) — `feat(evaluations): question catalog editor`

---

### Tâche 12 : onglet « Évaluations » du projet (liste, édition, partie chef de projet)

**Fichiers :**
- Créer : `features/evaluations/EvaluationsTab.tsx/.css`, `SheetEditor.tsx`, `InternalEvaluationForm.tsx`
- Modifier : `features/projects/ProjectDetailView.tsx` (nouvel onglet `"evaluations"`, libellé « Évaluations », visible si `project.permissions.can_view_evaluations`, placé après « Documentation »)

Comportement de `EvaluationsTab` :
- Vue liste : tableau des fiches (titre, statut en `StatusBadge`, date de création, réponses reçues, actions). Filtre « Afficher les archivées » décoché par défaut. Bouton « Nouvelle fiche » (si `can_manage_evaluations`) → `PromptDialog` pour le titre → ouvre la fiche créée.
- Un clic sur une fiche ouvre la vue détail avec trois sous-onglets (composant `SectionSidebar` ou onglets internes déjà utilisés dans le hub) : **Questions**, **Évaluation chef de projet**, **Résultats** (tâche 13).

Comportement de `SheetEditor` (sous-onglet Questions) :
- En-tête : titre éditable (`InlineEditableText`), intro client éditable (`InlineEditableTextarea`), statut.
- Barre d'actions selon le statut : brouillon → « Ouvrir et générer le lien » (`ConfirmDialog` : « Les questions ne seront plus modifiables ») ; ouverte → lien public complet (`window.location.origin + public_path`, bouton copier), « Régénérer le lien » (`ConfirmDialog` : l'ancien lien cesse de fonctionner), « Clôturer » ; close → « Rouvrir », « Archiver » ; brouillon → « Archiver ».
- Deux sections (Client / Chef de projet) listant les questions. Badge « Générique » sur les copies du catalogue (non modifiables, sans actions). En brouillon, actions sur les questions propres : modifier, monter/descendre, retirer ; « Ajouter une question » par section (`QuestionDefinitionForm`, `siblings` = questions actives de la fiche).
- Aperçu : un bouton « Aperçu du formulaire client » rend les questions client avec `AnswerField` en local (état non enregistré), conditions comprises, pour tester les branchements avant ouverture.

Comportement de `InternalEvaluationForm` (sous-onglet Évaluation chef de projet) :
- En brouillon : message « Ouvrez la fiche pour remplir l'évaluation » (les questions doivent être figées).
- Sinon : questions `interne` rendues avec `AnswerField`, filtrées par `visibleQuestionIds`. Édition par les chefs de projet seulement (`permissions.can_manage`), lecture seule pour les admins. Bouton « Enregistrer » (pas d'enregistrement automatique), mention « Dernière mise à jour par X le … ». Une erreur `question` du serveur surligne le champ concerné.

- [ ] **Étape 1 : écrire les trois composants et brancher l'onglet.**
- [ ] **Étape 2 : lint + build** → OK.
- [ ] **Étape 3 : commit** (si autorisé) — `feat(evaluations): project evaluations tab`

---

### Tâche 13 : résultats, réponses, export CSV et impression PDF

**Fichiers :**
- Créer : `features/evaluations/SheetResults.tsx/.css`, `features/evaluations/SheetPrintView.tsx/.css`

Comportement de `SheetResults` (sous-onglet Résultats) :
- En-tête : `StatCard` « Réponses reçues », boutons « Exporter en CSV » (`downloadEvaluationExport`) et « Exporter en PDF » (impression).
- **Synthèse client** : une carte par question, selon `summary.kind` :
  - `note` : moyenne en grand (« 4,2 / 5 ») + `BarChart` de la distribution 1 à 5
  - `nps` : score en grand (« NPS +35 ») + `DonutChart` promoteurs / passifs / détracteurs
  - `yes_no` : `DonutChart` Oui / Non
  - `choices` : `BarChart` horizontal des options
  - `text` : liste des réponses (les 5 premières, puis « Voir tout »)
  - Couleurs : celles déjà utilisées par ces composants (pas de nouvelle palette). Une question sans réponse affiche « Aucune réponse ».
- **Partie chef de projet** : questions visibles et réponses (`formatAnswer`), ou lien vers le sous-onglet si rien n'est rempli.
- **Réponses individuelles** : tableau (date, répondant, statut), ligne dépliable (patron accordéon des Tâches) avec toutes les réponses. Action « Écarter » / « Rétablir » (`ConfirmDialog`). Les réponses écartées sont grisées et exclues de la synthèse après rechargement.

Comportement de `SheetPrintView` (export PDF) :
- Monté dans un portail (`document.body`) quand on clique « Exporter en PDF », puis `window.print()` après le rendu (`requestAnimationFrame`), démonté à l'événement `afterprint`.
- **Un document par réponse client retenue** (`page-break-after: always`), chacun contenant :
  1. En-tête : nom du projet, titre de la fiche, nom du répondant, date de réponse
  2. **Satisfaction client** : chaque question visible pour ce répondant (`visibleQuestionIds` sur ses réponses), avec sa réponse. Notes rendues en « 4 / 5 », NPS en « 9 / 10 ».
  3. **Évaluation chef de projet** : questions visibles de la partie interne et leurs réponses, avec « Renseignée par X le … »
- Sans réponse client : un seul document « Évaluation chef de projet ».
- Option « Imprimer seulement cette réponse » sur chaque ligne du tableau des réponses : même vue, filtrée sur une réponse.
- CSS d'impression : `@media print` masque `#root` (`display: none`) et n'affiche que le conteneur d'impression. Fond blanc, texte noir, police de la charte, marges `@page { margin: 18mm }`, aucune couleur d'interface. `@media screen` masque le conteneur.
- Le nom du fichier PDF proposé par le navigateur vient de `document.title` : le passer temporairement à `Évaluation – <projet> – <fiche>` pendant l'impression, puis le restaurer.

- [ ] **Étape 1 : écrire les deux composants.**
- [ ] **Étape 2 : lint + build** → OK.
- [ ] **Étape 3 : vérifier l'impression** dans Edge headless (`--print-to-pdf`), comme lors de la vérification de la doc publique : 2 réponses → PDF de 2 pages minimum, la partie chef de projet présente sur chacune.
- [ ] **Étape 4 : commit** (si autorisé) — `feat(evaluations): results screen, CSV and PDF export`

---

### Tâche 14 : page publique `/evaluation/<token>`

**Fichiers :**
- Créer : `features/evaluations/PublicEvaluationPage.tsx/.css`
- Modifier : `frontend/src/App.tsx` (détection d'URL, à côté de `PUBLIC_DOCS_PATH_PATTERN`)

```ts
const PUBLIC_EVALUATION_PATH_PATTERN = /^\/evaluation\/([^/]+)\/?$/;
// …
const publicEvaluationToken = window.location.pathname.match(PUBLIC_EVALUATION_PATH_PATTERN)?.[1];
if (publicEvaluationToken) {
  return <PublicEvaluationPage token={publicEvaluationToken} />;
}
```

À placer **avant** la garde de connexion, au même niveau que la doc publique.

Comportement :
- Page autonome, sans navigation Awtodo. Elle suit le thème clair/sombre comme `PublicDocsPage`. Colonne centrée (max 720 px), lisible sur mobile (gouttière 16 px, aucun défilement horizontal).
- En-tête : nom du projet (petit), titre de la fiche, intro (`MarkdownView` si l'intro accepte du Markdown, texte simple sinon ; choisir le texte simple pour cette version).
- Champ « Votre nom » obligatoire en premier, puis les questions client visibles (`visibleQuestionIds` recalculé à chaque changement). Une question masquée garde sa saisie en mémoire, mais elle n'est pas envoyée : le serveur l'ignore de toute façon.
- Validation locale des obligatoires visibles avant envoi (défilement vers la première erreur, focus). Bouton « Envoyer mes réponses » désactivé pendant l'envoi.
- Succès : écran de remerciement (le message du serveur), sans possibilité de renvoyer depuis la même page. Fiche close (`closed: true` ou 410) : « Ce questionnaire est clos. Merci de votre intérêt. » 404 : « Ce lien n'est pas ou plus valide. » 429 : « Trop d'envois depuis cette connexion, réessayez dans une heure. »
- Mention discrète en pied de page « Propulsé par Awtodo ».
- Aucun appel authentifié, aucun `authFetch` sur cette page.

- [ ] **Étape 1 : écrire la page et la route.**
- [ ] **Étape 2 : lint + build** → OK.
- [ ] **Étape 3 : vérification bout en bout** sur une base jetable (même méthode que la doc le 2026-11-05) : créer une fiche, l'ouvrir, ouvrir `/evaluation/<token>` en navigation privée, tester une condition, envoyer, voir la réponse dans Résultats, exporter CSV et PDF. Vérifier aussi à 375 px de large.
- [ ] **Étape 4 : commit** (si autorisé) — `feat(evaluations): public client evaluation page`

---

### Tâche 15 : documentation

**Fichiers :**
- Modifier : `CLAUDE.md`, `docs/modeles-et-api.md`, `docs/charte-graphique.md`

- [ ] **Étape 1 : `CLAUDE.md`**
  - Stack technique > Auth : la phrase « C'est le **seul** contournement autorisé de ce garde-fou » devient la mention de **deux** exceptions : la doc publiée (`/docs/<token>`) et le formulaire client d'une fiche d'évaluation ouverte (`/evaluation/<token>`, endpoints `GET/POST /api/v1/evaluations/public/<token>/…` en `AllowAny`, seules les questions client sont exposées, envoi limité à 10/h/IP).
  - Structure du projet : ajouter `evaluations/` (« fiches d'évaluation : catalogue de questions par groupe, formulaire client public, évaluation chef de projet — dépend de accounts/projects ») ; noter que `dashboards` en dépend.
  - Roadmap : entrée « Session du 2026-11-13 » résumant les décisions de cadrage (tableau du début de ce plan) et ce qui a été vérifié ou non.
  - Liste des modèles `StatusLifecycleModel` ayant le `Meta` explicite : ajouter `CatalogQuestion`, `EvaluationSheet`, `SheetQuestion`, `ClientResponse`.
- [ ] **Étape 2 : `docs/modeles-et-api.md`** : nouvelle section « Fiches d'évaluation de projet » (modèles, cycle de vie, règles de condition, copie figée du catalogue, droits, tous les endpoints, format des résultats, export CSV, widgets).
- [ ] **Étape 3 : `docs/charte-graphique.md`** : section « Évaluations » (`AnswerField` par type, page publique, impression PDF).
- [ ] **Étape 4 : suite complète** — `.venv/Scripts/python.exe manage.py test` (toutes apps) + `npm --prefix frontend run lint` + `npm --prefix frontend run build` ; consigner le nombre de tests dans la Roadmap.
- [ ] **Étape 5 : commit** (si autorisé) — `docs: evaluation sheets`

---

## Auto-relecture

- **Couverture des demandes :** lien public (5, 14) ; questions génériques + personnalisées (1, 3, 4, 11, 12) ; écran de recueil (13) ; export (6, 13) ; stats globales (7) ; partie satisfaction client + évaluation chef de projet (1, 6, 12) ; questions conditionnelles (2, 3, 10) ; PDF par répondant avec la partie chef de projet (13).
- **Noms cohérents entre tâches :** `sheet_questions`, `public_path`, `clean_definition`, `swap_position`, `visible_question_ids` / `visibleQuestionIds`, `evaluation_insights`, flags `can_manage_evaluations` / `can_view_evaluations`.
- **Points à vérifier à l'implémentation (non devinables sans lancer le code) :** nom de la fonction de permissions projet (tâche 4), mécanisme `security: [{}]` des vues publiques (tâche 8), lecture des taux de throttle à l'import (tâche 5), budget de requêtes de la liste des projets (tâche 4).
