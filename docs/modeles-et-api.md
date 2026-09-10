# Awtodo — Modèles fonctionnels & API

Détail des modèles de données et des endpoints. Référencé depuis CLAUDE.md — lire seulement les sections pertinentes à la tâche en cours, pas le fichier entier par défaut.

## Modèles fonctionnels clés (première ébauche)

### Project
- Nom, description, type (`individuel` / `collaboratif`)
- **Statut : `actif` / `clôturé` (implémenté — session du 06/08/2026).** Remplace le placeholder `actif`/`archivé` jamais construit côté UI jusqu'ici — `clôturé` est le terme métier retenu (action délibérée d'un chef de projet marquant le projet comme terminé), pas un renommage cosmétique. Toujours aucune suppression physique : un projet clôturé reste consultable, avec ses tâches/versions/historique intacts.
- Catégorisation : deadline et/ou priorité pour la roadmap
- **`already_in_production`** (booléen, défaut `False`, choisi à la création — session du 2026-09-10) : le projet suit quelque chose de déjà en ligne (maintenance/évolutions), **pas de date de livraison cible**. Incompatible avec `deadline` (`create_project` rejette les deux à la fois). Pas d'écran d'édition après coup, comme `project_type`.
- **`team`** (FK vers `Team`/Groupe) : obligatoire si `collaboratif`, interdit (null) si `individuel` — voir section "Groupes"

### ProjectMembership
- Utilisateur × Projet × Rôle
- Rôles possibles : `chef_de_projet`, `membre`, `lecteur` (lecture seule — session du 2026-09-10, voir `docs/organisation-et-comptes.md` > "Rôle Lecteur")
- **Un projet peut avoir plusieurs chefs de projet simultanément**
- **Contrainte (projets collaboratifs uniquement) :** l'utilisateur doit déjà être membre du `Team`/Groupe attribué au projet — voir section "Groupes"

### ProjectVersion (implémenté — session du 06/08/2026)

**Statut : implémenté.** Un projet peut avoir plusieurs versions (ex. "v1.0", "Sprint 3" — libellé libre, pas de format imposé). Une tâche s'attribue toujours à la **version courante** du projet au moment de sa création.

- `project` (FK), `label` (texte libre), `is_current` (booléen), `created_at`, `created_by` (FK `User`).
- **Une seule version courante à la fois par projet.** Créer une nouvelle version la fait automatiquement devenir la courante (bascule la précédente) — pas de toggle manuel séparé, l'action "créer une version" et "en faire la courante" sont la même action.
- **Création réservée aux chefs de projet** du projet concerné.
- **Migration de données :** chaque `Project` existant reçoit une version initiale (`label="v1"`, `is_current=True`) créée automatiquement, et toutes ses `Task` existantes y sont rattachées rétroactivement.
- **Sélecteur de version** dans l'onglet Tâches (Kanban et Roadmap partagent le même sélecteur) : la version courante est affichée par défaut ; consulter une version passée est possible mais **informationnel** — la création de nouvelles tâches cible toujours la version courante, quelle que soit la version actuellement affichée à l'écran (évite la confusion "je crée une tâche en regardant une vieille version").
- **Jamais de suppression de version** — cohérent avec la règle transverse.

### Task
- Projet parent
- **Version du projet** (FK `ProjectVersion`, voir ci-dessus) — attribuée automatiquement à la version courante du projet au moment de la création, jamais choisie manuellement.
- Titre, description
- **Type** : `CORRECTION` / `AJOUT` / `ÉVOLUTION`
- **Priorité** : niveau configurable (basse/moyenne/haute/critique — à affiner)
- Deadline optionnelle
- Assigné à (utilisateur)
- **Temps passé** : champ numérique simple, saisi manuellement à la clôture de la tâche (pas de pointage par session en v1)
- **Origine** : création manuelle (chef de projet ou membre) ou création automatique via API (ticketing)
- Référence externe (ID du ticket d'origine si applicable)
- **Statut** — voir cycle de vie détaillé ci-dessous

### Cycle de vie du statut d'une tâche

Trois flux de création possibles, chacun aboutissant à un statut initial différent :

| Créateur | Action | Statut résultant |
|---|---|---|
| Chef de projet | Crée + attribue directement à un membre | `assignée` |
| Chef de projet | Crée sans attribuer | `disponible` |
| Membre / développeur | Crée une tâche | `en_attente_validation` |
| N'importe qui | Crée une tâche sur un projet **`individuel`** sans assigné explicite (session du 2026-09-10) | `assignée` au créateur — une seule personne travaille sur un projet individuel, toute tâche lui revient. Un assigné fourni explicitement via l'API est respecté ; le reste des règles ci-dessus s'applique ensuite (le créateur d'un projet individuel est chef de projet). |

Transitions :

```
en_attente_validation
   ↓ validation par un chef de projet     ↓ rejet par un chef de projet
disponible / assignée                     rejetée  (conservée, jamais supprimée, motif de rejet à prévoir)
   ↓ (auto-attribution libre par un membre, OU attribution directe par un chef)
assignée
   ↓
en_cours
   ↓ (le membre marque la tâche comme faite)
archivée  (jamais supprimée — historique permanent, base des statistiques)
```

Points importants sur ce cycle :
- La pool `disponible` est **auto-assignable librement par n'importe quel membre du projet**, sans validation supplémentaire (la validation a déjà eu lieu, ou la tâche vient directement d'un chef de projet).
- La validation d'une tâche en `en_attente_validation` doit permettre au chef de projet soit de simplement valider (→ `disponible`), soit de valider ET assigner en une seule action (→ `assignée`).
- Le rejet aboutit toujours à un statut terminal `rejetée`, jamais à une suppression.

### Incident

**Entité séparée du modèle `Task`**, pas un simple type de tâche. Remonté par un utilisateur ou constaté par un développeur après mise en production. Généralement prioritaire sur les tâches d'évolution.

- **Rattachement (implémenté — session du 07/08/2026) : soit `project`, soit `team`, jamais les deux, jamais aucun des deux.** Les deux champs sont nullable en base (`null=True, blank=True`) — l'invariant XOR est une règle service-layer (`create_incident`, `apps/incidents/services.py`), pas une contrainte DB, cohérent avec le pattern déjà en place pour `create_project` (type de projet → champ `team` conditionnellement requis). Motivation : l'outil de ticketing externe (pas encore branché) pourra créer un incident sans connaître de projet Awtodo précis, en renseignant seulement le groupe concerné (obligatoire côté outil externe, pas dans le modèle Awtodo) — voir "Boîte de réception des incidents non-affectés" ci-dessous.
- Titre, description
- Priorité
- Statut : `signalé` → `en_cours` → `résolu` → `archivé` (jamais supprimé)
- **`assigned_to`** (implémenté — session du 11/08/2026) : `User` nullable, `on_delete=PROTECT`. N'existait pas avant cette session (voir "Différence volontaire avec les tâches" ci-dessous, nuancée depuis) — sert uniquement de prérequis au changement de priorité, ne restreint aucune des transitions de statut existantes (`start`/`resolve`/`archive` restent ouvertes à tout membre du groupe, inchangé).
- **Écran dédié séparé des tâches** côté frontend — ne pas mélanger les deux dans les mêmes vues/listes, même si le modèle de données peut partager des composants communs (mixins de statut, etc.)

#### Boîte de réception des incidents non-affectés (implémenté — session du 07/08/2026)

Un incident créé avec `team` seul (`project=None`) n'apparaît **jamais** dans la liste "par projet" (`GET /api/v1/incidents/`, scopée par `accessible_projects` — `project__in=...` exclut naturellement les lignes `project=NULL`). Il est visible uniquement via un nouvel endpoint dédié :

- `GET /api/v1/incidents/inbox/` — incidents `project=NULL` dont le `team` fait partie des groupes accessibles à l'acteur (`accessible_inbox_teams`, `apps/incidents/services.py` : admin plateforme voit tout, sinon uniquement les groupes où l'appartenance `TeamMembership` est active — même logique que `accessible_projects`, côté groupe). Réutilise `IncidentFilterSet` tel quel (filtre de statut par défaut inclus).
- `POST /api/v1/incidents/{id}/assign-project/` (body `{"project": "<uuid>"}`) — réassigne un incident non-affecté vers un projet : `incident.team` repassé à `None`, `incident.project` renseigné. Autorisation à deux niveaux : membre du groupe source de l'incident (403 sinon), **et** membre du projet de destination (403 sinon — même règle d'appartenance que partout ailleurs dans cette app, `_is_member_via_project` : pour un projet collaboratif, l'appartenance au groupe du projet suffit, pas besoin d'une `ProjectMembership` individuelle). 400 si l'incident avait déjà un projet. Une fois réassigné, l'incident quitte définitivement la boîte de réception (pas de chemin retour — non demandé).
- Nouveau flag `can_assign_project` dans `permissions` (voir "Permissions API — flags calculés" ci-dessous) : vrai seulement pour un incident `team`-only dont l'acteur est membre du groupe. Le flag ne vérifie pas l'appartenance au projet de *destination* (inconnue à ce stade) — c'est la transition elle-même qui la vérifie à la soumission.
- Frontend : section "Boîte de réception" sur l'écran Incidents global (jamais dans l'onglet Incidents d'un projet), visible seulement si l'utilisateur appartient à au moins un groupe et que la boîte n'est pas vide ; colonne "Groupe" (résolue via `team_name`, `SerializerMethodField`) à la place de "Projet". Réassignation depuis le drawer de détail (`IncidentDrawer`) : sélecteur de projet + bouton "Rattacher au projet", sur le même schéma que l'attribution de tâche (`TaskDrawer`, session du 06/08/2026).
- Le formulaire de création manuelle "Signaler un incident" (`IncidentCreateDialog`) reste **project-only**, délibérément — pas de choix de groupe ajouté côté UI. La contrainte de groupe ne s'applique qu'au flux ticketing externe à venir (toujours pas branché, app `integrations`).
- Résout la tension documentée dans "Scoping des listes par appartenance" ci-dessous : les fonctions de garde de `apps/incidents/services.py` (`_ensure_can_start`/`resolve`/`archive`/`comment`/`assign_project`) prennent désormais l'**incident** (`_require_member(actor, incident)`), pas son projet — l'autorisation suit `incident.team` s'il est renseigné, sinon `incident.project` (avec le fallback groupe existant pour les projets collaboratifs). `IncidentViewSet.get_queryset()` distingue `list` (scoping projet uniquement, inchangé) des actions de détail (`retrieve`/`start`/`resolve`/`archive`/`comments`/`assign-project`, qui résolvent aussi les incidents non-affectés pour un membre autorisé de leur groupe — sinon `self.get_object()` 404 systématiquement sur tout incident de la boîte de réception).

### BudgetEntry (évolution future — non développée en v1)

Le modèle (temps passé × coût horaire) doit rester prévu structurellement dans le schéma dès le départ, sans être implémenté fonctionnellement en v1.

## API — endpoints de transition de statut (tâches)

**Statut : acté. Complète le cycle de vie déjà documenté dans "Cycle de vie du statut d'une tâche" (section Modèles fonctionnels) — chaque transition devient un endpoint dédié, pas une simple mise à jour de champ.**

| Endpoint | Rôle requis | Effet |
|---|---|---|
| `POST /api/v1/tasks/` | membre du projet | crée la tâche, statut initial déterminé par le rôle du créateur (chef de projet avec assigné → `assignée` ; chef de projet sans assigné → `disponible` ; membre → `en_attente_validation`) |
| `POST /api/v1/tasks/{id}/validate/` | chef de projet | `en_attente_validation` → `disponible` (ou `assignée` si un assigné est fourni dans le body) |
| `POST /api/v1/tasks/{id}/reject/` | chef de projet | `en_attente_validation` → `rejetée`, motif obligatoire |
| `POST /api/v1/tasks/{id}/claim/` | membre du projet | `disponible` → `assignée` (auto-attribution ; échoue si la tâche n'est pas en `disponible`) |
| `POST /api/v1/tasks/{id}/assign/` | chef de projet | attribution manuelle à un membre, peu importe le statut de départ (`disponible` ou réassignation) |
| `POST /api/v1/tasks/{id}/start/` | assigné actuel | `assignée` → `en_cours` |
| `POST /api/v1/tasks/{id}/complete/` | assigné actuel **ou** chef de projet | `en_cours` → `archivée`, avec saisie du temps passé |
| `POST /api/v1/tasks/{id}/rename/` | membre du projet | modifie le titre |
| `POST /api/v1/tasks/{id}/update-description/` (session du 08/08/2026) | membre du projet | modifie la description — même garde que `rename` (`_ensure_can_rename`, flag `can_edit_description` = `can_rename`), vide autorisé |

**Règle d'implémentation :** chaque transition est une fonction dans `services.py` (règle déjà actée plus haut dans ce fichier), qui centralise le contrôle de rôle et la validation du statut de départ. Pas de logique de transition dupliquée dans les vues DRF — la vue appelle le service, rien de plus.

**Correction — clôture par un chef de projet (session du 2026-08-06)** : remontée client, `complete_task`/`_ensure_can_complete` réservait la clôture au seul assigné actuel, empêchant un chef de projet de clôturer une tâche qu'il n'avait pas assignée à lui-même. `_ensure_can_complete` autorise désormais l'assigné actuel **ou** un chef de projet du projet (`_is_manager`) — `start` reste, lui, réservé au seul assigné (pas demandé, portée volontairement limitée à `complete`). La réattribution d'une tâche déjà assignée (`assign`, ligne ci-dessus) fonctionnait déjà correctement (`_ensure_can_assign` accepte `disponible` et `assignée` comme statuts de départ) — vérifié, pas de correctif nécessaire sur ce point. Le flag `can_complete` (une seule source de vérité, voir "Permissions API — flags calculés") reflète le changement automatiquement ; aucune modification frontend requise, `TaskDrawer`/`isDropAllowed` lisaient déjà `task.permissions.can_complete` plutôt que de recalculer "assigné == utilisateur courant".

**Correction — interface d'attribution manquante côté frontend (session du 2026-08-06)** : suite au correctif ci-dessus, remontée client complémentaire — l'endpoint `assign` (déjà fonctionnel côté backend, y compris pour réattribuer une tâche déjà assignée) n'avait **aucune interface** côté frontend : ni pour la première attribution manuelle par un chef de projet, ni pour la réattribution. `TaskDrawer` gagne une section "Attribution" : affichage de l'assigné actuel (ou "Non assignée"), et — visible uniquement si `task.permissions.can_assign` est vrai — un sélecteur de membre + bouton "Assigner"/"Réattribuer" (le libellé du bouton dépend de la présence d'un assigné actuel), désactivé si aucune sélection ou si la sélection correspond déjà à l'assigné en cours. `handleAssign` ajouté à `useTaskTransitions` (hook partagé, voir "Vue Roadmap" > précisions) et branché dans les trois consommateurs de `TaskDrawer` (`KanbanBoard`, `RoadmapView`, `TasksListPage`) — chacun fournit sa propre liste `assignableUsers`, scopée aux membres du projet concerné (voir correction suivante, même principe de scoping).

**Correction — liste d'assignation non filtrée par membres du projet (session du 2026-08-06)** : remontée client, `TaskCreateDialog` (formulaire de création de tâche) affichait **tous les utilisateurs de la plateforme** dans le champ "Assigné à", pas seulement les membres du projet concerné — `KanbanBoard` lui passait la liste globale issue de `useCurrentUser()` (utilisée par ailleurs pour le sélecteur de démo utilisateur, pas pertinente ici). Corrigé : `KanbanBoard`/`RoadmapView` dérivent désormais une liste `projectMembers = project.members.map(m => m.user)` (déjà disponible sur l'objet `Project`, aucun nouvel appel API) et la passent à la place — même liste réutilisée pour `assignableUsers` de `TaskDrawer` (correction ci-dessus). Pour `TasksListPage` (vue transverse multi-projets), la liste est recalculée par tâche à l'ouverture du tiroir, à partir du projet correspondant dans `projects` (déjà chargé pour l'affichage de la colonne "Projet").

**Référence externe (ticket) sur `POST /api/v1/tasks/` :** ce champ est **facultatif**. Une tâche créée manuellement (par un chef de projet ou un membre, via le front) n'a pas de référence externe — c'est un cas normal, pas une donnée manquante. Seules les tâches créées automatiquement via l'API ticketing renseignent ce champ.

**`POST /api/v1/tasks/{id}/rename/` (ajouté le 2026-08-04, édition inline) :** ce n'est pas une transition de statut — modifie uniquement le titre, à n'importe quel statut. Rôle requis : membre du projet (pas réservé à l'assigné, un correctif de titre n'a pas besoin d'être gardé aussi étroitement qu'une transition de cycle de vie).

**`GET /api/v1/tasks/assigned-to/{user_id}/` (implémenté — session du 06/08/2026) :** contourne délibérément le scoping par appartenance habituel — voir docs/organisation-et-comptes.md > "Membres (organisation)" pour le contexte produit (fiche utilisateur de l'écran Administration). Réservé à `organisation_role=admin`, uniquement pour un utilisateur de sa propre organisation (`apps.tasks.services.get_assigned_tasks_for_admin`, même pattern "fonction de garde" que le reste). Renvoie uniquement les tâches actives (`Task.objects.active()`) assignées à l'utilisateur — volontairement une vue de **charge de travail courante**, pas un historique complet (les tâches archivées n'y figurent pas). Route enregistrée via `@action(detail=False, methods=["get"], url_path="assigned-to/(?P<user_id>[^/.]+)")` sur `TaskViewSet` plutôt qu'un endpoint séparé dans `apps.accounts` : `apps.accounts` ne peut pas importer `apps.tasks` (hiérarchie de dépendances), alors que `apps.tasks` a déjà le droit d'importer `apps.accounts.models.User`.

## ⚠️ Mécanisme d'identification temporaire (dev uniquement — SSO pas encore implémenté)

Le SSO/gestion de comptes est volontairement mis en dernier dans la roadmap — la logique métier est construite et testée avant l'authentification réelle. Pour permettre de tester les endpoints de transition de statut (qui dépendent du rôle de l'acteur) sans attendre le SSO :

- Un header custom **`X-Debug-User-Id`**, lu par une authentication class DRF dédiée, permet de simuler "je suis cet utilisateur" en environnement de dev.
- **Cette authentication class doit être strictement conditionnée à `DEBUG=True`** (ou équivalent variable d'environnement dev) — jamais active en staging/production. À vérifier explicitement dans les tests (un test doit confirmer que le header est ignoré si `DEBUG=False`).
- Le rôle (chef de projet / membre) continue d'être déduit normalement via `ProjectMembership` une fois l'utilisateur identifié par ce header — toute la logique de permission par rôle déjà conçue reste valable telle quelle. Seul le mécanisme d'identification de l'utilisateur changera quand le vrai SSO sera implémenté (remplacement du header par le token JWT/OIDC réel), pas la logique de permissions elle-même.
- Le sélecteur "Aucun utilisateur" déjà présent dans la topbar du front (`UserMenu`) sert de point d'entrée pour choisir quel utilisateur de test simuler via ce header. **Depuis l'ajout du login réel (session du 2026-08-06, voir "Authentification par mot de passe"), la connexion est devenue la porte d'entrée obligatoire du site** (`App.tsx` : tant qu'aucun `currentUser` n'existe — ni connexion réelle, ni sélection démo — seul l'écran de connexion s'affiche, plus de navigation "en observateur" sans identité). Le même sélecteur "mode démo" est donc désormais dupliqué sur `LoginPage.tsx` (liste inline plutôt que menu déroulant, rendu différent, logique identique) pour rester atteignable dès ce premier écran — sinon un testeur n'ayant pas encore de compte réel n'aurait plus aucun moyen d'entrer dans l'app. Choisir un utilisateur ici (ex. un compte `is_platform_admin=True` pour tester avec tous les droits) appelle `setCurrentUserId`, exactement comme depuis `UserMenu`.
- **Ce mécanisme est temporaire par nature** — à retirer explicitement (pas juste désactiver) une fois le SSO réel implémenté. Ne pas le laisser traîner dans le code par la suite.

**⚠️ Piège CORS à connaître (trouvé et corrigé le 2026-08-04) :** `django-cors-headers` n'autorise par défaut qu'un jeu standard de headers — `X-Debug-User-Id` n'en fait pas partie. Comme ce header est attaché à **toutes** les requêtes du front dès qu'un utilisateur de démo est sélectionné (persisté en `localStorage`), sans `CORS_ALLOW_HEADERS` explicite dans `config/settings/dev.py`, le preflight CORS du navigateur rejette silencieusement absolument tout — projets, tâches, incidents ne chargent plus, création impossible. **`curl` ne révèle jamais ce genre de panne** (il n'est pas soumis à CORS) : un diagnostic doit simuler un vrai preflight (`curl -X OPTIONS` avec `Origin`/`Access-Control-Request-Headers`) pour le voir. Fix : `CORS_ALLOW_HEADERS = [*default_headers, "x-debug-user-id"]` dans `dev.py`.

## API — création de projets

**Statut : acté. Résout le point d'architecture laissé ouvert sur "qui devient chef de projet à la création".**

| Endpoint | Rôle requis | Effet |
|---|---|---|
| `POST /api/v1/projects/` | tout utilisateur authentifié | crée le projet (nom, description, type `individuel`/`collaboratif`, `deadline`/`priority` optionnels, `already_in_production` optionnel — exclusif de `deadline`) ; **le créateur devient automatiquement `chef_de_projet`** via une `ProjectMembership` créée dans le même service — jamais de projet sans au moins un chef de projet |

**Règle d'implémentation :** comme pour les tâches, la logique (création du projet + création de la `ProjectMembership` du créateur) est une seule fonction dans `services.py` (`apps/projects/services.py`), pas répartie entre serializer et vue.

**Scope volontairement restreint :** cette passe couvre uniquement la création. L'ajout d'autres membres à un projet collaboratif (endpoint `POST /api/v1/projects/{id}/members/`, réservé aux chefs de projet) est le chantier suivant — sans lui, un projet collaboratif reste mono-utilisateur en pratique, mais on préfère ne pas mélanger les deux sujets dans une même passe.

## API — clôture de projet et versions (implémenté — session du 06/08/2026)

| Endpoint | Rôle requis | Effet |
|---|---|---|
| `POST /api/v1/projects/{id}/close/` | chef de projet du projet | `status` → `clôturé` |
| `POST /api/v1/projects/{id}/reopen/` | chef de projet du projet | `status` → `actif` (réouverture possible, pas un aller simple) |
| `POST /api/v1/projects/{id}/versions/` | chef de projet du projet | crée une `ProjectVersion`, devient automatiquement la version courante |
| `GET /api/v1/projects/{id}/versions/` | membre du projet | liste les versions (pour le sélecteur) |

**Liste des projets :** filtre par défaut sur `status=actif`, filtrable pour inclure aussi `clôturé` — voir "Filtre d'état généralisé" ci-dessous, même pattern que pour tâches/incidents.

**Précisions actées à l'implémentation :**
- **Valeur DB renommée `archive` → `cloture`** (pas juste le libellé) : l'ancien statut `archivé` de `Project` n'avait jamais été construit côté UI (aucune transition ne l'atteignait), donc pas de vraie donnée en jeu — migration de données défensive (`apps/projects/migrations/0010_rename_archive_to_cloture.py`) au cas où une ligne de seed/test l'utilisait, suivie de l'`AlterField` sur les `choices`.
- **`_ensure_can_close`/`_ensure_can_reopen`** (`apps/projects/services.py`) suivent le même pattern "fonction de garde" que le reste du projet (voir "Permissions API — flags calculés") — `close_project`/`reopen_project` les appellent et laissent l'exception remonter, `can_close`/`can_reopen` (nouveaux flags `permissions`) les appellent via `check_permission`.
- **`ProjectVersion`** : `created_by` nullable — nécessaire pour la migration de données de rétro-compatibilité (`apps/tasks/migrations/0004_backfill_project_versions.py`, qui crée la version "v1" de chaque projet existant sans acteur réel disponible). Un `UniqueConstraint` sur `(project, is_current=True)` garantit qu'il n'existe jamais deux versions courantes simultanées pour un même projet — `create_project_version` bascule l'ancienne à `is_current=False` avant de créer la nouvelle.
- **Invariant maintenu à deux endroits** : `apps.projects.services.create_project` crée désormais la version initiale "v1" automatiquement (pas seulement la migration de données pour les projets déjà existants) — sans ça, tout projet créé après cette passe n'aurait aucune version courante et `create_task` échouerait. **Limite assumée** : un `Project` créé en contournant ce service (ex. `Project.objects.create(...)` direct en shell/admin) n'a pas de version — non couvert par un signal (le projet préfère éviter les signaux pour de la logique métier, voir règle d'architecture n°1), vérifié manuellement lors du test E2E de cette session.
- **`apps.tasks.services.create_task`** attribue `version=get_current_version(project)` — jamais de paramètre `version` exposé côté `TaskCreateSerializer`/API, cohérent avec "jamais choisie manuellement".
- **`Task.version_label`** (`SerializerMethodField` sur `TaskSerializer`, via `source="version.label"`) : évite au frontend de résoudre la version par id pour un simple affichage.
- **`GET .../versions/` et `POST .../versions/`** cohabitent sur la même `@action(detail=True, methods=["get", "post"])` (`ProjectViewSet.versions`) plutôt que deux actions séparées — même URL, méthode HTTP différente, cohérent avec le tableau ci-dessus.

## Filtre d'état généralisé (implémenté — session du 06/08/2026)

**Statut : implémenté, remplace toute logique de filtre d'état ad hoc écrite précédemment.** Les entités en statut terminal/historique (archivé, rejeté, clôturé) ne doivent **jamais apparaître par défaut** dans une liste ou un tableau — mais doivent rester **retrouvables** via un filtre explicite, pas supprimées de la vue de façon définitive.

**Pattern UI unique, réutilisé partout :** une combobox multi-sélection "Afficher" avec une case à cocher par statut, état par défaut = seuls les statuts "actifs" cochés.

| Entité | Statuts visibles par défaut | Statuts masqués par défaut (filtrables) |
|---|---|---|
| Task | `en_attente_validation`, `disponible`, `assignée`, `en_cours` | `archivée`, `rejetée` |
| Incident | `signalé`, `en_cours`, `résolu` | `archivé` |
| Project | `actif` | `clôturé` |

**Conséquence sur le Kanban :** les colonnes correspondant à des statuts masqués par défaut (`archivée`, `rejetée`) ne s'affichent que si l'utilisateur les active via le filtre — pas de colonne vide en permanence comme c'était le cas jusqu'ici pour "Archivée".

**Précisions actées à l'implémentation :**
- **`apps.common.filters.DefaultActiveStatusFilterMixin`** : seule source de vérité pour la règle "absent → statuts actifs, présent → respecté tel quel", réutilisée par `TaskFilterSet`/`IncidentFilterSet`/`ProjectFilterSet` (chacun ne fournit que son propre `active_statuses`). Implémentée en surchargeant `filter_queryset()`, **pas** via un `method=` sur le filtre `status` lui-même — piège découvert en cours de route : django-filter court-circuite un filtre `method=` dès que la valeur reçue est "vide" au sens de ses `EMPTY_VALUES` (`[]` pour un `MultipleChoiceFilter` sur un paramètre absent en fait partie), donc la méthode n'était **jamais appelée** dans le cas justement le plus important (absence du paramètre) — testé et confirmé en écrivant `apps/projects/tests/test_scoping.py::ProjectStatusFilterApiTests` avant de comprendre la cause exacte.
- **Bascule de queryset de base `.active()` → `all_objects`** dans `get_queryset()` des trois `ViewSet` (`Task`/`Incident`/`Project`) : nécessaire pour que le filtre puisse jamais renvoyer un statut terminal — sinon `status=archivee` resterait sans effet, la restriction `.active()` du manager par défaut les ayant déjà exclus en amont du filtre.
- **`ListOnlyFilterMixin`** (`apps/common/views.py`) : DRF applique `filterset_class` à `list()` **et** à `get_object()` (`GenericAPIView.get_object()` appelle `self.filter_queryset(...)` avant de résoudre le lookup) — sans ce mixin, le filtre par défaut empêcherait `retrieve()`/toute action détail (ex. `reopen` sur un projet `cloture`, dont le statut n'est justement pas dans le sous-ensemble actif par défaut) d'atteindre l'objet. Le filtrage par statut ne s'applique donc qu'à `self.action == "list"`.
- **Conséquence positive non demandée** : `accessible_projects()` (voir "Scoping des listes par appartenance") est devenue statut-agnostique dans la foulée de ce chantier — un projet clôturé reste consultable/accessible par appartenance, c'est uniquement `ProjectFilterSet` qui décide de l'inclure ou non dans la liste par défaut. Testé (`ProjectStatusFilterApiTests`, `AccessibleProjectsServiceTests.test_platform_admin_sees_active_and_closed_projects`) et vérifié en conditions réelles (`curl` sur serveur dev).
- **Kanban — colonne `rejetee` ajoutée** (`frontend/src/lib/taskTransitions.ts::KANBAN_COLUMNS`, 6 statuts désormais) : elle n'existait pas du tout auparavant (une tâche rejetée disparaissait simplement de l'écran). Comme les deux colonnes masquées par défaut (`archivee`/`rejetee`) ne s'affichent plus en permanence, la 5ᵉ colonne "Archivée" ajoutée lors d'une passe précédente uniquement comme cible de drop toujours vide n'a plus cette justification — elle se comporte maintenant comme une vraie colonne (peut lister des tâches réelles) quand l'utilisateur l'active.
- **Conséquence assumée sur le drag-and-drop** : la transition `en_cours → archivée` (glisser-déposer ouvrant le dialog de clôture) n'a plus de colonne cible visible tant que "Archivée" n'est pas cochée dans le filtre (masquée par défaut) — le bouton explicite "Clôturer" du drawer/de la carte reste la voie normale par défaut, cohérent avec "les colonnes de statuts masqués par défaut ne doivent plus s'afficher tant que l'utilisateur ne les active pas".
- **Roadmap non concernée par la combobox** : `RoadmapView` excluait déjà les tâches archivées/rejetées par construction (comportement documenté plus haut dans ce fichier, antérieur à ce chantier) — pas de filtre "Afficher" ajouté là, le comportement par défaut correspond déjà à ce que demande ce chantier.
- Tests dédiés : `apps/tasks/tests/test_status_filter.py`, `apps/incidents/tests/test_status_filter.py`, `apps/projects/tests/test_scoping.py::ProjectStatusFilterApiTests` (défaut masqué, filtre explicite, détail toujours atteignable).

## Correction — emplacement du Kanban (confusion de portée)

**Erreur de cadrage dans une passe précédente, corrigée ici :** le Kanban avec glisser-déposer doit vivre sur la **vue détail d'un projet** (accessible en cliquant sur un projet depuis l'écran Projets), scopé aux tâches de ce projet uniquement. L'écran **"Tâches" global** (accessible depuis la sidebar, toutes les tâches tous projets confondus) **reste une liste simple**, sans Kanban ni drag-and-drop — juste un tableau, avec le filtre décrit ci-dessous (section Groupes).

## Correction — périmètre du drag-and-drop dans le Kanban

**Constat :** un utilisateur a pu glisser une carte vers une colonne où il n'a pas la permission d'agir, découvrant l'erreur seulement après le drop ("Seul un membre du projet peut effectuer cette action"). Plus largement, le drag-and-drop n'est un bon pattern que pour une transition qui (a) ne nécessite aucune information supplémentaire et (b) a un acteur non ambigu. En reprenant les 7 transitions du cycle de vie des tâches sous cet angle :

| Transition | Info requise | Drag pertinent ? |
|---|---|---|
| `disponible → assignée` (claim/assign) | qui ? (soi-même ou un membre choisi) | Non — ambigu |
| `assignée → en_cours` (start) | aucune, l'acteur est déjà l'assigné | **Oui** |
| `en_cours → archivée` (complete) | temps passé | Partiel — le drag peut déclencher l'ouverture du dialog de saisie du temps, pas une complétion directe |
| `en_attente_validation → disponible/assignée` (validate) | valider seul, ou valider + assigner à qui ? | Non — ambigu |
| `→ rejetée` (reject) | motif obligatoire | Non — dialog nécessaire de toute façon |

**Décision actée :** le drag-and-drop du Kanban ne doit permettre que **`assignée → en_cours`** en glisser-déposer direct, et peut déclencher l'ouverture du dialog existant pour `en_cours → archivée` (le drop ouvre le dialog de saisie du temps, ne complète pas seul). **Toutes les autres transitions passent par des boutons d'action explicites** sur la carte ou dans le drawer de détail (déjà existants pour la plupart), pas par un glisser-déposer vers une colonne. Les colonnes qui ne correspondent à aucune transition valide en drag pour l'utilisateur courant doivent visuellement l'indiquer (zone de dépôt désactivée/grisée), plutôt que d'accepter le drop puis d'échouer après coup.

**Statut : implémenté (session du 2026-08-04).** Précisions actées à l'implémentation :
- Le Kanban n'avait que 4 colonnes (`en_attente_validation`/`disponible`/`assignee`/`en_cours`) — pas de colonne `archivée`, donc pas de cible de drop possible pour `en_cours → archivée`. Une 5ᵉ colonne "Archivée" a été ajoutée spécifiquement comme zone de dépôt (elle reste toujours vide visuellement : `TaskViewSet.queryset` utilise `Task.objects.active()`, qui exclut déjà les tâches archivées de la réponse API — la colonne existe uniquement pour recevoir le drop, pas pour lister quoi que ce soit).
- `claim`/`assign`/`validate`/`reject` ont été retirées de `DRAG_ACTIONS` (`frontend/src/lib/taskTransitions.ts`) — vérifié qu'aucune n'était perdue : toutes ont déjà un bouton explicite dans `TaskDrawer` (Valider/Rejeter/M'attribuer/Démarrer/Clôturer), donc rien à ajouter côté chantier 2.2.
- Grisage pendant un drag : `useDroppable({ disabled })` de `@dnd-kit/core` désactive nativement la colonne comme cible (le drop n'est pas juste refusé après coup, il n'est jamais accepté) — calculé via `isDropAllowed(task, toStatus)`, qui lit directement `task.permissions.can_start`/`can_complete` (pas de recalcul de rôle côté frontend, voir "Permissions API — flags calculés"). `can_start` reste vrai uniquement pour l'assigné actuel ; `can_complete` est vrai pour l'assigné actuel **ou** un chef de projet du projet (voir correctif du 2026-08-06 ci-dessus) — la colonne "Archivée" du Kanban est donc "droppable" pour un chef de projet même sur une tâche assignée à quelqu'un d'autre, automatiquement, sans changement de code frontend.

## API — endpoints Incidents

**Statut : acté. Complète le cycle de vie déjà documenté (section Modèles fonctionnels, `Incident`), actuellement en lecture seule côté backend.**

| Endpoint | Rôle requis | Effet |
|---|---|---|
| `POST /api/v1/incidents/` | membre du groupe attribué au projet **ou** du groupe direct (`team`, incident non-affecté — voir "Boîte de réception" ci-dessus) | crée l'incident, statut initial `signalé`. **Peut aussi être créé automatiquement via l'intégration ticketing** (voir note ci-dessous) — dans ce cas, pas de contrainte de groupe, l'appel vient du service account ticketing, pas d'un utilisateur. |
| `POST /api/v1/incidents/{id}/start/` | n'importe quel membre du groupe | `signalé` → `en_cours` |
| `POST /api/v1/incidents/{id}/resolve/` | n'importe quel membre du groupe | `en_cours` → `résolu` |
| `POST /api/v1/incidents/{id}/archive/` | n'importe quel membre du groupe | `résolu` → `archivé` (jamais supprimé) |
| `GET /api/v1/incidents/inbox/` (session du 07/08/2026) | membre du groupe | liste les incidents non-affectés (`project=NULL`) du/des groupe(s) de l'acteur |
| `POST /api/v1/incidents/{id}/assign-project/` (session du 07/08/2026) | membre du groupe source **et** du projet de destination | rattache un incident non-affecté à un projet, `team` repassé à `NULL` |
| `POST /api/v1/incidents/{id}/update-description/` (session du 08/08/2026) | membre du groupe concerné | modifie la description — même garde que `comments` (`_ensure_can_comment`, flag `can_edit_description`), vide autorisé |
| `POST /api/v1/incidents/{id}/claim/` (session du 11/08/2026) | n'importe quel membre du groupe | s'auto-assigne l'incident (`assigned_to = acteur`) — se réassigner à un autre membre écrase simplement l'assigné précédent, pas de restriction "déjà pris" |
| `POST /api/v1/incidents/{id}/update-priority/` (session du 11/08/2026), body `{"priority": "..."}` | **l'assigné actuel de l'incident**, ou un **administrateur du groupe concerné** (même définition que `apps.accounts.services.can_manage_team` : créateur du groupe, admin d'organisation ou de plateforme — pour un incident sur un projet individuel sans groupe, le chef de projet de ce projet joue ce rôle à la place) | modifie `priority` |

**Différence volontaire avec les tâches :** pas de notion d'assigné individuel ni de restriction "seul l'acteur assigné peut agir" — n'importe quel membre du groupe du projet peut faire avancer le **statut** d'un incident, à n'importe quelle étape. Plus permissif que le cycle de vie des tâches, assumé : la priorité sur un incident est la rapidité de traitement collectif, pas la traçabilité d'un acteur unique. **Nuancé depuis le 11/08/2026** : `assigned_to` existe désormais, mais seulement comme prérequis du changement de **priorité** (`claim` + `update-priority` ci-dessus) — le reste du cycle de vie (`start`/`resolve`/`archive`/commentaires/description) reste ouvert à tout membre du groupe, inchangé.

**Note — la création manuelle reste secondaire :** l'usage primaire attendu est la création automatique via l'intégration ticketing (un ticket créé côté ticketing → un incident créé sur Awtodo, même logique que pour les tâches). La création manuelle par un membre du groupe existe et doit être supportée, mais ce n'est pas le flux principal — ne pas sur-optimiser l'UI de création manuelle au détriment du flux API.

**Conséquence sur l'intégration ticketing :** le endpoint/webhook d'entrée ticketing (voir section "API / Intégration ticketing") doit pouvoir créer soit une `Task`, soit un `Incident`, selon le type du ticket d'origine — pas seulement des tâches comme décrit initialement. À préciser plus finement quand ce chantier sera lancé.

**Simulation en dev du service account ticketing (session du 11/08/2026) :** `User.is_service_account` (nouveau champ, `apps/accounts/models.py`) marque un compte technique. `IncidentViewSet.create` (`apps/incidents/views.py`) passe `actor=None` à `create_incident` quand `request.user.is_service_account` est vrai — déclenche exactement le même contournement de la contrainte de groupe que le futur appel système réel (voir `apps.incidents.services.create_incident`), au lieu d'être seulement un chemin mort inatteignable via HTTP. Utilisateur de seed dédié : `api.ticketing` (`apps/accounts/management/commands/seed_demo_users.py`, `SERVICE_ACCOUNT_USERS`) — à utiliser via `X-Debug-User-Id` pour tester la création automatique sans avoir besoin d'appartenir au groupe/projet visé. **Reste un mécanisme dev uniquement** (même portée que `X-Debug-User-Id` en général, voir "Mécanisme d'identification temporaire" ci-dessus) — pas une vraie clé API de service account, ce chantier restant hors périmètre (voir CLAUDE.md > "Stack technique" > Auth).

## Vue détail d'un incident + commentaires

**Statut : implémenté (session du 2026-08-04).** Fait sortir "commentaires" du hors-périmètre, mais uniquement pour les incidents — pas pour les tâches, qui restent hors-périmètre pour l'instant. Même logique de scope étroit que le reste du projet : ne pas généraliser aux tâches sans validation explicite.

**Précisions actées à l'implémentation :**
- `IncidentComment` n'hérite pas de `StatusLifecycleModel` — sans édition ni suppression possibles (pas d'endpoint pour ça), il n'y a jamais d'état "terminal" à distinguer d'un état "actif" : la règle "aucune suppression physique" est respectée par construction (aucun code ne supprime jamais une ligne), pas besoin du pattern manager actif/historique.
- `GET /api/v1/incidents/{id}/` utilise un serializer dédié (`IncidentDetailSerializer`, hérite de `IncidentSerializer` + `comments` imbriqués) — la liste (`GET /api/v1/incidents/`) continue d'utiliser le serializer sans commentaires, pour ne pas alourdir chaque ligne de la liste avec ses commentaires.
- `POST /api/v1/incidents/{id}/comments/` réutilise la même règle de permission que les transitions de statut (`_require_member` — membre du groupe du projet, ou du groupe direct pour un incident non-affecté depuis la session du 07/08/2026), 403 sinon.

### Contenu de la vue détail

**Révisé — session du 08/08/2026 : accordéon sous la ligne, plus un drawer latéral.** Clic sur un incident dans la liste → la ligne se déplie (`IncidentAccordion`, remplace l'ancien `IncidentDrawer`), même contenu, rendu en accordéon vertical dans le tableau plutôt qu'en overlay `position:fixed`. Affiche :
- Titre (reste dans la ligne du tableau, pas dans l'accordéon), description complète — **modifiable en inline** depuis cette session (`update-description`, voir tableau d'endpoints ci-dessus), clic direct sur le texte pour éditer
- Statut (badge), priorité, projet parent
- Date de création (`created_at`, déjà existant) + affichage du délai écoulé en relatif ("il y a 4h", "depuis 2 jours") — calculé côté front à partir de `created_at`, pas de nouveau champ backend nécessaire
- Les boutons d'action contextuels (Démarrer/Résoudre/Archiver) déjà présents sur la liste doivent être accessibles depuis l'accordéon — libre de garder aussi une action rapide sur la ligne de la liste en plus, tant que l'accordéon les propose également
- Zone de commentaires (liste + ajout)

Même conversion côté tâches (`TaskAccordion` remplace `TaskDrawer` **uniquement** dans l'écran "Tâches" — `TaskDrawer` reste utilisé tel quel par le Kanban et la Roadmap d'un projet, contextes en cartes où un drawer latéral reste pertinent, pas de raison de les convertir).

### Liste des incidents — affichage et tri

Le délai écoulé (relatif, même calcul que dans le drawer) doit aussi être **visible directement dans la liste** (nouvelle colonne), pas seulement dans le drawer de détail. La liste doit être **triable** sur deux colonnes :
- **Délai** : du plus récent au plus ancien (et l'inverse)
- **Priorité** : basse → critique (et l'inverse)

Tri géré côté front (les données sont déjà toutes chargées dans la liste, pas besoin d'un paramètre de tri côté API pour l'instant).

### Modèle `IncidentComment`

Nouveau modèle dans `apps/incidents` :
- `incident` (FK vers `Incident`)
- `author` (FK vers `User`)
- `content` (texte)
- `created_at`
- **Pas d'édition ni de suppression de commentaire en v1** — cohérent avec la règle transverse "aucune suppression physique" ; un commentaire posté est permanent.

### Endpoints

| Endpoint | Rôle requis | Effet |
|---|---|---|
| `GET /api/v1/incidents/{id}/` | membre du groupe du projet | détail complet de l'incident, avec les commentaires inclus (serializer imbriqué) |
| `POST /api/v1/incidents/{id}/comments/` | membre du groupe du projet | ajoute un commentaire |

## API / Intégration ticketing

**Flux principal :** création de ticket dans l'outil externe → création automatique de tâche Awtodo via API.

- Le **projet cible est choisi côté ticketing** au moment de la création du ticket.
- Si le ticket est catégorisé "autre" (ou pas de projet précisé) → la tâche atterrit dans une **boîte de réception par défaut** (à modéliser comme un projet système dédié), à trier manuellement ensuite par un chef de projet.
- Référence externe (ID du ticket) conservée sur la tâche Awtodo pour permettre un lien bidirectionnel futur (ex : notifier le ticketing quand la tâche est archivée).
- Toute création de tâche via API suit le **même cycle de vie de statut** que les tâches créées manuellement (à définir précisément quel flux s'applique par défaut — probablement équivalent à une création "chef de projet sans attribution" → `disponible`, à confirmer).

## Statistiques (implémenté — session du 2026-08-05, soir)

**Statut : implémenté.** Deux écrans distincts, portée différente : un onglet "Statistiques" par projet (hub projet, voir section dédiée plus bas) et un écran "Statistiques" global accessible depuis la sidebar.

### Onglet Statistiques (par projet)

- **Cards "stats projet"** : `tasks_total`/`tasks_done` — champs déjà exposés sur `ProjectSerializer` (calculés depuis avant ce chantier, voir "Roadmap"/`Project`), réutilisés tels quels côté frontend, aucun nouvel endpoint nécessaire pour cette partie.
- **Tableau "stats par membre"** : `GET /api/v1/tasks/project-stats/{project_id}/` (`apps.tasks.services.get_project_user_stats`) — `tasks_done` (statut `archivee`), `tasks_in_progress` (statut `en_cours`), `hours_spent` (`Sum(time_spent)` sur les tâches archivées de l'utilisateur, agrégation via `Task.all_objects` — le manager par défaut `.active()` exclurait justement les tâches archivées dont ce calcul a besoin).
  - **Permission (acté dans la demande) :** chef de projet → une ligne par membre actif du projet ; membre simple → une seule ligne, la sienne. Gardé par `_require_member` (403 si non-membre) ; la restriction "une seule ligne" n'est pas un filtre de statut caché côté frontend, c'est le service qui ne renvoie que `[actor]` si l'acteur n'est pas chef de projet — même principe que les autres flags calculés (une seule source de vérité côté `services.py`).

### Écran Statistiques (global, sidebar)

- `GET /api/v1/tasks/global-stats/` (`apps.tasks.services.get_global_task_stats`) — `projects_total`/`projects_active`/`projects_closed` + `tasks_done`/`tasks_in_progress`, sur **`contributor_projects(actor)`** (session du 2026-09-10 — un projet où l'acteur n'a qu'un droit de lecture n'entre pas dans ses stats globales, comme l'onglet Statistiques d'un projet lui est masqué).
- **Budgets** : `GET /api/v1/budgeting/summary/` (voir section "Budgétisation" ci-dessous) — restreint aux projets où l'acteur est `chef_de_projet`, conforme à la demande ("accès aux budgets des projets sur lesquels l'user est chef de projet").
- **Visibilité (actée à l'origine, confirmée à l'implémentation) :** les statistiques globales sont visibles par tout utilisateur authentifié (scopées à `accessible_projects`, pas une vue "admin"). Les statistiques d'un projet donné sont visibles par tout membre de ce projet ; le tableau par membre distingue seulement la **largeur** des données (tous les membres vs soi-même), pas l'accès à l'écran.

**Précisions actées à l'implémentation :**
- `Task.ACTIVE_STATUSES` exclut `archivee`/`rejetee` — toute agrégation de stats a besoin des tâches archivées (`tasks_done`, `hours_spent`) et doit donc utiliser `Task.all_objects`, jamais `Task.objects` (déjà noté ailleurs dans ce fichier pour d'autres besoins similaires, reconfirmé ici car c'est une source d'erreur silencieuse facile — un `Task.objects.filter(status="archivee")` renvoie toujours une liste vide).
- Logique d'agrégation placée dans `apps.tasks.services` (pas `apps.projects`) : `apps.tasks` a le droit d'importer `apps.projects.services.accessible_projects`, l'inverse serait interdit par la hiérarchie des apps — même raisonnement déjà utilisé pour la fiche utilisateur (`assigned_to`).
- Tableau "par membre" : composant `StatsTab.tsx`, tableau trié (colonnes Réalisées/En cours/Heures passées, cliquables), avatar initiales — même pattern que le sélecteur d'utilisateur (`UserMenu`).

### Widgets étendus (implémenté — session du 2026-08-05, soir bis)

**Statut : implémenté.** Remontée client directe : l'écran Statistiques (projet et global) manquait de graphiques/widgets pour un usage "gestionnaire de projets" — délais, heures passées, respect des échéances, personnes sollicitées. Ces quatre axes sont désormais calculés côté backend et affichés en widgets sur les **deux** écrans (onglet projet et écran global), pas seulement l'un des deux.

- **`apps.tasks.services._task_insights(tasks_qs)`** : fonction factorisée (portée = un projet pour `get_project_task_insights`, ou tous les projets accessibles pour `get_global_task_stats`), calcule :
  - `hours_total` : somme de `time_spent` sur les tâches archivées de la portée.
  - `avg_lead_time_days` : délai moyen de traitement (jours entre `created_at` et `updated_at` des tâches archivées) — `null` si aucune tâche terminée. **Pas de champ `completed_at` dédié** : `updated_at` (`auto_now`) au moment où `complete_task` passe le statut à `archivee` sert de date de complétion, une tâche archivée n'étant plus modifiée ensuite dans les flux existants — proxy fiable, sans migration supplémentaire.
  - `tasks_on_time`/`tasks_late` : respect des échéances, sur les tâches archivées **ayant une deadline** (tâches sans deadline exclues, même logique que la Roadmap) — comparaison `updated_at__date__lte=F("deadline")`.
  - `contributors_count` : nombre d'assignés distincts (non-null) sur la portée, tous statuts confondus — "personnes sollicitées".
  - `priority_breakdown` : comptage par valeur de `PRIORITY_CHOICES`, tous statuts confondus.
- **Endpoints** : `GET /api/v1/tasks/project-insights/{project_id}/` (nouveau, même garde `_require_member` que `project-stats`) ; `GET /api/v1/tasks/global-stats/` étendu avec ces mêmes champs (`GlobalTaskStatsSerializer` hérite désormais de `TaskInsightsSerializer` plutôt que de dupliquer les champs).
- **Widgets frontend** (composants partagés, réutilisés par `StatsTab.tsx` et `GlobalStatsPage.tsx`) :
  - `components/StatCard.tsx` : card KPI (icône/valeur/libellé) — extrait en composant partagé à ce chantier (auparavant dupliqué en CSS entre les deux écrans ; avec l'ajout de 3 cards supplémentaires par écran, la duplication serait devenue trop coûteuse à maintenir en double).
  - `components/DeadlineComplianceWidget.tsx` : `DonutChart` 2 parts (à temps/en retard) + légende + taux — couleurs `--tone-positive-text`/`--priority-critique-text`, réutilisation directe des deux teintes "sain"/"danger" déjà actées (pas de nouvelle teinte introduite pour ce widget, cohérent avec la règle "une couleur = un seul axe de sens").
  - `components/PriorityBreakdownWidget.tsx` : liste de barres horizontales, une par priorité, couleurs `--priority-{basse,moyenne,haute,critique}-text` (mêmes tokens que les badges de priorité).

### Graphique en barres + refonte visuelle des cards (implémenté — session du 2026-08-05, soir ter)

**Statut : implémenté.** Nouveau retour client, toujours sur le même écran : encore trop peu de graphiques, pas assez "visuel" pour un usage KPI rapide. Référence demandée : `ui.watermelon.sh` (components + dashboard exemple) — **inaccessible dans cet environnement** (403 sur le fetcher, et le site est de toute façon une SPA 100% rendue en JS, sans contenu exploitable via une requête HTTP simple ; confirmé y compris avec un user-agent de navigateur via `curl` — seule la coquille HTML vide est servie). Plutôt que d'inventer un rendu attribué à Watermelon UI sans l'avoir vu (règle du projet : jamais de faux "inspiré de X"), l'utilisateur a fourni une capture d'écran d'un autre dashboard générique (sidebar marine, cards KPI, barres, camembert central, courbe) comme référence structurelle — traduite dans les tokens Awtodo existants (palette cyan/violet-galaxie, pas de nouvelle couleur, pas de dégradé décoratif — cohérent avec les interdits déjà actés de la passe "montée en qualité visuelle").

- **`apps.tasks.services._completion_trend(done_qs, weeks=8)`** (nouveau, `COMPLETION_TREND_WEEKS = 8`) : nombre de tâches terminées par semaine sur une fenêtre glissante de 8 semaines (dont la semaine en cours), regroupement via `TruncWeek("updated_at")`. **Semaines sans tâche terminée incluses à 0** (liste toujours de longueur fixe `weeks`, construite par itération sur les semaines attendues puis lookup dans les comptages réels) — l'axe temporel doit rester continu, pas seulement les semaines où il s'est passé quelque chose. Champ `completion_trend` ajouté à `_task_insights` (donc disponible sur `project-insights` et `global-stats`), sérialisé via `CompletionTrendPointSerializer` (`week_start`, `count`).
- **`components/BarChart.tsx`** : graphique en barres fait main (divs + `height` en %, pas de SVG ni de dépendance graphique) — même choix que `DonutChart`/`ProgressBar`/Roadmap. Une valeur au-dessus de chaque barre (pas de tooltip interactif : toujours visible, plus simple, cohérent avec un outil interne sans besoin d'interaction complexe), libellé de semaine en dessous (`JJ/MM` du lundi de la semaine).
- **`components/CompletionTrendWidget.tsx`** : carte wrapper (titre + icône, même gabarit que les deux autres widgets) autour de `BarChart`, alimentée par `insights.completion_trend`.
- **`components/StatCard.tsx` — refonte du gabarit** : libellé (petit, majuscules) + badge icône circulaire en haut, grande valeur en gras en dessous (au lieu de l'ancien agencement icône-à-gauche/valeur-à-droite) — lecture "chiffre héros" plus proche de la référence fournie, toujours sur les mêmes tokens (`--tone-neutral-bg/text`, `--tone-positive-bg/text`, `--font-display`).
- **`components/DonutChart.tsx` — prop `emphasis` (nouvelle, optionnelle, défaut `false`)** : agrandit le chiffre central (26px au lieu de 17px) pour les donuts "héros" (ex. taux de respect des échéances, `size` porté à 130) sans changer le rendu par défaut utilisé en Budgétisation (deux petits donuts de légende, `emphasis` non activée là).
- **Disposition** : les trois widgets (`CompletionTrendWidget`, `DeadlineComplianceWidget`, `PriorityBreakdownWidget`) partagent une même rangée `flex-wrap`, le graphique en barres prenant deux fois plus de largeur relative (`flex: 2 1 380px` contre `flex: 1 1 260px`) — reproduit la hiérarchie "grand graphique + petits widgets à côté" de la référence sans dupliquer sa palette.

## Budgétisation — onglet par projet (implémenté — session du 2026-08-05, soir)

**Statut : implémenté. Précise le point laissé ouvert dans CLAUDE.md ("Budgétisation fonctionnelle complète" en hors périmètre v1) : ce chantier couvre un calculateur simple OPEX/CAPEX par projet, pas une refonte du modèle `BudgetEntry` (temps passé × coût horaire, toujours non implémenté fonctionnellement — voir ce modèle plus bas).**

### Modèle `BudgetLine` (`apps/budgeting`)

Nouveau modèle, distinct de `BudgetEntry` (qui reste un placeholder non branché) — hérite de `StatusLifecycleModel` (voir la règle transverse "aucune suppression physique" en tête de ce fichier, y compris le piège `default_manager_name`/`base_manager_name` sur chaque modèle concret) :
- `project` (FK), `category` (`opex`/`capex`), `label`, `quantity` (**entier**, `PositiveIntegerField` — voir précision ci-dessous), `unit_price` (Decimal), `created_by`, `status` (`active`/`removed`).
- `amount` : propriété calculée (`quantity × unit_price`), pas un champ stocké — recalculée à chaque lecture, jamais désynchronisée.
- **Retrait d'une ligne = `status="removed"`**, jamais un `DELETE` — cohérent avec la règle transverse.

**Correction — quantité en unités entières (implémenté — session du 2026-08-05, soir bis).** Remontée client : `quantity` acceptait des décimales (`DecimalField`), ce qui n'a pas de sens pour une ligne de budget ("3 licences", "2 serveurs" — jamais "2,5 licences"). `unit_price`, lui, reste en Decimal (le prix, contrairement à la quantité, a un sens fractionnaire). Double validation, cohérente avec le reste du projet (une seule règle, appliquée aux deux points d'entrée) :
- **Modèle** : `quantity = models.PositiveIntegerField(default=1)` (migration `0003_alter_budgetline_quantity`).
- **Frontier HTTP** : `BudgetLineCreateSerializer.quantity = serializers.IntegerField(min_value=1)` — rejette "2.5" avec un 400 avant même d'atteindre le service.
- **Service** (`add_budget_line`, appelé aussi directement par les tests, hors DRF) : conversion via `Decimal` puis vérification `quantity == quantity.to_integral_value()` avant `int(quantity)` — détecte proprement une valeur fractionnaire plutôt que de la tronquer silencieusement via un `int()` direct.
- **Frontend** : `<input type="number" min="1" step="1">` sur le champ quantité (distinct du champ prix unitaire, resté `step="0.01"`), `onChange` filtre en plus les caractères non numériques (`replace(/[^0-9]/g, "")`) — défense en profondeur, pas une confiance aveugle dans l'attribut HTML `step`. `BudgetLine.quantity` et `BudgetLineCreatePayload.quantity` sont typés `number` côté frontend (`IntegerField` sérialise en nombre JSON, pas en chaîne Decimal comme `unit_price`/`amount`).

### Endpoints

| Endpoint | Rôle requis | Effet |
|---|---|---|
| `GET /api/v1/budgeting/projects/{project_id}/lines/` | membre du projet | liste les lignes actives du projet (toutes catégories) |
| `POST /api/v1/budgeting/projects/{project_id}/lines/` | chef de projet | crée une ligne (`category`, `label`, `quantity`, `unit_price`) |
| `POST /api/v1/budgeting/{id}/remove/` | chef de projet | `status` → `removed` |
| `GET /api/v1/budgeting/summary/` | tout utilisateur authentifié | totaux OPEX/CAPEX des projets où l'acteur est `chef_de_projet` (voir écran Statistiques global ci-dessus) |

**Permissions :** `can_view_budget` (membre du projet) / `can_manage_budget` (chef de projet de ce projet précis) — même pattern "fonction de garde" que le reste de l'app (`_ensure_can_view_budget`/`_ensure_can_manage_budget` dans `apps.budgeting.services`, réutilisant `apps.projects.services.is_project_member`/`is_project_manager` plutôt que de dupliquer la requête `ProjectMembership` — `apps.budgeting` a le droit d'importer `apps.projects`, sens de dépendance autorisé). `can_manage_budget` est aussi exposé dans `Project.permissions` (flag calculé, même mécanisme que les autres — voir "Permissions API — flags calculés").

### Frontend — onglet "Budgétisation" (hub projet)

- Deux sections (OPEX/CAPEX), chacune avec : une carte "camembert" (donut + légende texte, part en % par ligne) et une carte tableau éditable (libellé/quantité/prix unitaire/montant calculé, ligne d'ajout inline, bouton de retrait) — **édition (ajout/retrait) masquée, pas grisée, si `can_manage_budget` est faux** (même règle que les autres actions gardées par flag), consultation ouverte à tout membre.
- **`DonutChart`** (`frontend/src/components/DonutChart.tsx`) : SVG fait main (pas de dépendance de graphique ajoutée — même choix que la Roadmap/`ProgressBar`), anneau avec espacement entre parts et bouts arrondis, libellé au centre. Design informé par une consultation réelle (WebFetch) du composant `PieChart`/`PieCenter` de Bklit UI (`padAngle`/`cornerRadius`/`innerRadius`) — reproduit à la main, pas copié.
- **Accessibilité (recherche `ui-ux-pro-max`, domaine `chart`) :** un camembert échoue au WCAG pour les daltoniens (couleur seule) — une **légende texte + pourcentage** accompagne systématiquement chaque donut, jamais le graphique seul. Au-delà de 5 lignes, les lignes restantes sont agrégées dans une part "Autres (N)" pour le graphique uniquement — le tableau complet, lui, reste intégral.
- **Couleurs des parts :** rampe monochrome sur `--color-accent` (`color-mix` à plusieurs opacités, + `--tone-neutral-text` pour "Autres") plutôt qu'une palette arc-en-ciel arbitraire — ce graphique porte un seul axe (part de budget par ligne), pas de collision avec la palette sémantique priorité/statut/type déjà figée dans `docs/charte-graphique.md`, mais pas de raison non plus d'improviser de nouvelles teintes globales pour un seul widget.

### Widgets d'ensemble (implémenté — session du 08/08/2026)

Référence de design : composants réels **Watermelon UI** `widget-5` (évolution dans le temps) et `widget-4` (répartition en camembert), tous deux basés sur `recharts` dans le composant source — **non repris** : Awtodo a déjà ses propres graphiques faits main (`DonutChart`, `BarChart`, voir ci-dessus), ajouter `recharts` juste pour ces deux widgets aurait introduit une deuxième façon de faire des graphiques dans le même projet, pour un gain nul. Seuls la composition visuelle (carte + en-tête + gros chiffre + graphique) et le principe (évolution dans le temps / répartition en camembert) sont repris.

- **`BudgetTrendWidget`** (+ nouveau composant générique `AreaChart`, `frontend/src/components/`) : montant total engagé (OPEX + CAPEX confondues) affiché en évolution cumulative, point par point dans l'ordre chronologique réel des lignes (`BudgetLine.created_at`), pas un découpage 7j/14j/30j comme le composant source — une ligne budgétaire est un événement ponctuel et irrégulier, ce découpage n'aurait pas eu de sens sur ces données. `AreaChart` : SVG fait main (aire remplie sous une ligne, dégradé de remplissage — affordance de donnée standard, pas un fond décoratif interdit par la charte), même logique que `BarChart`/`DonutChart`.
- **Répartition OPEX/CAPEX** : réutilise directement `DonutChart` existant (pas de nouveau composant) avec deux parts (total OPEX, total CAPEX) — différent des deux donuts déjà existants par catégorie (qui détaillent la composition *interne* de chacune, ligne par ligne) : celui-ci montre l'équilibre entre les deux catégories elles-mêmes. Placé dans une nouvelle rangée `budgeting-tab__overview` en tête de l'onglet Budgétisation, au-dessus des deux sections détaillées.

## Scoping des listes par appartenance (nouveau — acté, priorité pour cette passe)

**Statut : implémenté (session du 2026-08-05).** Remonté par Claude Code lors du chantier comptes externes : `GET /api/v1/projects/` ne filtrait par appartenance pour personne, interne ou externe.

**Règle générale :** un utilisateur ne voit (liste **et** détail) que les projets où il a une `ProjectMembership` active, et par extension les tâches/incidents de ces projets. `is_platform_admin` voit tout (visibilité administrative transverse, cohérent avec son rang) ; `organisation_role=admin` **ne** voit **pas** automatiquement tous les projets de son organisation — seulement ceux dont il est membre, comme tout le monde (pas d'exception ici, garde le modèle simple).

- `GET /api/v1/projects/` : filtré aux projets où l'utilisateur courant a une `ProjectMembership` de statut `active`.
- `GET /api/v1/tasks/` et `GET /api/v1/incidents/` : scoping vérifié/audité pour confirmer qu'ils héritent bien de cette même restriction (les filtres "Mes tâches"/"Tâches de mon groupe" existants doivent rester scopés aux projets accessibles, pas élargis par erreur).
- **Détail (`retrieve`) d'un projet/tâche/incident individuel** : si l'utilisateur n'a pas de `ProjectMembership` active sur le projet concerné, retourne **404** (pas 403) — ne pas révéler l'existence de l'objet à quelqu'un qui n'y a pas accès.
- Conséquence naturelle : les comptes `externe` (voir section "Comptes et invitations") héritent de cette même règle sans logique dédiée — ils n'ont par construction de `ProjectMembership` que sur leur(s) projet(s) d'invitation.

**Précisions actées à l'implémentation :**
- **`apps.projects.services.accessible_projects(user)`** : fonction unique (`Project.all_objects.none()` pour un utilisateur anonyme, `Project.all_objects.all()` pour `is_platform_admin`, sinon `Project.all_objects.filter(memberships__user=user, memberships__status="active").distinct()`) — seule source de vérité pour la portée, réutilisée telle quelle par `ProjectViewSet.get_queryset()` et `TaskViewSet.get_queryset()`. `apps.tasks`/`apps.incidents` important `apps.projects.services` : sens de dépendance autorisé (voir hiérarchie des apps).
- **`contributor_projects(user)` (session du 2026-09-10)** : même chose mais **exclut** les appartenances `lecteur` (`memberships__role__in={"chef_de_projet","membre"}`). Portée des écrans dont un lecteur est écarté : `IncidentViewSet`, `BudgetLineViewSet`, `DocSpaceViewSet`, planning, et les statistiques globales. Voir `docs/organisation-et-comptes.md` > "Rôle Lecteur" pour le détail de la séparation *voir* / *contribuer* et les helpers `is_project_member` (toute appartenance) vs `is_project_contributor` (base des gardes en écriture).
- **404 obtenu "gratuitement"** : en scopant `get_queryset()` plutôt qu'en ajoutant une vérification explicite dans `retrieve()`, le comportement DRF standard de `get_object()` (404 si l'objet ne fait pas partie du queryset filtré) donne directement le bon code — pas de logique à dupliquer entre liste et détail. Conséquence non demandée mais cohérente : les actions (`validate`/`claim`/`start`/...), qui appellent toutes `self.get_object()`, renvoient elles aussi 404 pour un non-membre plutôt que 403 (avant, elles renvoyaient 403 via `TaskPermissionError`) — ne cache pas moins d'information qu'avant, juste plus tôt dans le pipeline.
- **Tension notée précédemment, non résolue en tant que telle mais devenue sans objet pour les incidents non-affectés (session du 07/08/2026)** : l'autorisation d'action sur un incident *rattaché à un projet* (`_is_member_via_project`, voir "Boîte de réception des incidents non-affectés" ci-dessus) reste basée sur le `Team` du projet (plus large qu'une `ProjectMembership`), alors que le scoping de liste/détail reste strictement basé sur `ProjectMembership`. Ce cas limite existait déjà et n'a pas été retouché ici (portée hors de cette passe). Ce qui a changé : un incident peut désormais être rattaché **directement** à un groupe (`incident.team`, sans passer par un projet) — pour ce cas-là, autorisation et scoping (`accessible_inbox_teams`) suivent tous les deux la même `TeamMembership`, donc aucun écart équivalent ne s'y introduit. En pratique, les flux d'ajout de membre (onglet Administration du projet, sélection à la création) créent systématiquement une `ProjectMembership`, donc l'écart résiduel (incidents *rattachés à un projet*) ne se manifeste que si quelqu'un est ajouté à un `Team` après coup sans jamais passer par l'onglet Administration du projet.
- Tests dédiés : `apps/projects/tests/test_scoping.py` (liste/détail projet+tâche+incident, `is_platform_admin`, `organisation_role=admin` sans exception, compte `externe`, utilisateur anonyme) et vérification directe de `accessible_projects()` hors HTTP.

### Cache d'appartenances à portée requête (passe perfo, session du 2026-09-10 suite)

Le bloc `permissions` de chaque ligne (voir section suivante) fait appel à `is_project_member` / `is_project_contributor` / `is_project_manager` / `is_active_team_member`, qui font chacun un `SELECT EXISTS` d'appartenance. Sur une liste, ça donne un N+1 franc (`GET /tasks/` mesuré à 1058 requêtes pour 96 lignes).

- **`prefetched_project_roles(user, project_ids)`** (`apps/projects/services.py`) et **`prefetched_team_memberships(user, team_ids)`** (`apps/accounts/services.py`) : deux `@contextmanager`. À l'entrée, ils résolvent **en une requête** tous les rôles/appartenances de `user` sur les ids passés, et posent le résultat dans un `contextvars.ContextVar`. Les helpers `is_project_*` / `is_active_team_member` lisent ce cache s'il est présent **et** concerne le bon utilisateur, sinon retombent sur leur `.exists()` habituel.
- Chaque `list()` de viewset (`ProjectViewSet`, `TaskViewSet`, `IncidentViewSet` + son `inbox`) matérialise la page puis enroule la sérialisation dans le(s) contexte(s). **Hors `list` (détail, `@action`, usage service), rien ne change** — pas de `ContextVar` posé, requêtes normales.
- Complément `select_related` / `Prefetch(to_attr=...)` pour les autres `SerializerMethodField` (`get_members`, `get_current_version_id`, `UserSerializer.get_teams` via `assignee__team_memberships` / `user__team_memberships`) — **appliqués uniquement quand `self.action == "list"`** dans `get_queryset()` : une `@action` qui `get_object()` puis mute puis re-sérialise la même instance verrait sinon un `prefetch_related` figé d'avant la mutation (bug rencontré et corrigé sur `members`).
- Résultat : `GET /projects/` 158 → 6, `GET /tasks/` 1058 → 4, `GET /incidents/` 290 → 4, constant quel que soit le volume. Garde-fou anti-régression : `apps/projects/tests/test_list_performance.py` (budget de requêtes plafonné sur un jeu volumineux).

## Permissions API — flags calculés (acté — "conditionnement d'action aux droits")

**Statut : implémenté (session du 2026-08-05), complément naturel du scoping ci-dessus — le scoping dit qui voit quoi, ce chantier dit qui peut cliquer quoi.**

Le backend expose, dans les réponses API des ressources concernées (tâches, incidents, projets), un objet `permissions` avec des booléens précalculés pour l'utilisateur courant (ex. `can_validate`, `can_reject`, `can_claim`, `can_assign`, `can_start`, `can_complete`, `can_edit_spec`, `can_edit_notepad`, `can_comment`). **Le front ne doit jamais recalculer une règle de rôle/statut lui-même** — il lit uniquement ces flags. Une seule source de vérité (les fonctions de `services.py`, qui déterminent déjà ces règles pour valider les actions), pas de logique dupliquée côté JS.

**Comportement UI :** un bouton d'action dont le flag correspondant est `false` est **complètement masqué**, pas grisé — pas de "avant/après" trompeur (l'utilisateur ne doit jamais voir une action qu'il n'a pas le droit de faire).

**Exception assumée — Kanban :** cette règle de masquage s'applique aux boutons d'action individuels, pas aux colonnes du Kanban (zone structurelle du tableau, pas un bouton isolé — la masquer changerait la mise en page selon qui regarde). Pour le Kanban, la règle déjà actée reste : zone de dépôt **grisée/désactivée** si le drop n'y est pas autorisé (voir section "Correction — périmètre du drag-and-drop dans le Kanban"), pas masquée.

**Précisions actées à l'implémentation :**
- **Pattern "fonction de garde" par app** (`apps/tasks/services.py`, `apps/incidents/services.py`, `apps/projects/services.py`) : chaque règle existe une seule fois, sous la forme `_ensure_can_X(actor, obj)` qui lève l'exception appropriée (permission ou validation) si l'action n'est pas possible. La transition réelle (`validate_task`, `start_incident`, `update_project_notes`...) appelle cette garde et laisse l'exception remonter (403/400 côté vue) ; le flag correspondant (`can_validate_task`, `can_start_incident`...) appelle la **même** garde via `apps.common.permissions.check_permission(fn, *args, catch=(...))`, qui l'exécute et convertit une exception en `False`. Aucune condition de rôle/statut n'existe à deux endroits.
- **`get_task_permissions`/`get_incident_permissions`/`get_project_permissions`** : agrègent les flags d'un objet en un seul dict, appelées par un `SerializerMethodField("permissions")` sur `TaskSerializer`/`IncidentSerializer`/`ProjectSerializer`. Nécessite que `request` soit dans le contexte du serializer — les vues ont été changées de `TaskSerializer(obj).data` à `self.get_serializer(obj).data` partout (y compris dans les `@action` de transition) pour que `self.get_serializer_context()` (qui inclut `request`) soit systématiquement propagé.
- **Flags projet retenus** : `can_edit_spec`, `can_edit_notepad` (même garde sous-jacente `_ensure_can_edit_notes`, réutilisée par `update_spec_section` et `update_project_notepad` respectivement — deux actions distinctes côté frontend, `SpecTab`/`NotesTab`) et `can_manage_members` (garde déjà existante `_require_manager`, utilisée par `ProjectAdminTab` pour remplacer son ancien calcul client `project.members.some(...)`). `can_rename` ajouté côté tâches (action existante, gardée cohérente avec le reste même si non listée nommément dans la demande).
- **Frontend — recalculs remplacés par une lecture de `permissions`** : `TaskDrawer` (Valider/Rejeter/M'attribuer/Démarrer/Clôturer), `TaskCard`/`TasksListPage` (édition inline du titre via `can_rename`), `IncidentDrawer`/`IncidentsPage` (Démarrer/Résoudre/Archiver, zone de commentaire masquée si `can_comment` est faux), `NotesTab` (bouton "Modifier" masqué si `can_edit_spec`/`can_edit_notepad` est faux), `ProjectAdminTab` (`isManager` devient une lecture directe de `project.permissions.can_manage_members`). Seule exception : `lib/taskTransitions.ts::isDropAllowed`, qui lit désormais `task.permissions.can_start`/`can_complete` au lieu de recalculer `task.assignee?.id === currentUser.id` — la logique de calcul a donc, elle aussi, migré vers les flags, seul le traitement visuel (grisé, pas masqué) reste l'exception actée pour le Kanban.

## Projets — Hub complet (Cahier des charges / Bloc-notes / Roadmap / Maintenance)

**Statut : acté, révision élargie.** Le "détail projet" n'est pas qu'une liste de tâches — c'est le hub de tout le cycle de vie d'un projet. Workflow cible explicite : (1) définir le projet et ses besoins via un cahier des charges → (2) prendre des notes utiles en continu → (3) créer des tâches pour suivre le déroulement et construire une roadmap → (4) suivre la maintenance du projet (incidents).

**Vue détail projet, 7 onglets au total** (4 décrits ci-dessous + Administration, voir `docs/organisation-et-comptes.md` > "Onglet Administration sur le hub projet" + Statistiques/Budgétisation, voir sections dédiées plus haut dans ce fichier) :

### 1. Cahier des charges — structuré en sous-sections (implémenté — session du 2026-08-05, nuit)

**Statut : implémenté. Remplace l'ancien champ `spec_content` (texte libre unique), retiré du modèle `Project`** — remontée client : le cahier des charges doit être composé de sous-parties non obligatoires, l'utilisateur choisissant lesquelles activer.

- **Modèle `SpecSection`** (`apps/projects/models.py`) : une ligne par `(project, section_key)`, `section_key` en **12 valeurs fixes** (choices Django, pas de taxonomie personnalisable par projet — cohérent avec la philosophie v1) : `contexte`, `objectifs`, `besoin`, `perimetre`, `exigences_fonctionnelles`, `exigences_techniques`, `contraintes`, `livrables`, `planning`, `budget`, `organisation`, `annexes`. Champs `is_active` (cochée dans le "sommaire") et `content` (markdown libre). Créée à la demande (`get_or_create`), jamais pré-créée pour les 12 sections à la création du projet.
- **Pas de `StatusLifecycleModel`** : ce n'est pas une entité métier avec un cycle de vie (comme une tâche/un incident), juste une subdivision structurelle de `Project` — **décocher une section ne vide pas son `content`** (l'utilisateur peut la recocher plus tard sans perdre ce qu'il avait écrit), donc rien à "supprimer" au sens de la règle transverse.
- **Endpoints** : `GET /api/v1/projects/{id}/spec-sections/` (tout membre — renvoie toujours les 12 sections, synthétisées à `is_active=False`/`content=""` si jamais touchées, sans créer de ligne pour une simple lecture) ; `PATCH /api/v1/projects/{id}/spec-sections/{section_key}/` (tout membre, mêmes droits que le reste du cahier des charges — `is_active` et/ou `content`, au moins un des deux requis).
- **Frontend (`SpecTab.tsx`)** : mise en page à deux colonnes — à gauche un "sommaire" (liste des 12 sections à cocher/décocher, coche = `is_active`), à droite le corps du document qui n'affiche que les sections cochées, chacune éditable indépendamment (même pattern lecture/édition que le bloc-notes : `MarkdownView` en lecture, `<textarea>` + Enregistrer/Annuler en édition). Case à cocher **désactivée, pas masquée**, pour un non-éditeur (elle reste utile en lecture comme sommaire même sans droit d'édition — même exception déjà actée pour les zones structurelles du Kanban) ; le bouton "Modifier" par section, lui, reste masqué si `can_edit_spec` est faux (action isolée, règle standard).

### 2. Bloc-notes
- Champ `notepad_content` sur `Project` (markdown, texte libre) + `notepad_updated_at`, via `PATCH /api/v1/projects/{id}/` (`ProjectNotepadUpdateSerializer`/`update_project_notepad` — anciennement `update_project_notes`, renommé après le retrait de `spec_content` de ce même endpoint).
- Édition libre par tout membre du projet.
- Rendu markdown en lecture, édition en texte brut (pas d'éditeur WYSIWYG en v1). Pas d'historique de versions — le contenu s'écrase à l'édition. (Le cahier des charges, structuré en sous-sections depuis la passe ci-dessus, ne partage plus cet endpoint.)

### 3. Tâches — deux vues
- **Vue Kanban** (déjà existante) : exécution par statut, glisser-déposer.
- **Vue Roadmap** (frise temporelle, style Gantt simplifié) : **chantier séparé, pas dans la prochaine passe** — voir note d'implémentation ci-dessous. Chaque tâche ayant une deadline est représentée par un segment allant de sa date de création à sa deadline sur un axe temporel. Les tâches sans deadline sont listées à part, hors frise (pas de segment sans date de fin connue).

### Spécification détaillée — Vue Roadmap (Passe B)

**Direction visuelle validée sur maquette** (`maquette-roadmap-hub-projet.html`) : segments en pilule arrondie (pas de rectangles pleins), couleur = priorité (réutilise la rampe déjà actée), longueur = durée réelle (création → deadline) — priorité et durée sont deux axes volontairement découplés, ne jamais faire varier la longueur d'un segment selon sa priorité. Ligne "Aujourd'hui" en accent. Élévation au survol des segments (cohérent avec le principe acté plus haut).

**Correction — lisibilité et présentation.** La Roadmap doit être présentée **dans une carte dédiée**, avec un **fond légèrement plus clair que le fond de page** (surface distincte, pas la même teinte que l'arrière-plan général — cohérent avec le traitement "carte" déjà utilisé ailleurs dans l'app), et un **grillage aligné sur l'axe temporel** (lignes verticales fines au niveau de chaque graduation mensuelle/hebdomadaire, pas seulement le libellé de mois flottant sans repère visuel) pour que la position d'un segment dans le temps se lise d'un coup d'œil, pas seulement par calcul mental depuis les libellés.

**Statut : implémenté (session du 2026-08-05).** Le grillage (`.roadmap__gridline` sur la ligne d'axe, `.roadmap__row-gridline` répété sur chaque ligne de tâche, mêmes positions `left: {gridline.position}%` que les libellés de graduation) existait déjà dans `RoadmapView.tsx`/`.css` avant cette passe — seule la carte dédiée manquait. Ajoutée en enveloppant la légende + la zone scrollable de la frise dans un nouveau conteneur `.roadmap__card` (`background: var(--color-surface)`, `border: 1px solid var(--color-border)`, `border-radius: var(--radius-md)`, `padding: var(--space-5)`) — même token de surface que `.project-card`, pas une teinte propre à la Roadmap. La liste "Sans échéance" reste hors de la carte (élément distinct, pas une "carte imbriquée").

**Comportements actés :**
- **Fenêtre temporelle : auto-ajustée**, calculée dynamiquement sur les dates réelles des tâches du projet (min `created_at` → max `deadline`, sur les tâches actives avec deadline uniquement). Pas de fenêtre fixe.
- **Tâches archivées exclues de la roadmap** — seules les tâches actives (non archivées, non rejetées) avec une deadline apparaissent sur la frise.
- **Retard (deadline passée, tâche toujours active) : traitement gradué selon la priorité**, pas un indicateur uniforme :
  - Priorité `critique` ou `haute` + en retard → icône d'alerte visible sur le segment, en plus de sa couleur de priorité habituelle
  - Priorité `moyenne` ou `basse` + en retard → aucun traitement spécial, la couleur de priorité suffit
- **Rendu** : positionnement CSS pur (pas de librairie de Gantt tierce), cohérent avec le reste du projet.
- **Granularité des graduations temporelles** : mensuelle si l'étendue calculée dépasse ~2 mois, hebdomadaire sinon.
- **Tri des lignes** : par deadline croissante.
- **Clic sur un segment** : ouvre le même drawer de détail que le Kanban, pas une nouvelle interface.
- **Responsive** : scroll horizontal sous une certaine largeur d'écran, pas de repli en liste simple.
- Les deux vues sont accessibles depuis l'onglet "Tâches" (bascule Kanban/Roadmap, pas deux onglets séparés).

### 4. Incidents (renommé depuis "Maintenance" — session du 07/08/2026)
- Reprend les incidents du projet (liste + drawer de détail + commentaires, une fois ce chantier fait) directement dans le hub — pas besoin d'aller sur l'écran Incidents global et de filtrer par projet manuellement.
- Aucune nouvelle logique métier ici : c'est un réemploi contextualisé des composants Incidents déjà prévus (`IncidentsPage` avec `scopedProject`).
- Seul le libellé de l'onglet a changé ("Maintenance" → "Incidents", `ProjectDetailView.tsx`) — l'identifiant interne (`Tab = "maintenance"`) n'a pas été renommé, la fonctionnalité était déjà en place avant ce renommage.

**Séquencement (deux passes, pas une seule) — statut : les deux passes sont implémentées (session du 2026-08-04, faites à la suite l'une de l'autre dans la même session sur demande explicite) :**
- **Passe A** : cahier des charges + bloc-notes (champs + édition), structure en 4 onglets avec Kanban existant dans "Tâches" et onglet "Maintenance" (incidents scopés au projet, en réutilisant le détail incident/commentaires construit dans la même passe).
- **Passe B** : vue Roadmap/Gantt simplifié dans l'onglet Tâches.

**Précisions actées à l'implémentation (Passe A) — ⚠️ `spec_content` superseded, voir "1. Cahier des charges" plus haut (session du 2026-08-05, nuit) :**
- `spec_content`/`notepad_content` : édition en texte brut dans un `<textarea>`, rendu markdown en lecture via un petit composant maison (`frontend/src/components/MarkdownView.tsx`) — pas de dépendance ajoutée (`marked`, `react-markdown`...). Sous-ensemble volontairement restreint : titres `#`/`##`/`###`, **gras**, *italique*, `code`, liens `[texte](url)`, listes à puces/numérotées, paragraphes. Génère des éléments React directement (pas de `dangerouslySetInnerHTML`) — aucune surface XSS à traiter même si le contenu est écrit par n'importe quel membre du projet. **Le rendu markdown (`MarkdownView`) reste valable tel quel pour les sous-sections du cahier des charges** — seul le stockage en un champ unique `spec_content` a été remplacé par `SpecSection`.
- `PATCH /api/v1/projects/{id}/` : à l'origine un seul serializer (`ProjectNotesUpdateSerializer`, `spec_content`/`notepad_content` optionnels) — **`spec_content` retiré de cet endpoint**, qui ne gère plus que `notepad_content` (`ProjectNotepadUpdateSerializer`/`update_project_notepad`, champ désormais requis). Permission inchangée : `_require_member` (n'importe quel membre du projet, pas réservé au chef de projet — cohérent avec "édition libre par tout membre").
- Onglet Maintenance : `IncidentsPage` a gagné une prop `scopedProject?: Project` plutôt qu'un nouveau composant — quand fournie, verrouille le filtre projet, masque le sélecteur de projet et la colonne "Projet" de la liste (redondante une fois scopée). Aucune nouvelle logique métier, conforme au principe de réemploi contextualisé.

**Précisions actées à l'implémentation (Passe B — Roadmap) :**
- Longueur minimale de segment (`min-width` CSS + plancher de 1.5% en largeur calculée) pour qu'une tâche à échéance très proche de sa création reste cliquable/visible — n'affecte pas le calcul de position, seulement un plancher visuel pour les cas limites (durée quasi nulle).
- Composant auto-suffisant (`RoadmapView.tsx`) sur le même modèle que `KanbanBoard`/`TasksListPage` : fetch de tâches, hook `useTaskTransitions`, `TaskDrawer` + `RejectDialog`/`CompleteDialog` propres — pas d'état partagé avec le Kanban au-delà du composant `TaskDrawer` réutilisé, cohérent avec le pattern déjà en place où chaque vue liste est autonome plutôt que de forcer un state manager commun.

## Corrections UI — constatées sur captures d'écran (session du 04/08/2026, post-passe hub/roadmap)

**Statut : implémenté (session du 2026-08-04, soir).**

### 1. Dimensionnement du drawer de détail (tâche/incident)

Le drawer apparaît actuellement comme une **carte flottante** — coins arrondis, ne couvre pas toute la hauteur de l'écran (espace visible au-dessus et en dessous), scrollbar interne visible dans un espace réduit. Donne une impression de "petite fenêtre bizarre", pas d'un vrai panneau latéral. À corriger :
- Position fixe ancrée au bord droit, hauteur = 100% du viewport (`top: 0`, `bottom: 0`), sans marge au-dessus ni en dessous.
- Pas de coin arrondi sur les bords qui touchent l'écran (haut, bas, droite) — un arrondi flottant n'a pas de sens pour un panneau ancré au bord.
- Backdrop qui assombrit le reste de l'écran pendant que le drawer est ouvert (à vérifier si pas déjà présent).
- Le contenu (description/historique/commentaires) défile naturellement dans la hauteur disponible du panneau, pas dans une sous-boîte visuellement contrainte.
- S'applique au composant partagé par tâches et incidents (`TaskDrawer` et son équivalent incident).

### 2. Dialog de création de projet — contenu qui déborde du viewport

Le formulaire déborde par le haut : le titre du dialog et le champ "Nom du projet" ne sont pas visibles, coupés au-dessus de la fenêtre. Problème de centrage/hauteur du dialog, pas de scroll interne correctement géré. À corriger :
- Le dialog doit être centré verticalement OU plafonné à une hauteur maximale du viewport (ex. `max-height: 90vh`) avec son propre scroll interne si le formulaire dépasse cette hauteur — jamais de contenu qui déborde au-dessus de `y: 0`.
- Vérifier si le même bug affecte les dialogs de création de tâche/incident (probablement un composant de dialog partagé) — corriger à la source plutôt que dialog par dialog si c'est le cas.

### 3. Visibilité de la Roadmap

Les segments de la frise sont peu contrastés (remplissage sombre proche de la couleur de fond), rendant la priorité difficile à distinguer d'un coup d'œil ; les graduations mensuelles sont trop discrètes pour être lisibles confortablement. À corriger :
- Renforcer le contraste des segments : fond teinté clair + bordure/texte dans la couleur de priorité pleine (cohérent avec le traitement des badges de priorité ailleurs dans l'app), pas un aplat sombre uni.
- Ajouter une légende de couleurs de priorité sur la vue Roadmap (comme sur la maquette de référence `maquette-roadmap-hub-projet.html`).
- Renforcer la lisibilité des graduations temporelles (contraste et/ou taille du texte des libellés de mois/semaines).

**Précisions actées à l'implémentation :**
- **Cause racine du drawer/dialog "flottant" (1 et 2, même origine) :** `.view-transition` (transition de page ajoutée plus tôt cette session — voir "Transitions et profondeur visuelle") anime `transform: translateY(...)`. Avec `animation-fill-mode: both`, un `transform` non-`none` reste appliqué en continu, même `translateY(0)` en fin d'animation — et par la spec CSS, tout ancêtre avec un `transform` non-`none` devient le containing block des descendants en `position: fixed`, au lieu du viewport. Le drawer/dialog, rendus comme descendants de `.view-transition`, étaient donc positionnés relativement à cette zone de contenu paddée (pas edge-to-edge, pas pleine hauteur) au lieu du viewport — exactement le symptôme "petite fenêtre flottante". Corrigé en retirant le `transform` de l'animation (fondu seul — CLAUDE.md autorisait déjà "fondu **et/ou** léger déplacement"), ce qui règle le bug pour **tous** les overlays `position: fixed` de l'app d'un coup, pas seulement le drawer et le dialog de projet.
- **Bug distinct sur les dialogs de création (2) :** `.xxx-create-dialog` est un flex item dans un overlay centré (`display: flex; align-items: center`) avec `max-height` + `overflow-y: auto`. Un flex item a par défaut `min-height: auto` (= hauteur intrinsèque du contenu), qui **prime sur `max-height`** quand le contenu est plus haut que le viewport — `overflow-y: auto` n'engageait donc jamais, et l'excédent débordait au-dessus de `y: 0` sous l'effet du centrage. Trouvé en le vérifiant dans les trois dialogs de création (projet/tâche/incident, même pattern dupliqué) — corrigé par un `min-height: 0` sur chacun. Vérifié via `npm run build` + relecture du raisonnement CSS (pas de rendu navigateur possible dans cet environnement — à confirmer visuellement).
- **Roadmap :** fond des segments passé à `color-mix(in srgb, var(--priority-X-text) 22%, transparent)` (teinte translucide de la couleur "text", vive dans les deux thèmes) + bordure 1.5px pleine dans la même couleur — remplace l'ancien `background: var(--priority-X-bg)`, qui est sombre en mode sombre (pensé pour du texte sur badge, pas un remplissage de grande surface) et se fondait dans le fond de page. Légende ajoutée au-dessus de la frise (4 pastilles, même traitement couleur que les segments). Graduations : couleur passée de `--color-text-muted` à `--color-text`, poids 600, taille 11px→12px.

## Documentation de projet (implémenté — session du 2026-09-03)

App `apps/documentation/` (label `documentation`). Onglet « Documentation » du hub projet, **visible uniquement pour un chef de projet** (`permissions.can_edit_documentation`, ajouté à `get_project_permissions`). Objectif : de la **documentation utilisateur** du produit, hébergée dans Awtodo et partageable en lecture publique.

### Modèles

- **`DocSpace`** — un par projet (`OneToOneField(Project)`, `related_name="doc_space"`). Créé à la demande (`get_or_create`) au premier accès. Pas de `StatusLifecycleModel` (suit le projet). Champs : `is_public` (bool), `public_token` (`CharField(64)`, `unique`, `null` tant que jamais activé). Révoquer = `public_token=None` + `is_public=False`. Régénérer = nouveau token (`secrets.token_urlsafe(32)`).
- **`DocPage`** — page Markdown arborescente. `StatusLifecycleModel` (`brouillon` / `publie` / `archive` ; `ACTIVE_STATUSES = {brouillon, publie}`). `space` FK, `parent` self-FK **limité à 2 niveaux** (garde `create_page`/`update_page` : refuse un parent qui a lui-même un parent, refuse de re-parenter une page ayant des enfants), `title`, `slug` (unique par espace hors archivées, contrainte partielle), `content`, `order`. « Supprimer » = `status="archive"` ; les enfants directs sont remontés au parent de la page archivée.
- **`DocEntry`** — fiche structurée, un seul modèle pour les deux onglets via `kind` (`fonctionnalite` | `resolution`). `StatusLifecycleModel` même cycle. `space` FK, `title`, `description` (Markdown), `order`, `source` (`manuelle` | `tache` | `incident` | `cahier_des_charges`), `source_task` / `source_incident` (FK nullables `SET_NULL`).
- **`PendingDocEntry`** — file « À documenter ». `StatusLifecycleModel` (`en_attente` / `traitee` / `ignoree`). `space` FK, `kind`, `task` **ou** `incident` (`OneToOneField` nullables, `CheckConstraint` « exactement un des deux »), `entry` FK (renseignée quand `traitee`).

Les trois modèles `StatusLifecycleModel` déclarent `default_manager_name = base_manager_name = "all_objects"` dans leur `Meta` (piège Django documenté dans `CLAUDE.md`). Régression couverte par `apps/documentation/tests/test_models.py`.

### File « À documenter » — alimentation automatique

Deux signaux Django **nouveaux**, consommés par `apps/documentation/signals.py` (jamais d'import inverse — règle de dépendances) :

- **`apps.tasks.signals.task_completed`** (kwargs `task`, `actor`) — émis en fin de `complete_task`. Le récepteur crée une `PendingDocEntry(kind="fonctionnalite")` **si** `task.task_type ∈ {ajout, evolution}` (pas `correction`) **et** le projet a déjà un `DocSpace`.
- **`apps.incidents.signals.incident_resolved`** (kwargs `incident`, `actor`) — émis en fin de `resolve_incident`. Récepteur : `PendingDocEntry(kind="resolution")` **si** `incident.project_id` est renseigné (incident rattaché à un groupe seul → ignoré) **et** le projet a un `DocSpace`.

`get_or_create(task=…)` / `get_or_create(incident=…)` → idempotent.

### API — endpoints authentifiés (`/api/v1/docs/`, chef de projet)

`DocSpaceViewSet` (`GenericViewSet`, `lookup_field="project_id"` = UUID du projet). `DocsPermissionError` → 403, `DocsValidationError` → 400 (via `handle_exception`).

| Méthode / chemin | Effet |
|---|---|
| `GET /api/v1/docs/{project_id}/` | agrégat : `{ space, pages (arbre), features, resolutions, pending_features, pending_resolutions }` |
| `POST .../pages/` | crée une page (`title`, `parent_id?`, `content?`) |
| `PATCH .../pages/{page_id}/` | `title?`, `content?`, `parent_id?` (absent = inchangé, `null` = racine), `order?` |
| `POST .../pages/{page_id}/publish/` · `/unpublish/` | bascule `status` |
| `DELETE .../pages/{page_id}/` | archive (204) |
| `POST .../entries/` | crée une fiche (`kind`, `title`, `description?`) |
| `PATCH .../entries/{entry_id}/` · `POST .../publish/` · `/unpublish/` · `DELETE` | comme les pages (DELETE renvoie la fiche archivée) |
| `POST .../seed-from-spec/` | une fiche brouillon `kind=fonctionnalite` par bloc de la section `exigences_fonctionnelles` du cahier des charges (dé-doublonnage sur le titre ; 400 si section vide) |
| `POST .../pending/{pending_id}/create-entry/` | crée une fiche pré-remplie (titre + description de la tâche/incident), passe le pending à `traitee` |
| `POST .../pending/{pending_id}/ignore/` | pending → `ignoree` (204) |
| `POST .../public-link/` · `POST .../public-link/rotate/` · `DELETE .../public-link/` | active / régénère / révoque le lien public — renvoie `{ space }` |

### API — endpoint public (`AllowAny`, sans authentification)

`GET /api/v1/docs/public/{token}/` → `{ project_name, pages (arbre, publiées seulement), features, resolutions }`. `404` si token vide, inconnu, ou `is_public=False`. **Seul le contenu `status="publie"` est exposé** ; une page publiée dont le parent ne l'est pas est remontée à la racine. Aucune donnée de gestion (tâches, membres, budget, incidents) n'est jamais renvoyée. Voir `CLAUDE.md` > Stack technique > Auth pour l'exception au garde-fou « connexion obligatoire ».

Toute la logique est dans `apps/documentation/services.py` (y compris la mise en forme des dicts de réponse) ; les vues ne font que router et traduire les exceptions.


## Module Planning / Calendrier (implémenté — session du 2026-09-09)

Nouvelle app `apps/planning/` (label `planning`) — dépend de `common`/`accounts`/`projects`/`tasks`/`incidents`, rien ne dépend d'elle. Trois volets : calendrier personnel, planning de projet, partage entre calendriers. Nouvelle dépendance : `python-dateutil` (moteur RRULE, backend uniquement).

### Décisions cadrées

- **Récurrence** : moteur RRULE iCal complet via `dateutil.rrule.rrulestr`, stockée en chaîne `recurrence_rule` (valeur seule, sans préfixe `RRULE:`). **Édition à la série entière uniquement** — pas d'occurrence isolée (pas d'EXDATE / RECURRENCE-ID). Annuler = toute la série passe `annule`.
- **Planifier une tâche/incident ne change jamais son statut** — le créneau (`ScheduledBlock`) est une donnée d'agenda découplée du cycle de vie. `time_spent` reste saisi manuellement à la clôture.
- **Pas de lien public non authentifié** vers un calendrier — le partage est de compte à compte (éviterait une 2ᵉ exception au garde-fou « connexion obligatoire »).
- **Le partage n'est lié à aucun groupe ni type de compte** (précisé session du 2026-09-10) : `owner` peut partager son calendrier avec **n'importe quel** utilisateur du site — membre d'un autre groupe, ou compte `externe` invité sur un projet — la seule règle est `owner != grantee`. Le sélecteur du `SharePanel` (frontend) liste donc tous les comptes hors soi-même et hors partages déjà accordés, sans filtrer sur `account_type` ni sur l'appartenance de groupe. Conséquence assumée : un invité externe scopé à un seul projet peut recevoir la vue lecture seule du calendrier personnel de celui qui le lui partage — c'est un geste explicite de l'`owner`, révocable des deux côtés.
- **Fuseau unique** `Europe/Paris` (déjà `USE_TZ=True`). Datetimes stockés aware ; API en ISO 8601 avec offset. L'expansion des occurrences se fait en heure locale pour que l'heure d'horloge reste stable de part et d'autre des changements d'heure été/hiver.

### Mixin `RecurringEventModel` (abstrait, `apps/planning/models.py`)

`start`, `end` (`DateTimeField`), `all_day` (`BooleanField`), `recurrence_rule` (`TextField`, vide = ponctuel). Utilisé par `CalendarEvent` et `ProjectPlanningEntry`.

### Modèles

Tous héritent de `StatusLifecycleModel` avec le `Meta` (`default_manager_name` / `base_manager_name = "all_objects"`) obligatoire (piège Django, voir CLAUDE.md) — régression couverte par `apps/planning/tests/test_models.py`.

| Modèle | Rôle | Statuts (`ACTIVE_STATUSES`) |
|---|---|---|
| `CalendarEvent` | Événement du calendrier personnel (`owner` = organisateur). Récurrent. | `confirme` / `annule` (`{confirme}`) |
| `EventParticipant` | Invitation d'un utilisateur à un `CalendarEvent`. `response` ∈ `invite`/`accepte`/`refuse`. `UniqueConstraint(event, user)` sur les actifs. | `active` / `removed` (`{active}`) |
| `ScheduledBlock` | Créneau posé sur une tâche **ou** un incident assigné à `owner`. `CheckConstraint` « exactement un des deux ». Pas de récurrence. | `planifie` / `annule` (`{planifie}`) |
| `ProjectPlanningEntry` | Entrée du planning partagé d'un projet. `kind` ∈ `jalon`/`phase`/`reunion`/`autre`. `assignee` optionnel (si renseigné, l'entrée apparaît aussi sur le calendrier perso de cette personne). Récurrent. | `confirme` / `annule` (`{confirme}`) |
| `CalendarShare` | Partage lecture seule de `owner` vers `grantee`. `UniqueConstraint(owner, grantee)` sur les actifs, `CheckConstraint` `owner != grantee`. | `active` / `revoked` (`{active}`) |

### Service central — `expand_occurrences(sources, window_start, window_end)`

Développe une liste d'objets récurrents en occurrences concrètes chevauchant la fenêtre. Ponctuel → 0 ou 1 ; série → bornée par la fenêtre **et** par `MAX_OCCURRENCES = 366`. Pure fonction testée à part (`apps/planning/tests/test_recurrence.py` : FREQ DAILY/WEEKLY/MONTHLY/YEARLY, INTERVAL, BYDAY, UNTIL, COUNT, fenêtre partielle, DST mars/octobre, RRULE invalide → ignorée). Toute la mise en forme des dicts de réponse vit dans `services.py` (règle CLAUDE.md n°1) ; les vues traduisent seulement les exceptions (`PlanningPermissionError` → 403, `PlanningValidationError` → 400, via `handle_exception`).

### Gardes de permission

| Action | Garde |
|---|---|
| Créer/modifier/annuler un `CalendarEvent`, gérer ses participants | `actor == event.owner` |
| Répondre à une invitation | `actor == participant.user` |
| Créer/déplacer/annuler un `ScheduledBlock` | `actor == owner` **et** la tâche/incident lui est assignée **et** `is_project_member` |
| Créer/modifier/annuler un `ProjectPlanningEntry` | `is_project_manager(actor, project)` |
| Voir le planning d'un projet | `is_project_member(actor, project)` |
| Créer un `CalendarShare` | `actor == owner` |
| Révoquer un `CalendarShare` | `actor == owner` **ou** `actor == grantee` |

Scoping : `get_queryset()` filtre toujours par `owner` / participation / `project__in=accessible_projects(...)` — accès non autorisé ⇒ 404 « gratuit ». Nouveau flag projet `can_manage_project_planning` ajouté à `apps.projects.services.get_project_permissions` (garde `_ensure_can_manage_project_planning` = `_require_manager`).

### API — `/api/v1/planning/`

| Méthode / chemin | Effet |
|---|---|
| `GET /planning/calendar/?from=<ISO>&to=<ISO>&owners=<uuid,…>&projects=<uuid,…>` | agrégat calendrier de l'utilisateur : `{ events, blocks, project_entries, shared }`, occurrences expansées. `from`/`to` requis (400 sinon), fenêtre ≤ `MAX_WINDOW_DAYS = 92` jours |
| `GET/POST /planning/events/` | liste des séries dont l'utilisateur est owner ou participant actif / création (`title`, `start`, `end`, `all_day?`, `description?`, `location?`, `recurrence_rule?`) |
| `GET/PATCH /planning/events/{id}/` | détail (+ `participants`, `audit_log`) / modification de la série (owner) |
| `POST /planning/events/{id}/cancel/` | série → `annule` (owner) |
| `POST /planning/events/{id}/participants/` · `DELETE .../participants/{pid}/` | ajoute (→ signal `event_participant_invited`) / retire un participant (owner) |
| `POST /planning/events/{id}/respond/` | `{response: accepte\|refuse}` (le participant) |
| `POST /planning/blocks/` · `PATCH /planning/blocks/{id}/` · `POST /planning/blocks/{id}/cancel/` | crée `{task\|incident, start, end}` / déplace-redimensionne `{start?, end?}` / annule |
| `GET/POST /planning/projects/{project_id}/entries/?from=&to=` | entrées expansées du projet (membre) / création (chef de projet) |
| `PATCH /planning/projects/{project_id}/entries/{entry_id}/` · `POST .../cancel/` | modifie / annule (chef de projet) |
| `GET /planning/shares/` | `{granted, received}` de l'utilisateur |
| `POST /planning/shares/` · `POST /planning/shares/{id}/revoke/` | `{grantee}` / révoque (owner ou grantee) |

### Signal + notification

`apps.planning.signals.event_participant_invited` (kwargs `event`, `participant`, `actor`), émis par `add_participant`. Consommé par `apps/notifications/` : nouveau verbe `event_invited`, FK nullable `Notification.event` (`planning.CalendarEvent`, PROTECT), `notify_event_invited` (skip si le participant est l'acteur).

### Frontend

Section « Planning » de premier niveau (`BinderTabs`, icône `CalendarDays`) + onglet « Planning » du hub projet (**visible pour tous les membres**, édition réservée aux chefs de projet). Calendrier **fait main** (`frontend/src/features/planning/` : `WeekGrid`, `MonthGrid`, positionnement CSS pur, `@dnd-kit/core` déjà présent pour glisser-déposer et redimensionner) — aucune librairie de calendrier ajoutée, cohérent avec la charte. `RecurrenceEditor` produit une RRULE (sous-ensemble courant) ; `recurrence.ts` la décrit en français. Glisser une tâche du panneau « À planifier » sur la grille crée un `ScheduledBlock` — une même tâche peut recevoir **plusieurs créneaux** (aucune contrainte d'unicité), un compteur l'indique dans le panneau. Un créneau se modifie en l'étirant par la poignée basse ou via `BlockDialog` (début/fin, retrait). Panneau **« Calendriers » façon Outlook** : « Mon calendrier » + une entrée par personne qui partage avec moi, chacune avec case de visibilité et couleur d'identité (palette fixe de 6 teintes sobres, toujours doublée du nom du propriétaire). Les événements d'un calendrier partagé s'affichent dans sa couleur. `EventDialog`/`BlockDialog` gèrent l'édition ; `SharePanel` gère les partages. 448 → 491 tests backend, tous verts.

**Limite v1 assumée** : le panneau « À planifier » ne liste que les **tâches** assignées à l'utilisateur (le sérialiseur `Incident` n'expose pas `assigned_to` côté API) — les blocs sur incident restent créables via l'API mais pas en glisser-déposer depuis l'UI.
