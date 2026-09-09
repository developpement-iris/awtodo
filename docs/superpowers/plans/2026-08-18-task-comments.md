# Commentaires sur les tâches — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre à un membre de projet d'ajouter des commentaires sur une tâche, exactement comme c'est déjà possible sur un incident.

**Architecture:** Copie fidèle du pattern `IncidentComment` (`apps/incidents/`) vers `apps/tasks/` : un modèle `TaskComment` sans `StatusLifecycleModel` (pas d'édition/suppression, donc pas d'état terminal à distinguer), un service `add_comment` gardé par la même règle d'appartenance déjà utilisée pour renommer une tâche (`_ensure_can_rename` → tout membre du projet), un `TaskDetailSerializer` avec commentaires imbriqués réservé à `retrieve`, une action `POST /api/v1/tasks/{id}/comments/`. Côté frontend, deux zones sont déjà prévues et désactivées dans `TaskAccordion.tsx` ("Fonctionnalité à venir — l'API ne le supporte pas encore") — il s'agit de les brancher, pas de les créer.

**Tech Stack:** Django + DRF (backend), React + TypeScript (frontend) — aucune nouvelle dépendance.

## Global Constraints

- Règle transverse "aucune suppression physique" (CLAUDE.md) : `TaskComment` n'a pas d'édition ni de suppression exposée, donc pas de `StatusLifecycleModel` nécessaire — même raisonnement que `IncidentComment` (voir sa docstring dans `apps/incidents/models.py`).
- Toute logique métier non triviale vit dans `services.py`, jamais dans les vues/serializers (règle d'architecture n°1, CLAUDE.md).
- PK en UUID sur tout modèle exposé via l'API (`UUIDModel`, CLAUDE.md règle n°4).
- Le frontend ne recalcule jamais une règle de rôle — il lit `task.permissions.can_comment` (CLAUDE.md > "Permissions API — flags calculés").
- Toute app métier a ses tests dans `tests/` (CLAUDE.md règle n°7).
- Pas de librairie de composants front nouvelle pour cette passe — le markup existe déjà dans `TaskAccordion.tsx`, seul le câblage change.

---

## File Structure

- `apps/tasks/models.py` — ajoute `TaskComment` (nouveau modèle, en bas du fichier).
- `apps/tasks/migrations/0006_taskcomment.py` — migration auto-générée.
- `apps/tasks/services.py` — ajoute `_ensure_can_comment`, `can_comment_task`, `add_comment` ; étend `get_task_permissions` avec `can_comment`.
- `apps/tasks/serializers.py` — ajoute `TaskCommentSerializer`, `TaskCommentCreateSerializer`, `TaskDetailSerializer` (hérite de `TaskSerializer` + `comments` imbriqués, même pattern qu'`IncidentDetailSerializer`).
- `apps/tasks/views.py` — `get_serializer_class` renvoie `TaskDetailSerializer` sur `retrieve` ; nouvelle action `comments` (`POST /api/v1/tasks/{id}/comments/`).
- `apps/tasks/tests/test_comments.py` — nouveau fichier, tests service + API (mêmes scénarios que `apps/incidents/tests/test_services.py::AddCommentTests` et `test_api.py` pour les commentaires incidents).
- `frontend/src/types/watodo.ts` — ajoute `TaskComment`, `TaskDetail` (extends `Task`), `can_comment` sur `TaskPermissions`.
- `frontend/src/api/client.ts` — ajoute `getTask(taskId)`, `addTaskComment(taskId, content)`.
- `frontend/src/features/tasks/TaskAccordion.tsx` — remplace la section "Commentaires" statique par le rendu réel (liste + composeur), même structure que `IncidentAccordion.tsx`.
- `frontend/src/features/tasks/TasksListPage.tsx` — ajoute l'état `comments`/`commentsError`/`commentSubmitting` + le fetch au montage/dépliage + `handleAddComment`, même pattern qu'`IncidentsPage.tsx`.

---

### Task 1: Modèle `TaskComment` + migration

**Files:**
- Modify: `apps/tasks/models.py`
- Create: `apps/tasks/migrations/0006_taskcomment.py` (auto-générée)
- Test: `apps/tasks/tests/test_comments.py`

**Interfaces:**
- Produces: `TaskComment` (champs `task` FK→`Task`, `author` FK→`User`, `content` TextField, `created_at`/`updated_at`/`id` hérités) — consommé par Task 2 (`add_comment`) et Task 3 (`TaskCommentSerializer`).

- [ ] **Step 1: Write the failing test**

Créer `apps/tasks/tests/test_comments.py` :

```python
from django.test import TestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task, TaskComment


class TaskCommentModelTests(TestCase):
    def test_creates_comment_on_task(self):
        project = Project.objects.create(name="Projet Test")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        author = User.objects.create_user(username="alice")
        task = Task.objects.create(
            project=project, version=version, title="Corriger le bug", task_type="correction"
        )

        comment = TaskComment.objects.create(task=task, author=author, content="Je regarde ça")

        self.assertEqual(task.comments.count(), 1)
        self.assertEqual(comment.author, author)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.tasks.tests.test_comments -v 2`
Expected: FAIL avec `ImportError: cannot import name 'TaskComment'`

- [ ] **Step 3: Write minimal implementation**

Ajouter à la fin de `apps/tasks/models.py` :

```python
class TaskComment(UUIDModel, TimeStampedModel):
    """Pas d'édition ni de suppression en v1 — un commentaire posté est
    permanent, cohérent avec la règle transverse "aucune suppression
    physique". Pas de StatusLifecycleModel : sans update/delete possible,
    il n'y a jamais d'état "terminal" à distinguer d'un état "actif" — même
    raisonnement que `apps.incidents.models.IncidentComment`."""

    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="task_comments")
    content = models.TextField()

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Commentaire de {self.author} sur {self.task}"
```

- [ ] **Step 4: Generate and apply the migration**

Run: `python manage.py makemigrations tasks`
Expected: `Migrations for 'tasks': apps\tasks\migrations\0006_taskcomment.py — + Create model TaskComment`

Run: `python manage.py migrate tasks`
Expected: `Applying tasks.0006_taskcomment... OK`

- [ ] **Step 5: Run test to verify it passes**

Run: `python manage.py test apps.tasks.tests.test_comments -v 2`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/tasks/models.py apps/tasks/migrations/0006_taskcomment.py apps/tasks/tests/test_comments.py
git commit -m "feat(tasks): add TaskComment model"
```

---

### Task 2: Service `add_comment` + garde de permission

**Files:**
- Modify: `apps/tasks/services.py`
- Test: `apps/tasks/tests/test_comments.py`

**Interfaces:**
- Consumes: `TaskComment` (Task 1), `_require_member(actor, project)` (déjà existant dans ce fichier, ligne 46).
- Produces: `add_comment(*, actor, task, content) -> TaskComment` (lève `TaskPermissionError`/`InvalidTransitionError`) ; `can_comment_task(user, task) -> bool` ; `get_task_permissions(...)` inclut désormais la clé `can_comment` — consommés par Task 3 (vue) et par le frontend (Task 4/5).

- [ ] **Step 1: Write the failing test**

Ajouter à `apps/tasks/tests/test_comments.py` :

```python
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.services import InvalidTransitionError, TaskPermissionError, add_comment


class AddCommentServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.member = User.objects.create_user(username="member")
        self.outsider = User.objects.create_user(username="outsider")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Corriger le bug", task_type="correction"
        )

    def test_member_can_comment(self):
        comment = add_comment(actor=self.member, task=self.task, content="Je regarde ça")

        self.assertEqual(comment.author, self.member)
        self.assertEqual(comment.task, self.task)
        self.assertEqual(self.task.comments.count(), 1)

    def test_outsider_cannot_comment(self):
        with self.assertRaises(TaskPermissionError):
            add_comment(actor=self.outsider, task=self.task, content="Je ne devrais pas pouvoir")

    def test_empty_comment_is_rejected(self):
        with self.assertRaises(InvalidTransitionError):
            add_comment(actor=self.member, task=self.task, content="   ")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.tasks.tests.test_comments.AddCommentServiceTests -v 2`
Expected: FAIL avec `ImportError: cannot import name 'add_comment'`

- [ ] **Step 3: Write minimal implementation**

Dans `apps/tasks/services.py`, ajouter l'import du modèle et les fonctions :

```python
from .models import Task, TaskComment
```

Ajouter après `_ensure_can_rename` (garde de garde, même position logique que les autres fonctions de garde) :

```python
def _ensure_can_comment(actor, task):
    # Même règle que renommer/éditer la description : tout membre du
    # projet, pas réservé à l'assigné (_ensure_can_rename, ligne 67).
    _require_member(actor, task.project)


def can_comment_task(user, task):
    return _check(_ensure_can_comment, user, task)
```

Ajouter `"can_comment": can_comment_task(user, task),` dans le dict retourné par `get_task_permissions` (après `"can_edit_description"`).

Ajouter en bas du fichier, après `complete_task` :

```python
def add_comment(*, actor, task, content):
    _ensure_can_comment(actor, task)
    if not content or not content.strip():
        raise InvalidTransitionError("Le commentaire ne peut pas être vide.")

    return TaskComment.objects.create(task=task, author=actor, content=content.strip())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.tasks.tests.test_comments -v 2`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/tasks/services.py apps/tasks/tests/test_comments.py
git commit -m "feat(tasks): add comment permission guard and add_comment service"
```

---

### Task 3: Serializers + endpoint `POST /api/v1/tasks/{id}/comments/`

**Files:**
- Modify: `apps/tasks/serializers.py`
- Modify: `apps/tasks/views.py`
- Test: `apps/tasks/tests/test_comments.py`

**Interfaces:**
- Consumes: `add_comment`, `TaskPermissionError`, `InvalidTransitionError` (Task 2) ; `TaskComment` (Task 1) ; `TaskSerializer` (déjà existant).
- Produces: `TaskCommentSerializer` (champs `id`, `author`, `content`, `created_at`) ; `TaskDetailSerializer` (= `TaskSerializer` + `comments`) ; action de vue `comments` sur `TaskViewSet` — consommés par le frontend (Task 4/5).

- [ ] **Step 1: Write the failing test**

Ajouter à `apps/tasks/tests/test_comments.py` (nouvelle classe, utilise `rest_framework.test.APITestCase` — même montage que `apps/incidents/tests/test_api.py`) :

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
class TaskCommentApiTests(APITestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.member = User.objects.create_user(username="member-comment")
        self.outsider = User.objects.create_user(username="outsider-comment")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Corriger le bug", task_type="correction"
        )

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_member_can_add_comment(self):
        response = self.client.post(
            f"/api/v1/tasks/{self.task.id}/comments/",
            {"content": "On regarde ça"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["content"], "On regarde ça")

    def test_outsider_cannot_add_comment(self):
        response = self.client.post(
            f"/api/v1/tasks/{self.task.id}/comments/",
            {"content": "Je ne devrais pas pouvoir"},
            **self.as_user(self.outsider),
        )

        self.assertEqual(response.status_code, 403)

    def test_detail_includes_comments(self):
        self.client.post(
            f"/api/v1/tasks/{self.task.id}/comments/",
            {"content": "Premier commentaire"},
            **self.as_user(self.member),
        )

        response = self.client.get(f"/api/v1/tasks/{self.task.id}/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        comments = response.json()["comments"]
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["content"], "Premier commentaire")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.tasks.tests.test_comments.TaskCommentApiTests -v 2`
Expected: FAIL avec 404 sur `POST .../comments/` (l'action n'existe pas encore)

- [ ] **Step 3: Write minimal implementation**

Dans `apps/tasks/serializers.py`, ajouter en haut du fichier (avec les autres imports) :

```python
from .models import Task, TaskComment
```

Ajouter après `TaskSerializer` :

```python
class TaskCommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = TaskComment
        fields = ["id", "author", "content", "created_at"]


class TaskDetailSerializer(TaskSerializer):
    comments = TaskCommentSerializer(many=True, read_only=True)

    class Meta(TaskSerializer.Meta):
        fields = TaskSerializer.Meta.fields + ["comments"]


class TaskCommentCreateSerializer(serializers.Serializer):
    content = serializers.CharField()
```

Dans `apps/tasks/views.py`, mettre à jour les imports :

```python
from .serializers import (
    GlobalTaskStatsSerializer,
    ProjectUserStatsSerializer,
    TaskCommentCreateSerializer,
    TaskCommentSerializer,
    TaskCreateSerializer,
    TaskDetailSerializer,
    TaskInsightsSerializer,
    TaskSerializer,
)
from .services import (
    InvalidTransitionError,
    TaskPermissionError,
    add_comment,
    assign_task,
    claim_task,
    complete_task,
    create_task,
    get_assigned_tasks_for_admin,
    get_global_task_stats,
    get_project_task_insights,
    get_project_user_stats,
    reject_task,
    rename_task,
    start_task,
    update_task_description,
    validate_task,
)
```

Ajouter, juste après `filterset_class = TaskFilterSet` dans `TaskViewSet` :

```python
    def get_serializer_class(self):
        if self.action == "retrieve":
            return TaskDetailSerializer
        return super().get_serializer_class()
```

Ajouter une nouvelle action, à la suite de `complete` (fin de la classe) :

```python
    @action(detail=True, methods=["post"], url_path="comments")
    def comments(self, request, pk=None):
        task = self.get_object()
        serializer = TaskCommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            comment = add_comment(actor=request.user, task=task, **serializer.validated_data)
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except InvalidTransitionError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(TaskCommentSerializer(comment).data, status=201)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.tasks.tests.test_comments -v 2`
Expected: PASS (7 tests au total dans ce fichier)

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `python manage.py test`
Expected: tous les tests passent (368 avant cette passe + les nouveaux)

- [ ] **Step 6: Commit**

```bash
git add apps/tasks/serializers.py apps/tasks/views.py apps/tasks/tests/test_comments.py
git commit -m "feat(tasks): expose POST /api/v1/tasks/{id}/comments/ and nested comments on retrieve"
```

---

### Task 4: Types + client API frontend

**Files:**
- Modify: `frontend/src/types/watodo.ts`
- Modify: `frontend/src/api/client.ts`

**Interfaces:**
- Consumes: réponses JSON de `TaskCommentSerializer`/`TaskDetailSerializer` (Task 3).
- Produces: `TaskComment`, `TaskDetail` (types), `getTask(taskId: string): Promise<TaskDetail>`, `addTaskComment(taskId: string, content: string): Promise<TaskComment>` — consommés par Task 5.

- [ ] **Step 1: Add the types**

Dans `frontend/src/types/watodo.ts`, ajouter `can_comment: boolean;` à `TaskPermissions` (après `can_edit_description`).

Ajouter après l'interface `Task` (juste avant `export interface IncidentPermissions`) :

```typescript
export interface TaskComment {
  id: string;
  author: User;
  content: string;
  created_at: string;
}

export interface TaskDetail extends Task {
  comments: TaskComment[];
}
```

- [ ] **Step 2: Add the client functions**

Dans `frontend/src/api/client.ts`, ajouter `TaskComment` et `TaskDetail` à l'import de types en haut du fichier (liste alphabétique déjà en place).

Ajouter, à la suite des fonctions `getTasks`/existantes de `apps.tasks` dans ce fichier (regrouper avec les autres fonctions tâches) :

```typescript
export function getTask(taskId: string): Promise<TaskDetail> {
  return getJson<TaskDetail>(`/tasks/${taskId}/`);
}

export function addTaskComment(taskId: string, content: string): Promise<TaskComment> {
  return postJson<TaskComment>(`/tasks/${taskId}/comments/`, { content });
}
```

- [ ] **Step 3: Verify the frontend compiles**

Run: `cd frontend && npm run build`
Expected: build réussi, aucune erreur TypeScript (les nouveaux types/fonctions ne sont pas encore consommés, donc pas d'erreur d'usage à ce stade)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/watodo.ts frontend/src/api/client.ts
git commit -m "feat(tasks): add TaskComment/TaskDetail types and client functions"
```

---

### Task 5: Brancher `TaskAccordion` et `TasksListPage`

**Files:**
- Modify: `frontend/src/features/tasks/TaskAccordion.tsx`
- Modify: `frontend/src/features/tasks/TasksListPage.tsx`

**Interfaces:**
- Consumes: `getTask`, `addTaskComment` (Task 4), `TaskComment` (Task 4).
- Produces: rien de nouveau consommé ailleurs — dernier maillon de la chaîne.

- [ ] **Step 1: Update `TaskAccordion` props**

Dans `frontend/src/features/tasks/TaskAccordion.tsx`, ajouter l'import :

```typescript
import type { Task, TaskComment, User } from "../../types/watodo";
```

Ajouter à `TaskAccordionProps` (à la suite de `onSaveDescription`) :

```typescript
  comments: TaskComment[] | null;
  commentsError: string | null;
  commentSubmitting: boolean;
  onAddComment: (content: string) => void;
```

Ajouter aux paramètres déstructurés de la fonction (même liste).

- [ ] **Step 2: Replace the static "Commentaires" section**

Ajouter au début du corps de la fonction, avec `assigneeSelection` :

```typescript
  const [draft, setDraft] = useState("");

  function handleSubmitComment() {
    if (!draft.trim()) return;
    onAddComment(draft.trim());
    setDraft("");
  }
```

Remplacer la section entière :

```tsx
        <section className="task-accordion__section">
          <h3 className="task-accordion__section-title">Commentaires</h3>
          <p className="task-accordion__empty">Aucun commentaire pour l'instant.</p>
          <div className="task-accordion__comment-composer">
            <textarea
              className="task-accordion__comment-input"
              placeholder="Ajouter un commentaire…"
              rows={2}
              disabled
            />
            <button type="button" className="task-accordion__comment-submit" disabled>
              Publier
            </button>
          </div>
          <p className="task-accordion__meta-note">Fonctionnalité à venir — l'API ne le supporte pas encore.</p>
        </section>
```

par (structure identique à `IncidentAccordion.tsx`, lignes 173-219, classes `task-accordion__*` déjà stylées en CSS — mêmes règles que `incident-accordion__*`) :

```tsx
        <section className="task-accordion__section">
          <h3 className="task-accordion__section-title">Commentaires</h3>

          {comments === null && !commentsError && <p className="task-accordion__empty">Chargement…</p>}
          {commentsError && <p className="task-accordion__error">{commentsError}</p>}
          {comments !== null && comments.length === 0 && (
            <p className="task-accordion__empty">Aucun commentaire pour l'instant.</p>
          )}
          {comments !== null && comments.length > 0 && (
            <ul className="task-accordion__comment-list">
              {comments.map((comment) => (
                <li key={comment.id} className="task-accordion__comment">
                  <div className="task-accordion__comment-meta">
                    <span className="task-accordion__comment-author">{displayName(comment.author)}</span>
                    <time dateTime={comment.created_at} title={new Date(comment.created_at).toLocaleString("fr-FR")}>
                      {new Date(comment.created_at).toLocaleDateString("fr-FR")}
                    </time>
                  </div>
                  <p className="task-accordion__comment-content">{comment.content}</p>
                </li>
              ))}
            </ul>
          )}

          {task.permissions.can_comment && (
            <div className="task-accordion__comment-composer">
              <textarea
                className="task-accordion__comment-input"
                placeholder="Ajouter un commentaire…"
                rows={2}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                disabled={commentSubmitting}
              />
              <button
                type="button"
                className="task-accordion__comment-submit"
                onClick={handleSubmitComment}
                disabled={commentSubmitting || !draft.trim()}
              >
                {commentSubmitting ? "Publication…" : "Publier"}
              </button>
            </div>
          )}
        </section>
```

Ajouter les classes CSS manquantes à `frontend/src/features/tasks/TaskAccordion.css` (copier depuis `IncidentAccordion.css` les règles `.incident-accordion__comment-*`/`.incident-accordion__error`, renommées en `.task-accordion__comment-*`/`.task-accordion__error` — mêmes valeurs, ce sont déjà les mêmes tokens).

- [ ] **Step 3: Wire state and fetching in `TasksListPage`**

Dans `frontend/src/features/tasks/TasksListPage.tsx`, ajouter à l'import de `../../api/client` : `addTaskComment`, `getTask`.

Ajouter à l'import de types : `TaskComment`.

Ajouter après `const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null);` :

```typescript
  const [comments, setComments] = useState<TaskComment[] | null>(null);
  const [commentsError, setCommentsError] = useState<string | null>(null);
  const [commentSubmitting, setCommentSubmitting] = useState(false);
```

Ajouter un effet (même emplacement relatif que dans `IncidentsPage.tsx`, après les effets de chargement existants) :

```typescript
  useEffect(() => {
    if (!expandedTaskId) return;
    let cancelled = false;
    setComments(null);
    setCommentsError(null);

    getTask(expandedTaskId)
      .then((data) => {
        if (!cancelled) setComments(data.comments);
      })
      .catch(() => {
        if (!cancelled) setCommentsError("Impossible de charger les commentaires.");
      });

    return () => {
      cancelled = true;
    };
  }, [expandedTaskId]);
```

Ajouter un handler, à côté de `handleSaveDescription` :

```typescript
  async function handleAddComment(content: string) {
    if (!expandedTaskId) return;
    setCommentSubmitting(true);
    setCommentsError(null);
    try {
      const comment = await addTaskComment(expandedTaskId, content);
      setComments((current) => (current ? [...current, comment] : [comment]));
    } catch (err) {
      setCommentsError(err instanceof Error ? err.message : "L'ajout du commentaire a échoué.");
    } finally {
      setCommentSubmitting(false);
    }
  }
```

- [ ] **Step 4: Pass the new props to `TaskAccordion`**

Dans le JSX qui rend `<TaskAccordion ... />`, ajouter :

```tsx
                              comments={comments}
                              commentsError={commentsError}
                              commentSubmitting={commentSubmitting}
                              onAddComment={handleAddComment}
```

- [ ] **Step 5: Verify the frontend compiles**

Run: `cd frontend && npm run build`
Expected: build réussi, aucune erreur TypeScript

- [ ] **Step 6: Manual smoke test**

Démarrer `python manage.py runserver` et `npm run dev`, ouvrir l'écran "Tâches", déplier une tâche dont on est membre du projet, vérifier : la section Commentaires charge (vide au départ), publier un commentaire l'affiche immédiatement, recharger la page le montre toujours là.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/tasks/TaskAccordion.tsx frontend/src/features/tasks/TaskAccordion.css frontend/src/features/tasks/TasksListPage.tsx
git commit -m "feat(tasks): wire real comments into TaskAccordion/TasksListPage"
```

---

## Self-Review

**Spec coverage :** "Commentaires pas rajoutables sur des tâches" → couvert intégralement (modèle, service, endpoint, UI). Pas d'édition/suppression de commentaire ajoutée — hors demande, cohérent avec le comportement déjà accepté côté incidents.

**Placeholder scan :** aucun "TODO"/"à compléter" — chaque step contient le code réel à écrire.

**Type consistency :** `add_comment(*, actor, task, content)` (Task 2) ↔ appelé `add_comment(actor=request.user, task=task, **serializer.validated_data)` (Task 3, `validated_data` ne contient que `content`) ↔ `TaskComment`/`TaskDetail` (Task 4) ↔ `comments`/`commentsError`/`commentSubmitting`/`onAddComment` (Task 5) — noms cohérents de bout en bout, alignés sur les noms déjà utilisés côté incidents pour ne pas introduire de divergence de vocabulaire entre les deux features jumelles.
