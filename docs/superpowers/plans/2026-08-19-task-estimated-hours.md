# Temps théorique / temps réel sur les tâches — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre d'attribuer un temps théorique/estimé à une tâche (en plus du temps réel déjà capturé à la clôture, `time_spent`), et enrichir les écrans Statistiques (projet + global) avec la comparaison théorique/réel.

**Architecture:** Reprend le modèle `BudgetEntry` (temps × coût horaire) de `docs`/CLAUDE.md était initialement envisagé pour ce chantier — **remplacé, décision explicite de l'utilisateur** : pas de notion d'argent/taux horaire, uniquement du temps. `BudgetEntry` (`apps/budgeting/models.py`) reste donc un placeholder inutilisé, non touché par ce plan. Nouveau champ `Task.estimated_hours` (même forme que `time_spent`, déjà existant), gardé par la même règle que le titre/la description (`_ensure_can_rename` — tout membre du projet). `_task_insights` (déjà factorisé, réutilisé par l'onglet projet et l'écran global) étend son calcul avec les mêmes conventions déjà en place pour `tasks_on_time`/`tasks_late` (respect des échéances).

**Tech Stack:** Django + DRF, React + TypeScript. Aucune nouvelle dépendance.

## Global Constraints

- **Écart assumé par rapport à CLAUDE.md** : la section "Hors périmètre v1" nomme ce chantier "BudgetEntry (temps passé × coût horaire)" — remplacé par une notion de temps pur (théorique/réel), sans coût horaire, sur décision explicite de l'utilisateur en session. `BudgetEntry`/`hourly_rate` restent non implémentés, pas dans le périmètre de ce plan.
- Toute logique métier vit dans `services.py` (CLAUDE.md règle n°1).
- Le frontend ne recalcule jamais une règle métier — il lit ce que l'API renvoie.
- Toute app a ses tests dans `tests/` (CLAUDE.md règle n°7).
- Édition inline, jamais de bouton "Modifier" séparé pour un champ simple (cohérent avec le reste du projet — titre, description).
- Le comparatif "dépassement d'estimation" ne porte que sur les tâches **archivées ayant une estimation renseignée** (mêmes deux exclusions déjà en place pour `tasks_on_time`/`tasks_late` — tâches non terminées et tâches sans donnée de référence exclues du calcul, pas comptées comme un échec silencieux).

---

## File Structure

- `apps/tasks/models.py` — ajoute `Task.estimated_hours`.
- `apps/tasks/migrations/0007_task_estimated_hours.py` — auto-générée.
- `apps/tasks/serializers.py` — `TaskSerializer`/`TaskCreateSerializer` exposent `estimated_hours` ; `TaskInsightsSerializer` gagne `estimated_hours_total`/`tasks_over_estimate`/`tasks_under_estimate`.
- `apps/tasks/services.py` — `create_task` accepte `estimated_hours` ; nouvelle fonction `update_task_estimated_hours` ; `_task_insights` calcule les trois nouveaux agrégats.
- `apps/tasks/views.py` — nouvelle action `update-estimated-hours`.
- `apps/tasks/tests/test_estimated_hours.py` — nouveau : modèle + service + API + stats.
- `frontend/src/types/watodo.ts` — `Task.estimated_hours`, `TaskInsights` étendu.
- `frontend/src/api/client.ts` — `updateTaskEstimatedHours`, `TaskCreatePayload.estimated_hours`.
- `frontend/src/features/tasks/TaskCreateDialog.tsx` + `KanbanBoard.tsx` — champ de saisie à la création.
- `frontend/src/features/tasks/TaskAccordion.tsx` + `.css` — nouvelle section "Temps" (estimé éditable + réel en lecture seule).
- `frontend/src/components/EstimateComplianceWidget.tsx` + `.css` — nouveau, calqué sur `DeadlineComplianceWidget`.
- `frontend/src/features/projects/StatsTab.tsx` + `frontend/src/features/stats/GlobalStatsPage.tsx` — nouvelle StatCard + widget.

---

### Task 1: Champ `Task.estimated_hours` + exposition API en lecture/création

**Files:**
- Modify: `apps/tasks/models.py`
- Create: `apps/tasks/migrations/0007_task_estimated_hours.py` (auto-générée)
- Modify: `apps/tasks/serializers.py`
- Modify: `apps/tasks/services.py`
- Create: `apps/tasks/tests/test_estimated_hours.py`

**Interfaces:**
- Produces: `Task.estimated_hours` (Decimal, nullable) ; `create_task(..., estimated_hours=None)` — consommé par Task 2 (édition) et Task 4 (frontend).

- [ ] **Step 1: Write the failing test**

Créer `apps/tasks/tests/test_estimated_hours.py` :

```python
from django.test import TestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task
from apps.tasks.services import create_task


class EstimatedHoursFieldTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test Estim")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.member = User.objects.create_user(username="member-estim")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def test_task_can_be_created_with_an_estimate(self):
        task = create_task(
            actor=self.member,
            project=self.project,
            title="Corriger le bug",
            task_type="correction",
            estimated_hours="4.5",
        )

        self.assertEqual(task.estimated_hours, 4.5)

    def test_task_estimate_defaults_to_none(self):
        task = create_task(actor=self.member, project=self.project, title="Sans estimation", task_type="correction")

        self.assertIsNone(task.estimated_hours)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.tasks.tests.test_estimated_hours -v 2`
Expected: FAIL — `TypeError: create_task() got an unexpected keyword argument 'estimated_hours'`

- [ ] **Step 3: Write minimal implementation**

Dans `apps/tasks/models.py`, ajouter le champ juste après `time_spent` :

```python
    time_spent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    # Temps théorique/estimé, renseignable dès la création ou modifiable
    # ensuite par tout membre du projet (même garde que le titre/la
    # description, voir `_ensure_can_rename`) — distinct de `time_spent`
    # (temps réel, capturé uniquement à la clôture).
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
```

Générer et appliquer la migration :

Run: `python manage.py makemigrations tasks`
Expected: `Migrations for 'tasks': apps\tasks\migrations\0007_task_estimated_hours.py — + Add field estimated_hours to task`

Run: `python manage.py migrate tasks`
Expected: `Applying tasks.0007_task_estimated_hours... OK`

Dans `apps/tasks/services.py`, modifier la signature et le corps de `create_task` :

```python
def create_task(
    *,
    actor,
    project,
    title,
    task_type,
    description="",
    priority="moyenne",
    deadline=None,
    external_reference_id=None,
    assignee=None,
    estimated_hours=None,
):
    _require_member(actor, project)

    if _is_manager(actor, project):
        status = "assignee" if assignee else "disponible"
    else:
        status = "en_attente_validation"
        assignee = None

    return Task.objects.create(
        project=project,
        version=get_current_version(project),
        title=title,
        description=description,
        task_type=task_type,
        priority=priority,
        deadline=deadline,
        external_reference_id=external_reference_id,
        assignee=assignee,
        status=status,
        estimated_hours=estimated_hours,
    )
```

Dans `apps/tasks/serializers.py`, ajouter `"estimated_hours"` à `TaskSerializer.Meta.fields` (après `"time_spent"`), et ajouter le champ à `TaskCreateSerializer` :

```python
    estimated_hours = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True, min_value=0
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.tasks.tests.test_estimated_hours -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/tasks/models.py apps/tasks/migrations/0007_task_estimated_hours.py apps/tasks/serializers.py apps/tasks/services.py apps/tasks/tests/test_estimated_hours.py
git commit -m "feat(tasks): add estimated_hours field, settable at creation"
```

---

### Task 2: Édition de l'estimation après création

**Files:**
- Modify: `apps/tasks/services.py`
- Modify: `apps/tasks/views.py`
- Modify: `apps/tasks/tests/test_estimated_hours.py`

**Interfaces:**
- Consumes: `_ensure_can_rename`, `record_changes` (déjà existants dans `apps/tasks/services.py`).
- Produces: `update_task_estimated_hours(*, actor, task, estimated_hours)` ; `POST /api/v1/tasks/{id}/update-estimated-hours/` — consommés par le frontend (Task 5).

- [ ] **Step 1: Write the failing test**

Ajouter à `apps/tasks/tests/test_estimated_hours.py` :

```python
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.tasks.services import TaskPermissionError, update_task_estimated_hours


class UpdateEstimatedHoursServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test Estim 2")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.member = User.objects.create_user(username="member-estim-2")
        self.outsider = User.objects.create_user(username="outsider-estim")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Corriger le bug", task_type="correction"
        )

    def test_member_can_set_estimate(self):
        update_task_estimated_hours(actor=self.member, task=self.task, estimated_hours="6")

        self.assertEqual(self.task.estimated_hours, 6)

    def test_member_can_clear_estimate(self):
        update_task_estimated_hours(actor=self.member, task=self.task, estimated_hours="6")

        update_task_estimated_hours(actor=self.member, task=self.task, estimated_hours=None)

        self.assertIsNone(self.task.estimated_hours)

    def test_outsider_cannot_set_estimate(self):
        with self.assertRaises(TaskPermissionError):
            update_task_estimated_hours(actor=self.outsider, task=self.task, estimated_hours="6")


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
class UpdateEstimatedHoursApiTests(APITestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test Estim API")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.member = User.objects.create_user(username="member-estim-api")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Corriger le bug", task_type="correction"
        )

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_update_estimated_hours(self):
        response = self.client.post(
            f"/api/v1/tasks/{self.task.id}/update-estimated-hours/",
            {"estimated_hours": "3.5"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["estimated_hours"], "3.50")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.tasks.tests.test_estimated_hours.UpdateEstimatedHoursServiceTests apps.tasks.tests.test_estimated_hours.UpdateEstimatedHoursApiTests -v 2`
Expected: FAIL — `ImportError: cannot import name 'update_task_estimated_hours'`

- [ ] **Step 3: Write minimal implementation**

Dans `apps/tasks/services.py`, ajouter après `update_task_description` :

```python
def update_task_estimated_hours(*, actor, task, estimated_hours):
    # Même garde que le titre/la description : tout membre du projet, pas
    # réservé à l'assigné (_ensure_can_rename).
    _ensure_can_rename(actor, task)

    with record_changes(task, actor=actor):
        task.estimated_hours = estimated_hours
        task.save()
    return task
```

Dans `apps/tasks/views.py`, ajouter `update_task_estimated_hours` à l'import depuis `.services`, puis ajouter l'action après `update_description` :

```python
    @action(detail=True, methods=["post"], url_path="update-estimated-hours")
    def update_estimated_hours(self, request, pk=None):
        task = self.get_object()

        try:
            update_task_estimated_hours(
                actor=request.user, task=task, estimated_hours=request.data.get("estimated_hours")
            )
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except InvalidTransitionError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(task).data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.tasks.tests.test_estimated_hours -v 2`
Expected: PASS (2 tests de Task 1 + 5 de cette tâche = 7)

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `python manage.py test`
Expected: tous les tests passent (401 avant cette passe + les nouveaux)

- [ ] **Step 6: Commit**

```bash
git add apps/tasks/services.py apps/tasks/views.py apps/tasks/tests/test_estimated_hours.py
git commit -m "feat(tasks): expose POST /api/v1/tasks/{id}/update-estimated-hours/"
```

---

### Task 3: Enrichissement des statistiques (théorique vs réel)

**Files:**
- Modify: `apps/tasks/services.py`
- Modify: `apps/tasks/serializers.py`
- Modify: `apps/tasks/tests/test_estimated_hours.py`

**Interfaces:**
- Consumes: `Task.estimated_hours` (Task 1), `_task_insights` (déjà existant).
- Produces: `_task_insights(...)` renvoie désormais aussi `estimated_hours_total`, `tasks_over_estimate`, `tasks_under_estimate` — consommés par le frontend (Task 6/7) via `project-insights`/`global-stats` (endpoints déjà existants, aucun changement d'URL).

- [ ] **Step 1: Write the failing test**

Ajouter à `apps/tasks/tests/test_estimated_hours.py` :

```python
from apps.tasks.services import get_project_task_insights


class TaskInsightsEstimateTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test Estim Insights")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.member = User.objects.create_user(username="member-estim-insights")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def make_archived_task(self, *, estimated_hours, time_spent):
        return Task.objects.create(
            project=self.project,
            version=self.version,
            title="Tâche terminée",
            task_type="correction",
            status="archivee",
            estimated_hours=estimated_hours,
            time_spent=time_spent,
        )

    def test_estimated_hours_total_sums_all_tasks_in_scope(self):
        self.make_archived_task(estimated_hours="4", time_spent="5")
        Task.objects.create(
            project=self.project, version=self.version, title="Pas terminée", task_type="correction",
            estimated_hours="2",
        )

        insights = get_project_task_insights(actor=self.member, project=self.project)

        self.assertEqual(insights["estimated_hours_total"], 6)

    def test_task_over_estimate_is_counted(self):
        self.make_archived_task(estimated_hours="4", time_spent="5")

        insights = get_project_task_insights(actor=self.member, project=self.project)

        self.assertEqual(insights["tasks_over_estimate"], 1)
        self.assertEqual(insights["tasks_under_estimate"], 0)

    def test_task_under_estimate_is_counted(self):
        self.make_archived_task(estimated_hours="4", time_spent="3")

        insights = get_project_task_insights(actor=self.member, project=self.project)

        self.assertEqual(insights["tasks_over_estimate"], 0)
        self.assertEqual(insights["tasks_under_estimate"], 1)

    def test_task_without_estimate_excluded_from_over_under_counts(self):
        self.make_archived_task(estimated_hours=None, time_spent="3")

        insights = get_project_task_insights(actor=self.member, project=self.project)

        self.assertEqual(insights["tasks_over_estimate"], 0)
        self.assertEqual(insights["tasks_under_estimate"], 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.tasks.tests.test_estimated_hours.TaskInsightsEstimateTests -v 2`
Expected: FAIL — `KeyError: 'estimated_hours_total'`

- [ ] **Step 3: Write minimal implementation**

Dans `apps/tasks/services.py`, modifier `_task_insights` (fonction déjà existante) — ajouter après le calcul de `tasks_on_time`/`tasks_late` :

```python
    estimated_hours_total = tasks_qs.aggregate(total=Sum("estimated_hours"))["total"] or Decimal("0")

    done_with_estimate = done.exclude(estimated_hours__isnull=True)
    tasks_over_estimate = done_with_estimate.filter(time_spent__gt=F("estimated_hours")).count()
    tasks_under_estimate = done_with_estimate.count() - tasks_over_estimate
```

Ajouter les trois clés au dict retourné en fin de fonction (`return { ... }`) :

```python
        "estimated_hours_total": estimated_hours_total,
        "tasks_over_estimate": tasks_over_estimate,
        "tasks_under_estimate": tasks_under_estimate,
```

Dans `apps/tasks/serializers.py`, ajouter à `TaskInsightsSerializer` (après `hours_total`, et après `tasks_late` respectivement) :

```python
    estimated_hours_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    tasks_over_estimate = serializers.IntegerField(read_only=True)
    tasks_under_estimate = serializers.IntegerField(read_only=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.tasks.tests.test_estimated_hours -v 2`
Expected: PASS (7 tests précédents + 4 nouveaux = 11)

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `python manage.py test`
Expected: tous les tests passent

- [ ] **Step 6: Commit**

```bash
git add apps/tasks/services.py apps/tasks/serializers.py apps/tasks/tests/test_estimated_hours.py
git commit -m "feat(tasks): add estimated vs actual time comparison to task insights"
```

---

### Task 4: Types + client frontend

**Files:**
- Modify: `frontend/src/types/watodo.ts`
- Modify: `frontend/src/api/client.ts`

**Interfaces:**
- Consumes: réponses JSON de `TaskSerializer`/`TaskInsightsSerializer` (Tasks 1-3).
- Produces: `Task.estimated_hours`, `TaskInsights` étendu, `updateTaskEstimatedHours(taskId, value)`, `TaskCreatePayload.estimated_hours` — consommés par Tasks 5-7.

- [ ] **Step 1: Update the types**

Dans `frontend/src/types/watodo.ts`, ajouter `estimated_hours: string | null;` à l'interface `Task` (juste après `time_spent`).

Ajouter à `TaskInsights` (après `hours_total`, et après `tasks_late` respectivement) :

```typescript
  estimated_hours_total: string;
  tasks_over_estimate: number;
  tasks_under_estimate: number;
```

- [ ] **Step 2: Add the client function and extend the create payload**

Dans `frontend/src/api/client.ts`, ajouter `estimated_hours?: string;` à `TaskCreatePayload` (avant l'index signature `[key: string]: unknown`).

Ajouter, à côté de `updateTaskDescription` :

```typescript
export function updateTaskEstimatedHours(taskId: string, estimatedHours: string | null): Promise<Task> {
  return postJson<Task>(`/tasks/${taskId}/update-estimated-hours/`, { estimated_hours: estimatedHours });
}
```

- [ ] **Step 3: Verify the frontend compiles**

Run: `cd frontend && npm run build`
Expected: build réussi, aucune erreur TypeScript

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/watodo.ts frontend/src/api/client.ts
git commit -m "feat(tasks): add estimated_hours to Task/TaskInsights types and client"
```

---

### Task 5: Saisie de l'estimation à la création + édition dans l'accordéon

**Files:**
- Modify: `frontend/src/features/tasks/TaskCreateDialog.tsx`
- Modify: `frontend/src/features/tasks/KanbanBoard.tsx`
- Modify: `frontend/src/features/tasks/TaskAccordion.tsx`
- Modify: `frontend/src/features/tasks/TaskAccordion.css`
- Modify: `frontend/src/features/tasks/TasksListPage.tsx`

**Interfaces:**
- Consumes: `updateTaskEstimatedHours` (Task 4).
- Produces: rien de nouveau consommé ailleurs.

- [ ] **Step 1: Add the field to the creation form**

Dans `frontend/src/features/tasks/TaskCreateDialog.tsx`, ajouter `estimated_hours: string;` à `TaskCreateFormValues`, et `estimated_hours: ""` à l'état initial.

Ajouter un champ dans la grille (à côté d'"Échéance") :

```tsx
          <label className="task-create-dialog__field">
            <span>Temps estimé (heures)</span>
            <input
              type="number"
              min="0"
              step="0.5"
              value={values.estimated_hours}
              onChange={(event) => update("estimated_hours", event.target.value)}
            />
          </label>
```

- [ ] **Step 2: Include it in the create payload**

Dans `frontend/src/features/tasks/KanbanBoard.tsx`, dans `buildCreatePayload`, ajouter :

```typescript
  if (values.estimated_hours.trim()) payload.estimated_hours = values.estimated_hours.trim();
```

- [ ] **Step 3: Add an editable "Temps" section to `TaskAccordion`**

Dans `frontend/src/features/tasks/TaskAccordion.tsx`, ajouter l'import :

```typescript
import { InlineEditableText } from "../../components/InlineEditableText";
```

(Vérifier qu'il n'est pas déjà importé — `InlineEditableTextarea` l'est déjà pour la description, `InlineEditableText`, la variante mono-ligne, ne l'est pas encore dans ce fichier.)

Ajouter la prop `onSaveEstimatedHours: (task: Task, value: string | null) => void;` à `TaskAccordionProps` et au paramètre déstructuré.

Ajouter une nouvelle section dans `.task-accordion__grid`, à côté de la section "Attribution" :

```tsx
          <section className="task-accordion__section">
            <h3 className="task-accordion__section-title">Temps</h3>
            <p className="task-accordion__meta">
              Estimé :{" "}
              <InlineEditableText
                value={task.estimated_hours ?? ""}
                onSave={(value) => onSaveEstimatedHours(task, value.trim() ? value.trim() : null)}
                ariaLabel="Temps estimé (heures)"
                disabled={pending}
              />
              {" h"}
            </p>
            <p className="task-accordion__meta">
              Réel : {task.time_spent ? `${task.time_spent} h` : "—"} (renseigné à la clôture)
            </p>
          </section>
```

`InlineEditableText` affiche une chaîne vide si `task.estimated_hours` est `null` — cliquer dessus permet de saisir une première valeur (comportement déjà correct par construction du composant, pas de cas particulier à gérer côté `TaskAccordion`).

- [ ] **Step 4: Wire the handler in `TasksListPage`**

Dans `frontend/src/features/tasks/TasksListPage.tsx`, importer `updateTaskEstimatedHours` depuis `../../api/client`.

Ajouter un handler, à côté de `handleSaveDescription` :

```typescript
  async function handleSaveEstimatedHours(task: Task, value: string | null) {
    setPendingTaskId(task.id);
    try {
      const updated = await updateTaskEstimatedHours(task.id, value);
      setTasks((current) => current?.map((t) => (t.id === task.id ? updated : t)) ?? current);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "La mise à jour du temps estimé a échoué.");
    } finally {
      setPendingTaskId(null);
    }
  }
```

Passer `onSaveEstimatedHours={handleSaveEstimatedHours}` au rendu de `<TaskAccordion>`.

- [ ] **Step 5: Verify the frontend compiles**

Run: `cd frontend && npm run build`
Expected: build réussi, aucune erreur TypeScript

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/tasks/TaskCreateDialog.tsx frontend/src/features/tasks/KanbanBoard.tsx frontend/src/features/tasks/TaskAccordion.tsx frontend/src/features/tasks/TaskAccordion.css frontend/src/features/tasks/TasksListPage.tsx
git commit -m "feat(tasks): capture estimated hours at creation, editable inline in TaskAccordion"
```

---

### Task 6: `EstimateComplianceWidget`

**Files:**
- Create: `frontend/src/components/EstimateComplianceWidget.tsx`
- Create: `frontend/src/components/EstimateComplianceWidget.css`

**Interfaces:**
- Produces: `EstimateComplianceWidget` (composant, props `onTarget`/`overEstimate`) — consommé par Task 7.

- [ ] **Step 1: Create the component**

Créer `frontend/src/components/EstimateComplianceWidget.tsx` (calqué sur `DeadlineComplianceWidget.tsx`, même structure, `DonutChart` déjà générique) :

```tsx
import { Timer } from "lucide-react";
import { DonutChart } from "./DonutChart";
import "./EstimateComplianceWidget.css";

interface EstimateComplianceWidgetProps {
  onTarget: number;
  overEstimate: number;
}

export function EstimateComplianceWidget({ onTarget, overEstimate }: EstimateComplianceWidgetProps) {
  const total = onTarget + overEstimate;
  const rate = total > 0 ? Math.round((onTarget / total) * 100) : null;

  return (
    <div className="estimate-compliance">
      <div className="estimate-compliance__header">
        <Timer size={16} strokeWidth={1.75} aria-hidden="true" />
        <h3>Respect des estimations</h3>
      </div>
      {total === 0 ? (
        <p className="estimate-compliance__message">Aucune tâche estimée et clôturée pour l'instant.</p>
      ) : (
        <div className="estimate-compliance__body">
          <DonutChart
            slices={[
              { label: "Dans les temps", value: onTarget, color: "var(--tone-positive-text)" },
              { label: "Dépassement", value: overEstimate, color: "var(--priority-critique-text)" },
            ]}
            centerLabel="dans les temps"
            centerValue={`${rate} %`}
            size={130}
            emphasis
          />
          <ul className="estimate-compliance__legend">
            <li className="estimate-compliance__legend-item">
              <span className="estimate-compliance__swatch estimate-compliance__swatch--on-target" />
              <span>Dans les temps</span>
              <strong>{onTarget}</strong>
            </li>
            <li className="estimate-compliance__legend-item">
              <span className="estimate-compliance__swatch estimate-compliance__swatch--over" />
              <span>Dépassement</span>
              <strong>{overEstimate}</strong>
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}
```

Créer `frontend/src/components/EstimateComplianceWidget.css` — copier intégralement `frontend/src/components/DeadlineComplianceWidget.css`, en remplaçant le préfixe de classe `deadline-compliance` par `estimate-compliance` (mêmes valeurs/tokens, seuls les noms de classe changent) et `--on-time`/`--late` par `--on-target`/`--over`.

- [ ] **Step 2: Verify the frontend compiles**

Run: `cd frontend && npm run build`
Expected: build réussi, aucune erreur TypeScript

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/EstimateComplianceWidget.tsx frontend/src/components/EstimateComplianceWidget.css
git commit -m "feat: add EstimateComplianceWidget, mirrors DeadlineComplianceWidget"
```

---

### Task 7: Brancher le widget + une StatCard dans les deux écrans Statistiques

**Files:**
- Modify: `frontend/src/features/projects/StatsTab.tsx`
- Modify: `frontend/src/features/stats/GlobalStatsPage.tsx`

**Interfaces:**
- Consumes: `EstimateComplianceWidget` (Task 6), `TaskInsights.estimated_hours_total`/`tasks_over_estimate`/`tasks_under_estimate` (Task 4).
- Produces: rien de nouveau consommé ailleurs — dernier maillon de ce plan.

- [ ] **Step 1: `StatsTab` (onglet projet)**

Dans `frontend/src/features/projects/StatsTab.tsx`, ajouter l'import :

```typescript
import { EstimateComplianceWidget } from "../../components/EstimateComplianceWidget";
```

Ajouter une `StatCard`, juste après celle de "Heures passées" (même `formatHours` déjà défini dans ce fichier) :

```tsx
        <StatCard
          icon={Timer}
          tone="neutral"
          value={insights ? formatHours(insights.estimated_hours_total) : "—"}
          label="Temps estimé total"
        />
```

(`Timer` est déjà importé dans ce fichier, réutilisé pour "Délai moyen de traitement" — l'ajouter à l'import `lucide-react` en haut du fichier seulement s'il n'y est pas déjà.)

Ajouter le widget dans `.stats-tab__widgets`, à côté de `DeadlineComplianceWidget` :

```tsx
          <EstimateComplianceWidget onTarget={insights.tasks_under_estimate} overEstimate={insights.tasks_over_estimate} />
```

- [ ] **Step 2: `GlobalStatsPage` (écran global)**

Même principe dans `frontend/src/features/stats/GlobalStatsPage.tsx` : import de `EstimateComplianceWidget`, une `StatCard` "Temps estimé total" à côté de celle "Heures passées", et le widget à côté de `DeadlineComplianceWidget`.

- [ ] **Step 3: Verify the frontend compiles**

Run: `cd frontend && npm run build`
Expected: build réussi, aucune erreur TypeScript

- [ ] **Step 4: Manual smoke test**

Démarrer `python manage.py runserver` et `npm run dev`. Créer une tâche avec un temps estimé, la clôturer avec un temps réel différent, vérifier sur l'onglet Statistiques du projet et l'écran Statistiques global que la StatCard "Temps estimé total" et le widget "Respect des estimations" reflètent bien les données.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/projects/StatsTab.tsx frontend/src/features/stats/GlobalStatsPage.tsx
git commit -m "feat(stats): show estimated vs actual time in project and global stats screens"
```

---

## Self-Review

**Spec coverage :** les trois points de la reformulation utilisateur sont couverts : (1) temps théorique attribuable à une tâche (Task 1, création ; Task 2, édition ultérieure), (2) temps réel déjà existant (`time_spent`, inchangé, simplement affiché à côté de l'estimation dans `TaskAccordion` — Task 5), (3) statistiques projet et globales enrichies (Task 3 backend, Task 6/7 frontend).

**Placeholder scan :** aucun "TODO" — code complet à chaque step.

**Type consistency :** `estimated_hours` (Task 1, modèle/serializer) ↔ `estimated_hours` (Task 4, type frontend/payload) ↔ prop `onSaveEstimatedHours` (Task 5) ; `estimated_hours_total`/`tasks_over_estimate`/`tasks_under_estimate` (Task 3, service+serializer) ↔ mêmes noms dans `TaskInsights` (Task 4) ↔ props `onTarget`/`overEstimate` de `EstimateComplianceWidget` (Task 6, mappées explicitement depuis `tasks_under_estimate`/`tasks_over_estimate` en Task 7 — noms différents assumés : "under estimate" côté donnée technique, "on target" côté libellé utilisateur, cohérent avec `DeadlineComplianceWidget` qui a le même écart `onTime`/`tasks_on_time`).

**Écart de p érimètre, redit ici pour visibilité :** ce plan remplace le chantier "BudgetEntry (temps × coût horaire)" nommé dans `CLAUDE.md` par une version sans notion d'argent, sur demande explicite de l'utilisateur en session — `BudgetEntry`/`hourly_rate` restent des placeholders non implémentés après ce plan, comme avant.
