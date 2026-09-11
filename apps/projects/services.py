import contextvars
from contextlib import contextmanager

from django.utils import timezone

from apps.accounts.models import TeamMembership, User
from apps.common.permissions import check_permission

from .models import Project, ProjectMembership, ProjectVersion, SpecSection


# --- Cache d'appartenances pour la sérialisation d'une liste --------------
# Le bloc `permissions` renvoyé sur chaque ligne d'une liste (projets, tâches,
# incidents) est calculé par ~10 fonctions de garde qui appellent toutes
# `is_project_member/contributor/manager` — soit ~10 `SELECT EXISTS` par ligne
# si on n'y prend pas garde (mesuré : ~1000 requêtes pour 100 tâches).
#
# `prefetched_project_roles(user, project_ids)` résout en UNE requête les
# rôles de `user` sur tous les projets d'une page, et les trois helpers
# ci-dessous consultent ce cache pendant le bloc. **En dehors de ce bloc,
# comportement strictement inchangé** : le chemin "un seul objet" (détail,
# ré-sérialisation après mutation, fonctions de garde des actions) requête
# comme avant, aucune signature ne change.
_ROLES_CACHE: contextvars.ContextVar = contextvars.ContextVar("project_roles_cache", default=None)


def project_roles_for(user, project_ids):
    """`{project_id: frozenset(rôles actifs de `user`)}` en une seule requête.
    Un projet absent du dict = aucune appartenance active."""
    if user is None or not getattr(user, "is_authenticated", False):
        return {}
    acc: dict = {}
    for pid, role in ProjectMembership.objects.filter(
        user=user, project_id__in=list(project_ids), status="active"
    ).values_list("project_id", "role"):
        acc.setdefault(pid, set()).add(role)
    return {pid: frozenset(roles) for pid, roles in acc.items()}


@contextmanager
def prefetched_project_roles(user, project_ids):
    """À enrouler autour de la sérialisation d'une liste (voir les `list()`
    des viewsets). Hors de ce bloc, `_cached_roles` renvoie `None` et les
    helpers requêtent normalement."""
    token = _ROLES_CACHE.set((getattr(user, "id", None), project_roles_for(user, project_ids)))
    try:
        yield
    finally:
        _ROLES_CACHE.reset(token)


def _cached_roles(user, project):
    """Rôles de `user` sur `project` si un cache est actif ET concerne le bon
    utilisateur, sinon `None` (→ requête)."""
    cached = _ROLES_CACHE.get()
    if cached is None:
        return None
    cached_user_id, roles_map = cached
    if cached_user_id != getattr(user, "id", None):
        return None
    return roles_map.get(project.id, frozenset())


class ProjectPermissionError(Exception):
    """L'acteur n'a pas le droit d'effectuer cette action."""


class ProjectValidationError(Exception):
    """Les données fournies ne permettent pas de créer le projet."""


_PROJECT_EXCEPTIONS = (ProjectPermissionError, ProjectValidationError)


def _check(fn, *args):
    return check_permission(fn, *args, catch=_PROJECT_EXCEPTIONS)


def _require_actor(actor):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise ProjectPermissionError("Utilisateur non identifié.")


def accessible_projects(user):
    """Projets visibles par `user` — voir CLAUDE.md > "Scoping des listes par
    appartenance". Un utilisateur ne voit que les projets où il a une
    `ProjectMembership` active ; `is_platform_admin` voit tout (y compris
    `organisation_role=admin`, qui ne bénéficie d'aucune exception).

    **Inclut les membres `lecteur`** (session du 2026-09-10) : un lecteur voit
    le projet, son détail et ses tâches. Pour le scoping des écrans dont un
    lecteur est exclu (budget, incidents, planning, documentation, stats
    globales), utiliser `contributor_projects` ci-dessous, pas cette fonction.

    Statut-agnostique délibérément (`all_objects`, pas `.active()`) : un
    projet clôturé reste consultable (voir docs/modeles-et-api.md > "Clôture
    de projet") — c'est `ProjectFilterSet`/`ProjectViewSet` qui décide quels
    statuts apparaissent dans la liste par défaut (voir "Filtre d'état
    généralisé"), pas la portée par appartenance elle-même."""
    if user is None or not getattr(user, "is_authenticated", False):
        return Project.all_objects.none()
    if getattr(user, "is_platform_admin", False):
        return Project.all_objects.all()
    return Project.all_objects.filter(memberships__user=user, memberships__status="active").distinct()


def contributor_projects(user):
    """Comme `accessible_projects`, mais **exclut les appartenances `lecteur`**
    — portée des écrans qu'un lecteur ne voit pas (budget, incidents,
    planning, documentation, statistiques globales). Un `is_platform_admin`
    voit toujours tout."""
    if user is None or not getattr(user, "is_authenticated", False):
        return Project.all_objects.none()
    if getattr(user, "is_platform_admin", False):
        return Project.all_objects.all()
    return Project.all_objects.filter(
        memberships__user=user,
        memberships__status="active",
        memberships__role__in=ProjectMembership.CONTRIBUTOR_ROLES,
    ).distinct()


def is_project_member(user, project):
    """Toute appartenance active, `lecteur` compris — pour le scoping des
    listes/détails (voir CLAUDE.md > "Scoping des listes par appartenance").
    Pour savoir si l'utilisateur peut *agir* sur le projet, utiliser
    `is_project_contributor`."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    roles = _cached_roles(user, project)
    if roles is not None:
        return len(roles) > 0
    return ProjectMembership.objects.filter(project=project, user=user, status="active").exists()


def is_project_contributor(user, project):
    """Appartenance active avec un rôle qui peut agir (`chef_de_projet` ou
    `membre`, pas `lecteur`) — base de toutes les fonctions de garde en
    écriture. Aussi importée telle quelle par `apps.tasks`/`apps.incidents`
    (autorisées à dépendre de `apps.projects`)."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    roles = _cached_roles(user, project)
    if roles is not None:
        return bool(roles & ProjectMembership.CONTRIBUTOR_ROLES)
    return ProjectMembership.objects.filter(
        project=project, user=user, status="active", role__in=ProjectMembership.CONTRIBUTOR_ROLES
    ).exists()


def is_project_manager(user, project):
    """Version publique de la règle "chef de projet de ce projet", sans lever
    d'exception — pour les apps qui ont le droit d'importer `apps.projects`
    (`tasks`, `budgeting`, plus bas dans la hiérarchie de dépendances) et ont
    besoin de la même règle sans dupliquer la requête `ProjectMembership`."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    roles = _cached_roles(user, project)
    if roles is not None:
        return "chef_de_projet" in roles
    return ProjectMembership.objects.filter(
        project=project, user=user, status="active", role="chef_de_projet"
    ).exists()


def _require_member(actor, project):
    """Toute appartenance active — `lecteur` compris. À réserver aux actions
    de pure lecture qu'un lecteur a le droit de faire (lire le cahier des
    charges). Toute action en écriture passe par `_require_contributor`."""
    _require_actor(actor)
    if not is_project_member(actor, project):
        raise ProjectPermissionError("Seul un membre du projet peut effectuer cette action.")


def _require_contributor(actor, project):
    _require_actor(actor)
    if not is_project_contributor(actor, project):
        raise ProjectPermissionError("Seul un membre du projet (hors lecture seule) peut effectuer cette action.")


def _require_manager(actor, project):
    _require_actor(actor)
    if not is_project_manager(actor, project):
        raise ProjectPermissionError("Seul un chef de projet de ce projet peut effectuer cette action.")


# --- Fonctions de garde ---------------------------------------------------
# Même pattern que `apps.tasks.services`/`apps.incidents.services` : seule
# source de vérité pour chaque règle, réutilisée par l'action réelle et par
# le flag `can_*` correspondant (voir `get_project_permissions`).


def _ensure_can_edit_notes(actor, project):
    _require_contributor(actor, project)


def _ensure_can_manage_members(actor, project):
    _require_manager(actor, project)


def _ensure_can_close(actor, project):
    _require_manager(actor, project)
    if project.status != "actif":
        raise ProjectValidationError("Seul un projet actif peut être clôturé.")


def _ensure_can_reopen(actor, project):
    _require_manager(actor, project)
    if project.status != "cloture":
        raise ProjectValidationError("Seul un projet clôturé peut être réouvert.")


def _ensure_can_create_version(actor, project):
    _require_manager(actor, project)


def _ensure_can_manage_budget(actor, project):
    _require_manager(actor, project)


def _ensure_can_edit_documentation(actor, project):
    _require_manager(actor, project)


def _ensure_can_manage_project_planning(actor, project):
    _require_manager(actor, project)


def _ensure_can_manage_project_communication(actor, project):
    # Configuration des canaux de communication (adresses mail, canaux Teams,
    # connexion Office 365) — réservée au chef de projet. Voir apps.communication.
    _require_manager(actor, project)


def _ensure_can_send_project_communication(actor, project):
    # Rédiger et envoyer une communication — ouvert à tout contributeur
    # (chef de projet ou membre), pas aux lecteurs.
    _require_contributor(actor, project)


def can_edit_spec(user, project):
    return _check(_ensure_can_edit_notes, user, project)


def can_edit_notepad(user, project):
    return _check(_ensure_can_edit_notes, user, project)


def can_manage_members(user, project):
    return _check(_ensure_can_manage_members, user, project)


def can_close(user, project):
    return _check(_ensure_can_close, user, project)


def can_reopen(user, project):
    return _check(_ensure_can_reopen, user, project)


def can_create_version(user, project):
    return _check(_ensure_can_create_version, user, project)


def can_manage_budget(user, project):
    return _check(_ensure_can_manage_budget, user, project)


def can_edit_documentation(user, project):
    return _check(_ensure_can_edit_documentation, user, project)


def can_manage_project_planning(user, project):
    return _check(_ensure_can_manage_project_planning, user, project)


def can_manage_project_communication(user, project):
    return _check(_ensure_can_manage_project_communication, user, project)


def can_send_project_communication(user, project):
    return _check(_ensure_can_send_project_communication, user, project)


def get_project_permissions(user, project):
    return {
        # `false` pour un membre `lecteur` : le frontend s'en sert pour masquer
        # entièrement les onglets Budget/Incidents/Planning/Statistiques et
        # toutes les affordances de création/édition (voir
        # docs/organisation-et-comptes.md > "Rôle Lecteur").
        "can_contribute": is_project_contributor(user, project),
        "can_edit_spec": can_edit_spec(user, project),
        "can_edit_notepad": can_edit_notepad(user, project),
        "can_manage_members": can_manage_members(user, project),
        "can_close": can_close(user, project),
        "can_reopen": can_reopen(user, project),
        "can_create_version": can_create_version(user, project),
        "can_manage_budget": can_manage_budget(user, project),
        "can_edit_documentation": can_edit_documentation(user, project),
        "can_manage_project_planning": can_manage_project_planning(user, project),
        "can_manage_project_communication": can_manage_project_communication(user, project),
        "can_send_project_communication": can_send_project_communication(user, project),
    }


def close_project(*, actor, project):
    _ensure_can_close(actor, project)
    project.status = "cloture"
    project.save(update_fields=["status"])
    return project


def reopen_project(*, actor, project):
    _ensure_can_reopen(actor, project)
    project.status = "actif"
    project.save(update_fields=["status"])
    return project


def get_current_version(project):
    """Utilisé par `apps.tasks.services.create_task` pour attribuer
    automatiquement la version courante à toute nouvelle tâche — jamais
    choisie manuellement (voir docs/modeles-et-api.md > "ProjectVersion")."""
    return ProjectVersion.objects.filter(project=project, is_current=True).first()


def create_project_version(*, actor, project, label):
    """Créer une version la fait automatiquement devenir la courante — pas de
    toggle séparé, les deux actions n'en font qu'une (voir docs/modeles-et-api.md)."""
    _ensure_can_create_version(actor, project)
    if not label or not label.strip():
        raise ProjectValidationError("Le libellé de la version est obligatoire.")

    ProjectVersion.objects.filter(project=project, is_current=True).update(is_current=False)
    return ProjectVersion.objects.create(project=project, label=label.strip(), is_current=True, created_by=actor)


def create_project(
    *,
    actor,
    name,
    project_type,
    description="",
    deadline=None,
    priority=None,
    team=None,
    member_ids=None,
    already_in_production=False,
):
    _require_actor(actor)

    if already_in_production and deadline is not None:
        raise ProjectValidationError(
            "Un projet déjà en production n'a pas de date d'échéance — l'un ou l'autre, pas les deux."
        )

    if project_type == "collaboratif":
        if team is None:
            raise ProjectValidationError("Un projet collaboratif doit être rattaché à un groupe.")
        if not TeamMembership.objects.filter(team=team, user=actor).exists():
            raise ProjectPermissionError("Vous devez être membre du groupe pour y rattacher un projet.")
    elif team is not None:
        raise ProjectValidationError("Un projet individuel ne peut pas être rattaché à un groupe.")

    if member_ids and project_type != "collaboratif":
        raise ProjectValidationError("La sélection de membres n'est possible que pour un projet collaboratif.")

    # `member_ids` arrive déjà résolu en instances `User` par le serializer
    # (PrimaryKeyRelatedField), pas en UUIDs bruts.
    members_to_add = []
    if member_ids:
        team_member_user_ids = set(
            TeamMembership.objects.filter(team=team, user__in=member_ids).values_list("user_id", flat=True)
        )
        for user in member_ids:
            if user.id not in team_member_user_ids:
                raise ProjectValidationError(
                    f"{user.username} n'est pas membre actif du groupe rattaché au projet."
                )
            if user.id != actor.id:
                members_to_add.append(user)

    project = Project.objects.create(
        name=name,
        description=description,
        project_type=project_type,
        deadline=deadline,
        already_in_production=already_in_production,
        priority=priority,
        team=team,
        organisation=actor.organisation,
    )
    ProjectMembership.objects.create(project=project, user=actor, role="chef_de_projet")
    for user in members_to_add:
        ProjectMembership.objects.create(project=project, user=user, role="membre")
    # Invariant à maintenir partout : un projet a toujours une version
    # courante, pour que `create_task` puisse toujours en trouver une (voir
    # `get_current_version`) — pas seulement les projets nés avant ce chantier
    # (backfillés par migration), aussi ceux créés à partir de maintenant.
    ProjectVersion.objects.create(project=project, label="v1", is_current=True, created_by=actor)
    return project


def _ensure_not_last_manager(project, exclude_membership):
    """Empêche qu'un projet se retrouve sans aucun chef de projet actif (voir
    CLAUDE.md > "Onglet Administration sur le hub projet")."""
    other_managers = ProjectMembership.objects.filter(project=project, role="chef_de_projet").exclude(
        pk=exclude_membership.pk
    )
    if not other_managers.exists():
        raise ProjectValidationError("Le projet doit toujours avoir au moins un chef de projet actif.")


def add_project_member(*, actor, project, user=None, email=None, role="membre"):
    """Réservé aux chefs de projet de ce projet précis. Deux cas couverts ici
    (voir CLAUDE.md > "Onglet Administration sur le hub projet") : membre du
    groupe (le cas le plus simple, `user` déjà résolu côté frontend) ou membre
    existant de la même organisation trouvé par email, même hors du groupe.
    Le 3ᵉ cas (invitation d'une personne sans compte) est traité par
    `apps.accounts.services.create_invitation`, pas ici — hors périmètre de
    cette fonction, qui ne gère que des comptes déjà existants."""
    _ensure_can_manage_members(actor, project)

    if user is None:
        try:
            user = User.objects.get(email__iexact=email, organisation=project.organisation)
        except User.DoesNotExist:
            raise ProjectValidationError(
                "Aucun compte existant avec cet email dans votre organisation. "
                "Utilisez l'invitation pour un compte externe."
            )
    elif user.organisation_id != project.organisation_id:
        raise ProjectValidationError("Cet utilisateur n'appartient pas à la même organisation que le projet.")

    # `get_or_create` sur `(project, user, role)` : sans ce garde-fou, ajouter
    # quelqu'un déjà membre avec un rôle différent (ex. `lecteur` sur un
    # `membre`) créerait une 2ᵉ ligne d'appartenance active — incohérent.
    # Changer le rôle passe par `change_project_member_role`, pas par un
    # nouvel ajout.
    existing = ProjectMembership.objects.filter(project=project, user=user, status="active").first()
    if existing is not None:
        if existing.role == role:
            return existing
        raise ProjectValidationError(
            "Cette personne est déjà membre du projet — modifiez son rôle plutôt que de l'ajouter à nouveau."
        )

    return ProjectMembership.objects.create(project=project, user=user, role=role)


def change_project_member_role(*, actor, membership, role):
    _ensure_can_manage_members(actor, membership.project)
    valid_roles = {choice for choice, _ in ProjectMembership.ROLE_CHOICES}
    if role not in valid_roles:
        raise ProjectValidationError("Rôle de projet invalide.")

    if membership.role == "chef_de_projet" and role != "chef_de_projet":
        _ensure_not_last_manager(membership.project, exclude_membership=membership)

    membership.role = role
    membership.save(update_fields=["role"])
    return membership


def remove_project_member(*, actor, membership):
    _ensure_can_manage_members(actor, membership.project)
    if membership.role == "chef_de_projet":
        _ensure_not_last_manager(membership.project, exclude_membership=membership)

    membership.status = "removed"
    membership.save(update_fields=["status"])
    return membership


def update_project_notepad(*, actor, project, notepad_content):
    """Édition libre du bloc-notes par tout membre du projet. Le cahier des
    charges, lui, est structuré en sous-sections — voir `get_spec_sections`/
    `update_spec_section` ci-dessous, pas ce champ."""
    _ensure_can_edit_notes(actor, project)

    project.notepad_content = notepad_content
    project.notepad_updated_at = timezone.now()
    project.save(update_fields=["notepad_content", "notepad_updated_at"])
    return project


def _spec_section_payload(section_key, section):
    label = dict(SpecSection.SECTION_CHOICES)[section_key]
    return {
        "section_key": section_key,
        "label": label,
        "is_active": section.is_active if section else False,
        "content": section.content if section else "",
        "updated_at": section.updated_at if section else None,
    }


def get_spec_sections(*, actor, project):
    """Onglet "Cahier des charges" du hub projet (voir CLAUDE.md > "Projets
    — Hub complet") — les 12 sous-sections fixes, avec leur état
    coché/décoché et leur contenu s'ils ont déjà été touchés (sinon
    synthétisées à `is_active=False`/`content=""`, sans créer de ligne en
    base pour une simple lecture)."""
    _require_member(actor, project)
    existing = {section.section_key: section for section in SpecSection.objects.filter(project=project)}
    return [_spec_section_payload(key, existing.get(key)) for key, _ in SpecSection.SECTION_CHOICES]


def update_spec_section(*, actor, project, section_key, is_active=None, content=None):
    """Coche/décoche une sous-section (`is_active`) et/ou modifie son
    contenu — mêmes droits que le reste du cahier des charges (tout membre
    du projet). La ligne est créée à la demande (`get_or_create`) : pas de
    pré-création des 12 sections à la création du projet."""
    _ensure_can_edit_notes(actor, project)

    valid_keys = {key for key, _ in SpecSection.SECTION_CHOICES}
    if section_key not in valid_keys:
        raise ProjectValidationError("Section de cahier des charges invalide.")

    section, _created = SpecSection.objects.get_or_create(project=project, section_key=section_key)
    if is_active is not None:
        section.is_active = is_active
    if content is not None:
        section.content = content
    section.save()
    return _spec_section_payload(section_key, section)
