# Awtodo — Organisation, groupes, comptes et invitations

Hiérarchie plateforme/organisation/projet/groupe, écrans d'administration, cycle de vie des comptes. Référencé depuis CLAUDE.md.

## Groupes

**Statut : acté. Introduit une notion de groupe pour restreindre qui peut se voir attribuer une tâche sur un projet collaboratif.**

- Un **Groupe** (modèle `Team`) est un ensemble d'utilisateurs, rattaché à une organisation (voir section "Organisation").
- Un **projet collaboratif** est créé en l'attribuant à **un seul groupe** (`Project.team`, FK) — obligatoire pour un projet `collaboratif`, interdit (null) pour un projet `individuel`.
- **Contrainte à la création d'une `ProjectMembership`** (créateur automatiquement désigné `chef_de_projet`, ou ajout de membre via l'onglet Administration — voir plus bas) : l'utilisateur concerné doit déjà être membre du groupe attribué au projet.
- Conséquence sur la création de projet : à la création d'un projet collaboratif, le créateur doit choisir un groupe **dont il est déjà membre**.

### Administration des groupes (implémenté — session du 2026-08-07)

**Statut : la liste/membres/création existaient déjà** (`GroupsSection.tsx`, onglet "Groupes" de l'écran Administration organisation) ; cette session ajoute le **renommage** et élargit qui peut gérer un groupe.

- **"Administrateur du groupe"** (`apps.accounts.services._is_team_manager`) : le créateur du groupe (`Team.created_by`, règle historique), **ou** un administrateur d'organisation (`organisation_role="admin"`), **ou** un administrateur de plateforme (`is_platform_admin`) — élargissement volontaire de la règle précédente ("réservé au créateur"), pour qu'un admin puisse gérer n'importe quel groupe de son organisation, pas seulement ceux qu'il a personnellement créés. S'applique uniformément à l'ajout/retrait de membres (déjà existant) et au renommage (nouveau).
- **`PATCH /api/v1/accounts/teams/{id}/rename/`** (nouveau) — même découpage 403/400 que le reste de l'app.
- **`can_manage`** : nouveau flag calculé exposé sur `TeamSerializer` (voir CLAUDE.md > "Permissions API — flags calculés") — remplace le calcul client `team.created_by === currentUser.id` qui ne voyait pas les overrides admin. Nécessite que les actions du `TeamViewSet` utilisent `self.get_serializer(...)` plutôt qu'un `TeamSerializer(...)` instancié à la main (sinon pas de `request` dans le contexte du serializer, flag toujours faux) — corrigé au passage sur `create`/`members`/`members/remove`.
- **Frontend** : le titre de chaque carte de groupe (`GroupsSection.tsx`) devient éditable au clic via `components/InlineEditableText.tsx` (déjà utilisé pour le titre des tâches) — le nom reste toujours visible (ce n'est pas un bouton d'action séparé à masquer), mais l'affordance d'édition (curseur texte, surbrillance au survol, `role="button"`) est simplement absente si `!team.can_manage` : rien à cliquer, sans que l'information elle-même disparaisse.

### Filtre sur l'écran Tâches global

Deux modes, via un filtre sur l'écran "Tâches" (liste simple, pas le Kanban) :
- **"Mes tâches"** : tâches assignées à l'utilisateur courant — actionnable.
- **"Tâches de mon groupe"** : tâches assignées à un autre membre d'un groupe dont l'utilisateur courant fait partie — **lecture seule**.

## Organisation (nouveau — acté, session du soir)

**Statut : implémenté (session du 2026-08-04, soir).** Awtodo reste un outil interne à une seule entreprise en usage réel — mais le modèle de données et l'UI d'administration sont construits dès maintenant pour supporter plusieurs organisations, y compris la création de nouvelles organisations. **Aucune isolation stricte des données entre organisations n'est implémentée dans cette passe** (pas de scoping systématique de tous les querysets, pas de sous-domaine par client) au-delà de ce qui est explicitement décrit ici — le rattachement (`FK organisation`) existe partout où c'est listé plus bas, mais l'application ne fait pas encore respecter un cloisonnement strict à chaque requête.

**Hiérarchie à 4 niveaux — bien distinguer les portées, ce sont 4 champs différents, jamais interchangeables dans le code :**

1. **Plateforme** — `User.is_platform_admin` (booléen, défaut `False`). Peut créer de nouvelles organisations et voir la liste de toutes les organisations. N'est **pas** automatiquement admin de chaque organisation.
2. **Organisation** — `User.organisation_role` (`admin`/`chef_de_projet`/`membre`, défaut `membre`), scopé à `User.organisation`. Voir détail des droits ci-dessous.
3. **Projet** — `ProjectMembership.role` (`chef_de_projet`/`membre`), inchangé, par projet.
4. **Groupe** — `Team.created_by`, gère seul la composition de son groupe (pas un champ de rôle, juste "être le créateur").

**Modèles :**
- `Organisation` : `name`, `created_at`.
- `User.organisation` (FK, obligatoire — y compris pour un administrateur de plateforme, qui appartient lui aussi à une organisation).
- `User.organisation_role` :
  - `admin` : promeut/rétrograde le `organisation_role` d'autres utilisateurs de son organisation, crée des groupes, invite par email.
  - `chef_de_projet` (niveau organisation) : crée des groupes, invite par email pour ses groupes. Ne donne aucun rôle automatique sur un projet particulier.
  - `membre` : aucun droit de création de groupe ni d'invitation. Peut toujours créer un projet et en devenir chef de projet **au niveau du projet** (règle inchangée).

**Migration de données (déploiement de cette passe) :** crée une organisation unique, y rattache tous les `User`/`Team`/`Project` existants, désigne au moins un utilisateur `organisation_role=admin` **et** `is_platform_admin=True` (l'utilisateur de test principal, sinon demander si ambigu — sans ça, personne ne peut administrer quoi que ce soit après cette passe).

**Précisions actées à l'implémentation :**
- **Organisation unique nommée "Répar'Stores"**, créée par la migration de données (`apps/accounts/migrations/0005_backfill_organisation.py`). Utilisateur désigné admin+platform_admin : `achabane` — choix arbitraire (le premier utilisateur par `date_joined`, faute de "compte de test principal" identifiable), à corriger manuellement si ce n'est pas le bon compte (via `User.objects.filter(username=...).update(organisation_role="admin", is_platform_admin=True)`).
- **`Team.organisation` et `Project.organisation`, en plus de `User.organisation`** (le seul champ explicitement listé dans "Modèles" ci-dessus) : ajoutés parce que la ligne "rattache tous les `User`/`Team`/`Project` existants" de la migration de données n'aurait aucun sens sans ces deux FK, et parce que "Groupes (admin/chef_de_projet) : liste des groupes **de l'organisation**" (section suivante) a besoin d'un moyen fiable de scoper un `Team` à une organisation — le dériver via ses membres serait fragile (un groupe à 0 membre n'aurait pas d'organisation dérivable).
- **`default_organisation_id()`** (`apps/accounts/models.py`) : valeur par défaut pratique sur les 3 champs `organisation` ci-dessus (résout vers la première `Organisation` existante) — évite d'imposer `organisation=...` à chaque `User.objects.create_user(...)`/`Team.objects.create(...)`/`Project.objects.create(...)` existant dans ~10 fichiers de tests et le script de seed. N'affaiblit pas la contrainte NOT NULL en base ; un appelant qui veut une organisation précise (ex. `create_organisation`) la passe explicitement et prime sur ce défaut. Cohérent avec le principe déjà écrit plus haut dans ce fichier ("Awtodo reste un outil interne à une seule entreprise en usage réel") : il n'existe concrètement qu'une organisation à la fois tant que ce chantier n'est pas allé plus loin.
- **Tous les endpoints `accounts` (`/organisations/`, `/teams/`, `/invitations/`, `/users/...`) vivent sous `/api/v1/accounts/...`**, pas à la racine `/api/v1/...` comme les tableaux d'endpoints de ce fichier le laissent parfois entendre (`POST /api/v1/organisations/` → en réalité `POST /api/v1/accounts/organisations/`) — conséquence mécanique de `config/urls.py`, qui registre déjà chaque app sous son propre préfixe (`accounts/`, `projects/`, `tasks/`...), pas une déviation décidée cette session.

## Écran Administration (organisation) — 4 sous-sections unifiées

**Statut : implémenté (session du 2026-08-04, soir).** Un seul écran "Administration" dans la sidebar (distinct de l'onglet "Administration" du hub projet, qui reste séparé — voir plus bas), visible pour tout utilisateur ayant au moins un droit d'administration (`organisation_role` ≠ `membre`, ou `is_platform_admin`). Les sous-sections visibles dépendent du rang de l'utilisateur courant :

### 1. Membres (organisation) — implémenté, session du 06/08/2026
Visible par `admin`. Liste des utilisateurs de l'organisation, gestion de leur `organisation_role`.

- **Recherche/filtre par nom** sur la liste (texte libre, côté front suffit à ce volume).
- **Fiche utilisateur** (clic sur une ligne → drawer, même pattern que les autres détails) : nom, email, `organisation_role`, `account_type`/`account_status`, groupes dont il est membre, et **liste des tâches qui lui sont assignées** — sur l'ensemble des projets où il a une `ProjectMembership`, y compris ceux dont l'admin consultant n'est pas lui-même membre (exception assumée à la règle de scoping générale : un admin d'organisation a besoin d'une vue de charge de travail complète sur ses membres, c'est une capacité de gestion RH, pas une fuite de données projet — la fiche n'expose que la liste des tâches assignées, pas le détail complet des projets en question).
- **Sera étoffée à l'ajout des statistiques** (temps passé, historique d'activité) — la version actuelle reste volontairement simple (liste de tâches).

**Précisions actées à l'implémentation :**
- **`UserSerializer` gagne `email`, `account_type_display`, `account_status_display`** — aucun n'était exposé avant ce chantier (l'annuaire Membres n'affichait jusqu'ici que nom/rôle). Nécessaire pour la fiche ; sans risque de fuite puisque `UserSerializer` n'était déjà accessible qu'aux utilisateurs authentifiés de la même organisation via les écrans qui l'utilisent.
- **Recherche côté front, pas un paramètre d'API** — cohérent avec le volume d'utilisateurs attendu par organisation (`GET /api/v1/accounts/users/` charge déjà tout, filtré ensuite en mémoire sur `first_name`/`last_name`/`username`), pas besoin d'un nouveau paramètre de filtre côté backend pour cette passe.
- **Endpoint dédié `GET /api/v1/tasks/assigned-to/{user_id}/`** plutôt qu'un élargissement du scoping de `GET /api/v1/tasks/?assignee=...` — voir docs/modeles-et-api.md pour le détail (limité aux tâches **actives**, volontairement une vue de charge de travail courante, pas un historique).
- **`UserProfileDrawer`** (`frontend/src/features/administration/UserProfileDrawer.tsx`) : ne résout pas les noms de projet des tâches affichées (le nom de projet n'est pas dans le payload `Task`) — respecte volontairement "la fiche n'expose que la liste des tâches assignées, pas le détail complet des projets", pas une limitation technique contournable facilement.

### 2. Groupes
Visible par `admin`/`chef_de_projet`. Liste des groupes de l'organisation, création (`POST /api/v1/teams/`), et pour chaque groupe dont l'utilisateur courant est `created_by` : gestion de composition.
- **Correction de modélisation :** `Team.members` ne doit plus être un many-to-many brut. Remplacé par un modèle **`TeamMembership`** (`team`, `user`, `status`: `active`/`removed`, `created_at`) — cohérent avec la règle "aucune suppression physique" : retirer un membre = passer `status` à `removed`, jamais un `DELETE`.
- `Team.created_by` (FK `User`).

### 3. Invitations
Visible par `admin`/`chef_de_projet`. Voir section dédiée ci-dessous.

### 4. Organisations
**Visible uniquement par `is_platform_admin`.** Liste de toutes les organisations existantes, et création d'une nouvelle organisation.
- `POST /api/v1/organisations/` : réservé à `is_platform_admin`. **Le formulaire de création inclut directement les informations du premier utilisateur admin de cette nouvelle organisation** (nom, email) — créés dans la même transaction, ce nouvel utilisateur reçoit `organisation_role=admin` sur l'organisation qui vient d'être créée. Nécessaire car le flux d'invitation classique (voir ci-dessous) suppose déjà un admin existant dans l'organisation cible, ce qui est impossible pour une organisation qui vient de naître.
- `GET /api/v1/organisations/` : réservé à `is_platform_admin`.

**Précisions actées à l'implémentation :**
- **Correction de modélisation `TeamMembership` implémentée sans conserver `Team.members` comme M2M `through`** : la tentation initiale était `members = ManyToManyField(User, through=TeamMembership)` pour garder `team.members.add(...)`/`user.teams` intacts partout — écarté parce que `.add()` sur un M2M `through` ne sait pas raviver une ligne `removed` (il regarde seulement si une ligne existe pour la paire `(team, user)`, pas son statut), ce qui aurait cassé silencieusement le cas "réinviter un ancien membre retiré". `TeamMembership` est donc un modèle autonome, interrogé explicitement (même pattern que `ProjectMembership`, déjà en place) — a nécessité de mettre à jour ~10 sites d'appel (`.members.add(...)` → `TeamMembership.objects.create(...)`), fait via une migration de données `apps/accounts/migrations/0009_backfill_team_membership.py` pour convertir les lignes existantes.
- `POST /api/v1/teams/{id}/members/` (ajout) et `POST /api/v1/teams/{id}/members/remove/` (retrait, `status=removed`) — body `{"user": "<id>"}` dans les deux cas, réservés à `Team.created_by`.
- `admin.py` : `TeamAdmin.filter_horizontal = ("members",)` n'avait plus de sens après la suppression du M2M — remplacé par un `TeamMembershipInline` (`TabularInline`).

## Onglet "Administration" sur le hub projet (nouveau — acté, distinct de l'écran ci-dessus)

**Statut : implémenté (session du 2026-08-04, soir). Résout le chantier "ajout de membres à un projet" mis de côté depuis le début du projet. Ne pas confondre avec l'écran Administration (organisation) ci-dessus — portées différentes.**

- **5ᵉ onglet** sur la vue détail projet, à côté de Tâches/Cahier des charges/Bloc-notes/Maintenance — visible pour tous les membres du projet, **actions réservées aux chefs de projet de ce projet précis** (`ProjectMembership.role`, pas `organisation_role`).
- Liste des `ProjectMembership` actives (utilisateur, rôle, badge si compte `externe`), avec pour un chef de projet trois actions :
  - **Ajouter un membre du groupe** : sélection parmi les membres actifs du groupe attribué au projet (le cas simple, inchangé).
  - **Ajouter un membre externe au groupe** *(assoupli — voir "Comptes et invitations")* : recherche par email n'importe quel compte `interne` de la même organisation, même hors du groupe attribué au projet. Ajout direct, pas d'invitation nécessaire (le compte existe déjà).
  - **Inviter un externe à l'organisation** *(nouveau — voir "Comptes et invitations")* : email d'une personne sans compte → crée un compte `externe` restreint à ce projet, envoie une invitation.
  - **Changer le rôle** d'un membre existant (`membre` ↔ `chef_de_projet`).
  - **Retirer un membre** : `ProjectMembership.status` passe à `removed` (nouveau champ, même correction que pour `TeamMembership`). **Un projet doit toujours conserver au moins un `chef_de_projet` actif** — bloquer le retrait/la rétrogradation si c'est le dernier.
- **La contrainte de groupe sur `ProjectMembership` n'est donc plus stricte** : le groupe reste le vivier "par défaut" (facile d'accès, affiché en premier), mais un chef de projet peut faire entrer n'importe qui via les deux mécanismes ci-dessus. Les endpoints `assign`/`claim` sur les tâches n'ont toujours pas besoin de changer — ils continuent de vérifier uniquement que l'assigné a une `ProjectMembership` active, quelle que soit son origine.
- **Sélection de membres à la création d'un projet collaboratif** : le formulaire de création propose, après le choix du groupe, une sélection multiple parmi les membres actifs de ce groupe pour les ajouter directement comme `ProjectMembership` (rôle `membre`) dès la création — pas besoin de repasser par l'onglet Administration juste après pour les cas simples. Les membres externes/comptes externes restent une action post-création, dans l'onglet Administration (formulaire de création volontairement simple).
  - **Correction — tout le groupe coché par défaut (session du 2026-08-06)** : remontée client, le choix initial ("sélection multiple", cases décochées par défaut) obligeait à cocher un par un chaque membre pour le cas le plus courant — "je crée un projet pour mon groupe, tout le monde en fait partie". Le comportement acté devient : **choisir un groupe coche par défaut tous ses membres actifs** (hors le créateur, déjà chef de projet, et hors comptes externes) ; décocher reste possible au cas par cas pour exclure quelqu'un. Changement purement frontend (`ProjectCreateDialog.tsx` — le `onChange` du `<select>` groupe initialise désormais `member_ids` à la liste complète des membres sélectionnables plutôt qu'à `[]`) ; le endpoint `POST /api/v1/projects/` et `create_project` n'ont pas changé, `member_ids` fonctionnait déjà correctement quelle que soit la liste envoyée.

**Précisions actées à l'implémentation :**
- `ProjectMembership.status` (`active`/`removed`) **existait déjà** avant cette session (posé lors d'une passe antérieure, non documentée à l'époque) — aucune migration nécessaire pour ce point précis du chantier, seuls les endpoints/l'UI manquaient.
- Endpoints, tous sous `POST /api/v1/projects/{id}/members/...` (body, pas de sous-ressource dans l'URL au-delà de `role`/`remove`/`invite`) :
  - `POST .../members/` : `{"user": "<id>"}` **ou** `{"email": "...", "role": "membre"|"chef_de_projet"}` — le cas "membre du groupe" et "membre existant hors groupe" partagent le même endpoint (`apps.projects.services.add_project_member`), la seule différence est `user` (déjà résolu par le frontend depuis la liste du groupe) vs `email` (recherche serveur).
  - `POST .../members/role/` : `{"membership": "<id>", "role": "..."}`.
  - `POST .../members/remove/` : `{"membership": "<id>"}`.
  - `POST .../members/invite/` : `{"email": "...", "first_name"?, "last_name"?}` — 3ᵉ cas (personne sans compte), délègue à `apps.accounts.services.create_invitation` (voir "Comptes et invitations").
  - Les trois premiers renvoient le **`Project` complet** (`members` inclus), pas juste la `ProjectMembership` modifiée — permet au frontend de faire `onUpdated(await ...)` uniformément sans requête de re-fetch séparée (même pattern que `NotesTab`).
- **Protection du dernier chef de projet** : `_ensure_not_last_manager()` (`apps/projects/services.py`) — appelée à la fois par le retrait et par le changement de rôle (rétrogradation `chef_de_projet → membre`), pas seulement par le retrait pur, puisque les deux aboutissent au même risque (plus aucun `chef_de_projet` actif).
- **Membres de la sélection à la création (5.6)** : validé côté service (`create_project`, param `member_ids`) que chaque utilisateur sélectionné est bien `TeamMembership` active du groupe choisi — sinon `ProjectValidationError`, pas une insertion silencieuse.

## Comptes et invitations (révisé — création puis activation, comptes internes et externes)

**Statut : implémenté (session du 2026-08-04, soir), remplace la version précédente de cette section.** Flux en deux temps : un admin **crée le compte** (existe en base, `account_status=pending`), puis une **invitation par email active ce compte**. Ce n'est pas l'invitation qui crée le compte.

### Types de compte

- **`User.account_type`** : `interne` (membre normal de l'organisation) / `externe` (invité restreint, voir plus bas).
- **`User.account_status`** : `pending` (compte créé, pas encore activé) / `active` (invitation acceptée).

### Création de compte interne (écran Administration → Membres)

- Réservée à `organisation_role=admin`. Formulaire : nom, email, éventuellement groupe(s) initial(aux) (crée directement les `TeamMembership` correspondantes). Crée le `User` (`account_type=interne`, `account_status=pending`).
- Déclenche l'envoi d'une invitation (voir modèle ci-dessous) pour activation. Un admin peut renvoyer l'invitation si besoin (nouveau `token`, ancien `status=expired`).

### Compte externe restreint à un projet (nouveau — écran Administration du **projet**, pas de l'organisation)

Un chef de projet peut ajouter au projet une personne qui n'a pas de compte dans l'organisation — deux cas, dans le même flux "Inviter" :
- **La personne existe déjà** (recherche par email, compte `interne` d'un autre groupe de la même organisation) : ajout direct en `ProjectMembership`, aucune invitation nécessaire — c'est le cas "externe au groupe du projet, mais dans la même organisation".
- **La personne n'a aucun compte** : crée un `User` avec `account_type=externe`, `account_status=pending`, rattaché à l'organisation du projet (pour la traçabilité administrative) mais **sans droit organisation** (`organisation_role` non pertinent pour ce type de compte — ne jamais lui accorder `admin`/`chef_de_projet`). Une invitation scoée à ce projet est envoyée (voir `Invitation.project` ci-dessous) ; à l'acceptation, la `ProjectMembership` sur ce projet précis est créée directement.
- **Un compte `externe` n'a de visibilité que sur le(s) projet(s) où il a une `ProjectMembership` active** — pas d'accès aux autres projets, pas à l'écran Administration (ni organisation, ni un autre projet), pas listé dans l'annuaire "Membres" de l'organisation comme un membre normal (à afficher séparément ou marqué distinctement s'il apparaît quelque part). Ne compte pas comme éligible pour rejoindre un groupe ou un autre projet.

### Modèle `Invitation`

- `email`, `user` (FK, le compte `pending` concerné), `organisation` (FK), `team` (FK nullable — activation avec rattachement direct à un groupe), `project` (FK nullable — activation avec rattachement direct à ce projet, utilisé pour les comptes `externe`), `invited_by` (FK `User`), `token` (UUID unique), `status` (`pending`/`accepted`/`revoked`/`expired`), `created_at`, `accepted_at`.
- **Qui peut inviter :** `admin` (comptes internes, section Membres) ; `chef_de_projet` niveau organisation (comptes internes rattachés à un groupe dont il est `created_by`) ; chef de projet d'un projet donné (comptes externes scopés à ce projet, ou ajout direct si la personne a déjà un compte).
- **Envoi d'email en dev : backend console Django par défaut** (aucun SMTP configuré tant qu'un `.env` ne le précise pas), cohérent avec le blocage infra déjà en place.
- **Test avec de vrais emails, sans attendre le déploiement (ajouté — session du 2026-08-06).** `config/settings/dev.py` lit désormais `EMAIL_BACKEND`/`EMAIL_HOST`/`EMAIL_PORT`/`EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`/`EMAIL_USE_TLS`/`DEFAULT_FROM_EMAIL` depuis l'environnement (`django-environ`, déjà en place pour `DJANGO_SECRET_KEY`), avec repli sur le backend console si rien n'est renseigné. En créant un `.env` à la racine (voir `.env.example`) avec les identifiants d'une boîte sandbox (ex. Mailtrap, gratuit) et `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, les invitations arrivent pour de vrai dans une boîte de test — utile pour valider le **pattern/contenu** des emails (objet, corps, lien d'activation) avant même le déploiement. **Reste inchangé et toujours reporté au déploiement :** la déliverabilité réelle (vrai domaine d'expédition, DKIM/SPF, fournisseur transactionnel type Mailgun en prod) — ça rejoint le SSO et le webhook ticketing dans la même catégorie de validation bout-en-bout différée. `staging.py`/`production.py` ne sont pas concernés par ce changement (settings 100% locaux à `dev.py`).
- **⚠️ Appel synchrone, exception dev assumée.** `_send_invitation_email` (`apps/accounts/services.py`) appelle `send_mail` de façon synchrone dans le flux de requête HTTP — au sens strict, ça enfreint la règle d'architecture n°2 (CLAUDE.md, "aucun appel synchrone vers un système externe") dès qu'un vrai SMTP est configuré (le backend console, lui, n'est qu'un `print`, donc hors-jeu). Assumé pour l'instant : Celery n'est encore qu'une dépendance déclarée, pas câblée dans ce projet, et l'usage visé ici est un aller-retour ponctuel vers une sandbox de test, pas un flux de production. **Quand le vrai pipeline async (signal Django → tâche Celery) sera construit, cet appel devra y être déplacé** — ne pas considérer le SMTP direct comme le design cible.
- **Endpoints :** `POST /api/v1/invitations/` (crée le `User` `pending` si nécessaire + l'invitation + "envoie"), `GET /api/v1/invitations/{token}/` (public), `POST /api/v1/invitations/{token}/accept/` (public, `password` requis dans le body — voir "Authentification par mot de passe" ci-dessous — passe `User.account_status=active`, crée la `TeamMembership`/`ProjectMembership` selon ce qui est renseigné sur l'invitation, marque `accepted`).

### Authentification par mot de passe (implémenté — session du 2026-08-06)

**Statut : implémenté. Remplace la limite précédemment assumée ("pas de vraie authentification tant que le SSO n'est pas fait")** — remontée client explicite : une vraie page de login est nécessaire dès maintenant, avec la possibilité de "s'inscrire" (activer un compte) sans passer par le SSO. Le SSO Microsoft reste différé (tenant Azure AD réel requis, choix de librairie non tranché) ; cette passe ajoute un mécanisme d'authentification indépendant, **en parallèle** du sélecteur de test `X-Debug-User-Id` — celui-ci n'est pas retiré, il reste utile pour changer rapidement de rôle en test.

- **"S'inscrire" = compléter le flux d'invitation existant**, pas une inscription publique ouverte : un admin/chef de projet crée toujours le compte (`account_status=pending`), l'invité choisit désormais un **mot de passe** au moment d'accepter (`apps.accounts.services.accept_invitation`, validé via `AUTH_PASSWORD_VALIDATORS` déjà configuré) — c'est ce mot de passe qui active un vrai moyen de connexion. `User(AbstractUser)` fournit nativement `set_password`/`check_password`, aucune migration de champ nécessaire.
- **`POST /api/v1/accounts/login/`** (`LoginView`, public) : `{"username", "password"}` → `{"access", "refresh", "user"}`. Utilise `django.contrib.auth.authenticate` (compatible nativement avec `AbstractUser`) puis `rest_framework_simplejwt.tokens.RefreshToken.for_user(user)`. Rejette un compte `account_status != "active"` (compte pas encore activé).
- **`GET /api/v1/accounts/me/`** (`MeView`) : renvoie l'utilisateur authentifié, quel que soit le mécanisme résolu par DRF (JWT, header debug...) — sert au frontend à retrouver "qui je suis" à partir d'un token stocké, sans décoder le JWT côté client.
- **`JWTAuthentication`** ajoutée à `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`, **après** `DebugUserIdAuthentication` : le header debug garde la priorité s'il est présent (bascule rapide en test), le JWT est le mécanisme qui reste utilisable une fois `DEBUG=False`. `SIMPLE_JWT` configuré avec une durée de vie généreuse (`ACCESS_TOKEN_LIFETIME=8h`, `REFRESH_TOKEN_LIFETIME=7j`) — pas de rafraîchissement silencieux implémenté côté frontend dans cette passe, se reconnecter manuellement suffit après expiration.
- **Frontend :** `CurrentUserContext` étendu (pas remplacé) — nouvel état `authUser` distinct de la sélection debug, `currentUser = authUser ?? debugPickedUser`. `login()`/`logout()` exposés par le contexte ; se connecter pour de vrai efface la sélection debug et inversement (un seul mécanisme d'identité actif à la fois). `features/auth/LoginPage.tsx` (nouvelle page pleine, pas de sidebar/topbar — même traitement que `InvitationAcceptPage`) atteignable depuis `UserMenu` ("Se connecter"/"Déconnexion", à côté du sélecteur de test inchangé).
- **Hors périmètre explicite de cette passe :** rafraîchissement silencieux du token, réinitialisation de mot de passe ("mot de passe oublié"), inscription publique ouverte, mot de passe pour les comptes déjà `active` créés hors flux d'invitation (reste accessible via `manage.py changepassword <username>` ou l'admin Django, déjà disponibles nativement). `django-allauth` (déjà une dépendance déclarée) et le choix de librairie SSO restent réservés au futur chantier SSO, non touchés ici.

**Précisions actées à l'implémentation :**
- **`Invitation.project` référence `apps.projects.Project` par chaîne** (`"projects.Project"`), pas par import direct : `apps.accounts` ne doit jamais importer `apps.projects` (accounts est plus bas dans la hiérarchie de dépendances). Une FK par chaîne est une référence de schéma résolue paresseusement par Django (aucun `import` Python de `apps.projects` dans `accounts/models.py`), pas un couplage de code — ne viole donc pas la règle, qui porte sur le couplage de service/logique métier. Même raisonnement pour la vérification de permission dans `create_invitation` (import de `apps.projects.models.ProjectMembership` **local à la fonction**, pas en tête de module) et pour `accept_invitation`.
- **Deux endpoints de création distincts plutôt qu'un seul avec un champ `project` optionnel**, pour rester cohérent avec la contrainte ci-dessus sans introduire de résolution d'UUID cross-app côté serializer :
  - `POST /api/v1/accounts/invitations/` (`apps.accounts`) : comptes **internes** uniquement (`email`, `first_name`?, `last_name`?, `team`?). Réservé à `organisation_role=admin` (n'importe quel groupe) ou `chef_de_projet` (uniquement vers un groupe dont il est `created_by`).
  - `POST /api/v1/projects/{id}/members/invite/` (`apps.projects`, section précédente) : comptes **externes** scopés à ce projet. `apps.projects` a le droit d'importer `apps.accounts` (sens de dépendance autorisé) et a déjà l'instance `Project` résolue via `self.get_object()` — pas besoin de la faire transiter par `apps.accounts`.
  - Les deux appellent la **même** fonction de service (`apps.accounts.services.create_invitation`, paramètre `team` ou `project` mutuellement pertinent selon l'appelant), donc aucune logique dupliquée malgré les deux points d'entrée HTTP.
- **`GET /api/v1/accounts/invitations/` (liste)** : endpoint non explicitement demandé par ce fichier mais nécessaire pour que la sous-section "Invitations" de l'écran Administration organisation ait quelque chose à afficher (statut des invitations en cours). Scopé à `request.user.organisation`, réservé à `admin`/`chef_de_projet` — ajouté comme complément direct de la fonctionnalité déjà actée, pas une extension de périmètre.
- **`POST /api/v1/accounts/invitations/{token}/resend/`** : idem, complète "un admin peut renvoyer l'invitation si besoin" — marque l'ancienne `expired`, crée une nouvelle ligne avec un nouveau `token` (jamais de mutation de l'ancienne au-delà de son statut, cohérent avec "aucune suppression physique").
- **Envoi d'email synchrone (pas de signal → tâche Celery)**, alors que la règle d'architecture n°2 de ce fichier impose ce pattern pour "tout appel vers un système externe" : jugé non applicable ici, le backend console (déjà configuré dans `config/settings/dev.py`, présent avant cette session) n'effectue aucune I/O réseau réelle — c'est un `print`, pas un appel externe. Celery n'est d'ailleurs pas encore câblé dans ce projet (aucun `celery.py`, aucun `@shared_task`, tous les `signals.py` sont des stubs vides) — le mettre en place aurait été un chantier d'infra à part entière, hors du périmètre "backend console suffit pour vérifier que le flux fonctionne" déjà acté dans ce fichier. À revoir quand un vrai fournisseur transactionnel sera branché en prod (rejoint la liste "validation reportée au déploiement" en fin de fichier).
- **Restriction de visibilité des comptes `externe` (chantier 6.7) — implémentée partiellement, limite documentée plutôt qu'improvisée :**
  - ✅ Exclus de l'annuaire "Membres" de l'organisation (`MembersSection`) et des pickers "ajouter un membre" (`GroupsSection`, sélection de membres à la création de projet) — filtrage sur `account_type === "interne"` côté frontend.
  - ✅ Un compte `pending` (interne ou externe) n'est pas sélectionnable dans le sélecteur `X-Debug-User-Id` (`UserMenu`) tant que son invitation n'est pas acceptée.
  - ✅ Un badge "Externe" est affiché dans l'onglet Administration du projet.
  - ❌ **"N'ont accès qu'aux projets où ils ont une `ProjectMembership` active" n'est pas appliqué** — `GET /api/v1/projects/` retourne aujourd'hui tous les projets à n'importe quel utilisateur authentifié, **externe ou interne**. Ce n'est pas une règle spécifique aux comptes externes qui manquerait : c'est qu'**aucun** filtrage par appartenance n'existe nulle part dans l'API des projets, pour personne. L'ajouter uniquement pour `account_type=externe` créerait une incohérence (un compte interne verrait plus de projets qu'un compte externe sans qu'aucune règle de ce genre n'existe par ailleurs) sans résoudre le vrai sujet (accès aux projets en général, pour tous les types de compte). Documenté ici comme limite ouverte — chantier de contrôle d'accès à part entière, pas un correctif ponctuel pour ce cas précis.

