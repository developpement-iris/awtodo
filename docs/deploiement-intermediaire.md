# Watodo — Déploiement intermédiaire (Render + Supabase + UptimeRobot)

**Statut : acté, session du 06/08/2026.** Phase de test en conditions réelles (SSO, webhook ticketing) avant le déploiement définitif sur AWS. Référencé depuis CLAUDE.md — à lire uniquement pour les tâches touchant à cette phase de déploiement, pas à chaque session.

## Pourquoi cette phase existe

Le SSO Microsoft et le webhook ticketing entrant ont besoin d'une URL HTTPS publique stable pour être testés réellement — impossible en local. Plutôt que de sauter directement sur AWS (encore bloqué, voir plus bas), une étape intermédiaire sur des services gratuits permet de tester en conditions réelles sans la complexité AWS.

## Infrastructure déjà en place (ne pas recréer)

- **Repo GitHub** : `https://github.com/developpement-iris/awtodo`
- **Projet Supabase (Postgres)** : `https://viiezyqjigwmaqxmylyo.supabase.co`
- **Render** : en cours de configuration par l'utilisateur — c'est l'objet de cette passe.

## ⚠️ Ce que Claude Code peut faire, et ce qu'il ne peut pas faire

**Peut faire (écrire du code/config) :**
- `render.yaml` (blueprint Render — permet de décrire les services en infra-as-code, lu automatiquement si le repo est connecté en mode Blueprint)
- `Dockerfile` (recommandé plutôt que le buildpack natif de Render — même image réutilisable telle quelle sur AWS App Runner plus tard, pas de double travail de conteneurisation)
- `config/settings/staging.py` (nouveau — voir plus bas, ce blocage est levé spécifiquement pour Render/Supabase, pas pour AWS/RDS)
- L'endpoint de santé `/api/health/` (voir plus bas)
- Configuration CORS/`ALLOWED_HOSTS`, `whitenoise` pour les fichiers statiques (voir plus bas)
- La liste exacte des variables d'environnement à renseigner, avec leur nom et leur provenance — **pas leur valeur secrète**

**Ne peut pas faire (nécessite une action humaine dans un navigateur) :**
- Se connecter au tableau de bord Render ou Supabase
- Créer les services Render, copier les clés/tokens réels
- Coller les valeurs de secrets dans l'interface Render
- Configurer le monitor UptimeRobot (interface web, pas de CLI)

**Conséquence pratique :** à la fin d'une session sur ce chantier, Claude Code doit produire une **liste claire d'actions manuelles restantes** (variables à copier depuis Supabase vers Render, etc.), pas juste dire "c'est fait".

## Levée de blocage partielle — BDD et déploiement

Le blocage initial ("ne pas créer de `settings/staging.py`/`production.py` avec des paramètres concrets, ne pas ajouter de dépendances de déploiement") est **levé spécifiquement pour Render/Supabase**. **Il reste en vigueur pour AWS/RDS** — ne pas écrire de configuration AWS (`boto3`, `django-storages`, S3, App Runner) dans cette passe, ce n'est toujours pas le sujet.

## Ce qu'il faut construire

### 1. `config/settings/staging.py`
- `DEBUG = False`
- `DATABASE_URL` lue depuis une variable d'environnement (format Supabase), **avec `sslmode=require`** — Supabase exige une connexion SSL, une erreur de connexion silencieuse sinon.
- `ALLOWED_HOSTS` et `CORS_ALLOWED_ORIGINS` : domaines Render réels une fois les services créés (ex. `awtodo-api.onrender.com`, `awtodo-frontend.onrender.com` — noms exacts à confirmer une fois les services nommés dans Render).
- `SECRET_KEY` lue depuis une variable d'environnement, jamais en dur.
- Fichiers statiques servis via **`whitenoise`** (pas de S3 — toujours bloqué) : simple, suffisant pour cette phase de test.
- ⚠️ **Les fichiers médias uploadés ne persisteront pas entre deux déploiements** sur le système de fichiers éphémère de Render (sans S3). Acceptable pour cette phase de test, à signaler dans le compte-rendu — pas un bug, une limite connue.

### 2. Endpoint de santé `/api/health/`
- Exécute une requête DB légère (ex. `SELECT 1` ou un `.count()` simple) — **pas un simple `return 200` statique**, il doit toucher réellement la base.
- Sert de cible unique au monitor UptimeRobot : un ping toutes les ~10 minutes satisfait à la fois le seuil de veille Render (15 min) et le seuil de pause Supabase (7 jours d'inactivité mesurée en requêtes DB réelles) — un seul monitor, pas deux à gérer séparément.

### 3. `render.yaml` (blueprint)
- Décrit deux services : un web service (Django, via Dockerfile) et un static site (frontend React/Vite build).
- Rappel : les valeurs de secrets (SECRET_KEY, DATABASE_URL, credentials Azure AD futurs) se configurent dans l'interface Render, pas dans ce fichier versionné.

### 4. Compte-rendu attendu à la fin de la passe
Liste précise des actions manuelles restantes pour l'utilisateur : quelles variables copier depuis quel tableau de bord vers quel autre, dans quel ordre, et comment configurer le monitor UptimeRobot (URL à pinguer = l'endpoint `/api/health/` en production, fréquence ~10 min).

## État au 2026-09-09 — fichiers construits

Passe réalisée. **Écarts vs le plan initial ci-dessus, validés avec l'utilisateur :**
- **Un seul service Render** (pas deux) : le frontend React est **servi par Django** via WhiteNoise, même origine que l'API. Plus de `CORS` à gérer, plus de static site séparé.
- **Runtime natif Render** (pas de Dockerfile) : l'environnement Python de Render fournit Node, le build Vite se fait dans `buildCommand`. Conséquence assumée : rien de réutilisable tel quel pour AWS App Runner — la conteneurisation sera à faire au moment du chantier AWS.
- **`config/settings/staging.py`** est la cible Render (et non `production.py`, laissé intact pour AWS/RDS). Render sélectionne via `DJANGO_SETTINGS_MODULE=config.settings.staging`.

Fichiers ajoutés / modifiés :
| Fichier | Rôle |
|---|---|
| `config/settings/staging.py` | Réglages Render : `DEBUG=False`, secrets via env, Supabase `sslmode=require` + `CONN_MAX_AGE=0` + `DISABLE_SERVER_SIDE_CURSORS` (compat pooler pgbouncer), WhiteNoise (statiques Django **et** build Vite), en-têtes de sécurité derrière proxy, logs stdout, SMTP par env. |
| `config/health.py` + route `/api/health/` | Health check qui exécute un `SELECT 1` réel. Cible unique UptimeRobot. |
| `config/spa.py` + fallback `re_path` dans `config/urls.py` | Renvoie `frontend/dist/index.html` sur toute route non-API/non-admin (routage client : `/docs/<token>`, invitations…). Inactif en dev (aucun `SPA_INDEX_FILE`). |
| `requirements/staging.txt` | `-r base.txt` + `gunicorn` + `whitenoise`. |
| `render.yaml` | Blueprint : 1 web service, `buildCommand` (pip + npm build + collectstatic + migrate), `startCommand` gunicorn, `healthCheckPath: /api/health/`, liste des env vars (secrets en `sync: false`). |
| `.env.example` | Section de référence des variables Render (commentée). |

**Vérifié en local :** settings staging s'importent sans erreur (psycopg accepte les options), `/api/health/` répond `200 {"status":"ok"}`. **Non vérifiable en local :** le build frontend dans l'environnement Render (présence de `npm`), la connexion Supabase réelle.

## Actions manuelles restantes (utilisateur)

1. **Supabase — récupérer la connection string.** Dashboard Supabase > projet `viiezyqjigwmaqxmylyo` > *Project Settings* > *Database* > *Connection string* > onglet **URI**. Copier la valeur (format `postgres://postgres:[MOT_DE_PASSE]@db.viiezyqjigwmaqxmylyo.supabase.co:5432/postgres`). Si le mot de passe DB n'est pas connu : *Reset database password* sur la même page.
   - Préférer la connexion **directe** (port `5432`) ou le *Session pooler*. Le staging est déjà configuré pour tolérer le *Transaction pooler* (port `6543`) si besoin.
2. **Render — créer le service depuis le blueprint.** Dashboard Render > *New* > *Blueprint* > connecter le repo `developpement-iris/awtodo`, branche `main`. Render lit `render.yaml` et propose le service `awtodo`.
3. **Render — renseigner les variables `sync: false`** (écran de création du blueprint, ou *Environment* après coup) :
   | Variable | Valeur |
   |---|---|
   | `DJANGO_ALLOWED_HOSTS` | le domaine attribué, ex. `awtodo.onrender.com` (visible après la 1ʳᵉ création — si besoin, mettre une valeur provisoire puis corriger) |
   | `CSRF_TRUSTED_ORIGINS` | `https://awtodo.onrender.com` |
   | `FRONTEND_BASE_URL` | `https://awtodo.onrender.com` |
   | `DATABASE_URL` | l'URI Supabase de l'étape 1 |
   | `EMAIL_*` / `DEFAULT_FROM_EMAIL` | optionnel (Mailtrap sandbox), sinon laisser vide → backend console |
   - `DJANGO_SECRET_KEY` est généré automatiquement par Render, ne rien saisir.
   - `DJANGO_SETTINGS_MODULE` et `PYTHON_VERSION` sont déjà dans le blueprint.
4. **Premier déploiement.** Render lance `buildCommand` puis `startCommand`. Le `buildCommand` passe `--settings=config.settings.staging` explicitement à `collectstatic`/`migrate` (ne pas compter uniquement sur la var d'env au build). Vérifier quand même que `DJANGO_SETTINGS_MODULE=config.settings.staging` est bien présent dans *Environment* (utilisé au runtime par gunicorn). Surveiller les logs :
   - si `npm: command not found` au build → Node absent de l'image Python Render : basculer le service en *Docker* avec un Dockerfile (à écrire), ou builder `frontend/dist` en local et le commiter (retirer `frontend/dist` du `.gitignore`).
   - `migrate` s'exécute à chaque build ; les migrations Awtodo tournent sur une base Supabase vierge au 1ᵉʳ coup.
5. **Créer un compte de départ.** Shell Render (*Shell* dans le dashboard) : `python manage.py createsuperuser` (admin Django) et/ou `python manage.py seed_demo_users` si on veut les comptes de démo.
6. **Vérifier :** ouvrir `https://awtodo.onrender.com/api/health/` → doit répondre `{"status": "ok", "database": "ok"}`. Ouvrir la racine → le frontend doit se charger.
7. **UptimeRobot — monitor.** uptimerobot.com > *Add New Monitor* > type **HTTP(s)** > URL `https://awtodo.onrender.com/api/health/` > *Monitoring Interval* **5 minutes** (le plan gratuit ne descend pas sous 5 min ; ça couvre le seuil de veille Render de 15 min et l'inactivité Supabase de 7 j). Un seul monitor suffit.

**Limite connue à signaler :** les fichiers médias uploadés (`MEDIA`) ne survivent pas à un redéploiement (disque éphémère Render, pas de S3 dans cette phase). Sans impact sur les tests SSO / webhook ticketing visés.

## Rappel — toujours valable

- SSO Microsoft et webhook ticketing : testables une fois cette phase en place (URL HTTPS stable enfin disponible), mais leur implémentation applicative reste un chantier à part, pas couvert ici.
- Déploiement AWS définitif : toujours hors périmètre, reste la cible finale une fois cette phase de test validée.
