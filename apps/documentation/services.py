import re
import secrets

from django.utils.text import slugify

from apps.projects.models import SpecSection
from apps.projects.services import is_project_manager, is_project_member

from .models import DocEntry, DocPage, DocSpace, PendingDocEntry


class DocsPermissionError(Exception):
    pass


class DocsValidationError(Exception):
    pass


_UNSET = object()
_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")


def _require_member(actor, project):
    if actor is None or not getattr(actor, "is_authenticated", False) or not is_project_member(actor, project):
        raise DocsPermissionError("Seul un membre du projet peut consulter sa documentation.")


def _require_manager(actor, project):
    if actor is None or not getattr(actor, "is_authenticated", False) or not is_project_manager(actor, project):
        raise DocsPermissionError("Seul un chef de projet peut modifier la documentation.")


def _generate_token(slug=""):
    """Le suffixe aléatoire (24 octets d'entropie, comme avant) est ce qui
    rend le lien non devinable — `slug`, lisible, n'est qu'un préfixe
    cosmétique optionnel (session du 2026-09-23, retour direct : "on doit
    pouvoir personnaliser l'URL dans la mesure du possible", en gardant le
    token secret). Toujours un seul champ/une seule recherche exacte côté
    lookup public — pas de logique de découpage fragile."""
    suffix = secrets.token_urlsafe(24)
    return f"{slug}-{suffix}" if slug else suffix


def get_or_create_space(*, actor, project):
    _require_member(actor, project)
    space, _ = DocSpace.objects.get_or_create(project=project)
    return space


def _space_for_manager(actor, project):
    _require_manager(actor, project)
    space, _ = DocSpace.objects.get_or_create(project=project)
    return space


# --- Lien public --------------------------------------------------------------


def enable_public_link(*, actor, project):
    space = _space_for_manager(actor, project)
    if not space.public_token:
        space.public_token = _generate_token(space.custom_slug)
    space.is_public = True
    space.save(update_fields=["public_token", "is_public", "updated_at"])
    return space


def rotate_public_link(*, actor, project):
    space = _space_for_manager(actor, project)
    space.public_token = _generate_token(space.custom_slug)
    space.is_public = True
    space.save(update_fields=["public_token", "is_public", "updated_at"])
    return space


def revoke_public_link(*, actor, project):
    space = _space_for_manager(actor, project)
    space.public_token = None
    space.is_public = False
    space.save(update_fields=["public_token", "is_public", "updated_at"])
    return space


_SLUG_RE = re.compile(r"^[a-z0-9-]{0,80}$")


def set_public_slug(*, actor, project, slug):
    """Change le segment lisible du lien public (session du 2026-09-23) —
    régénère `public_token` pour l'embarquer (même principe qu'une
    rotation : l'ancien lien cesse de fonctionner). Slug vide = retire le
    préfixe lisible, le lien redevient un token opaque pur."""
    space = _space_for_manager(actor, project)
    cleaned = slugify((slug or "").strip())[:80]
    if slug and not cleaned:
        raise DocsValidationError("Ce segment d'URL n'est pas utilisable, choisissez-en un autre.")
    space.custom_slug = cleaned
    update_fields = ["custom_slug", "updated_at"]
    if space.public_token:  # lien déjà actif : le régénérer avec le nouveau préfixe
        space.public_token = _generate_token(cleaned)
        update_fields.append("public_token")
    space.save(update_fields=update_fields)
    return space


def update_space_appearance(*, actor, project, accent_color=None, header_content=None, footer_content=None):
    """Personnalisation de la page publique (session du 2026-09-23) —
    couleur d'accent, en-tête, pied de page. Mise à jour partielle, comme
    `apps.accounts.services.update_planning_preferences` : chaîne vide
    valide (retire la personnalisation de ce champ), `None` = champ non
    fourni."""
    space = _space_for_manager(actor, project)
    update_fields = []
    if accent_color is not None:
        space.accent_color = accent_color
        update_fields.append("accent_color")
    if header_content is not None:
        space.header_content = header_content
        update_fields.append("header_content")
    if footer_content is not None:
        space.footer_content = footer_content
        update_fields.append("footer_content")
    if update_fields:
        space.save(update_fields=[*update_fields, "updated_at"])
    return space


# --- Pages -------------------------------------------------------------------


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
                raise DocsValidationError(
                    "Cette page a des sous-pages : elle ne peut pas devenir elle-même une sous-page."
                )
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


# --- Fiches (DocEntry) -----------------------------------------------------


def _get_entry(space, entry_id):
    try:
        return DocEntry.all_objects.get(space=space, id=entry_id)
    except DocEntry.DoesNotExist:
        raise DocsValidationError("Fiche introuvable.")


def create_entry(*, actor, project, kind, title, description="", source="manuelle",
                 source_task=None, source_incident=None, version=None):
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
        source=source, source_task=source_task, source_incident=source_incident, version=version,
        order=(max_order or 0) + 1,
    )


def update_entry(*, actor, project, entry_id, title=None, description=None, order=None, version=_UNSET):
    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    e = _get_entry(space, entry_id)
    if title is not None:
        if not title.strip():
            raise DocsValidationError("Le titre est obligatoire.")
        e.title = title.strip()[:200]
    if description is not None:
        e.description = description
    if version is not _UNSET:
        # `version=None` explicite = détache la fiche de toute version
        # (retour "sans version"), distinct de "champ non fourni".
        e.version = version
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
                blocks.append("\n".join(current))
                current = []
            continue
        if _BULLET_RE.match(line) and current:
            blocks.append("\n".join(current))
            current = []
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


_CONTRIBUTORS_TITLE = "Contributeurs au projet"
_ROLE_LABELS = {"chef_de_projet": "Chef de projet", "membre": "Membre", "lecteur": "Lecteur"}


def generate_contributors_entry(*, actor, project):
    """(Re)génère la fiche "Contributeurs au projet" (session du 2026-09-23)
    — une seule fiche par espace, `get_or_create` sur `(space, kind)`, son
    contenu est entièrement réécrit à chaque appel (liste des membres
    actifs, pas un ajout incrémental) : c'est un instantané, pas un journal.
    Contrairement aux autres fiches, jamais alimentée via la file "à
    documenter"."""
    from apps.projects.models import ProjectMembership

    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    memberships = (
        ProjectMembership.objects.filter(project=project).select_related("user").order_by("role", "user__first_name")
    )
    if not memberships:
        raise DocsValidationError("Ce projet n'a aucun membre actif à lister.")
    lines = []
    for role in ("chef_de_projet", "membre", "lecteur"):
        role_members = [m for m in memberships if m.role == role]
        if not role_members:
            continue
        lines.append(f"**{_ROLE_LABELS[role]}**")
        for m in role_members:
            name = f"{m.user.first_name} {m.user.last_name}".strip() or m.user.username
            lines.append(f"- {name}")
        lines.append("")
    description = "\n".join(lines).strip()

    entry, created = DocEntry.all_objects.get_or_create(
        space=space, kind="contributeurs",
        defaults={"title": _CONTRIBUTORS_TITLE, "description": description, "source": "manuelle"},
    )
    if not created:
        entry.description = description
        entry.save(update_fields=["description", "updated_at"])
    return entry


# --- File « À documenter » (PendingDocEntry) ------------------------------


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
        # Une tâche porte sa version ; un incident n'en a pas (pas de notion
        # de version sur ce modèle) — retenue automatiquement pour alimenter
        # le regroupement par version des fiches (session du 2026-09-23).
        version=pending.task.version if pending.task_id else None,
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


# --- Agrégat public (lecture seule, AllowAny) -----------------------------


def _public_pages(space):
    pages = list(DocPage.all_objects.filter(space=space, status="publie").order_by("order", "created_at"))
    ids = {p.id for p in pages}

    def node(pg):
        return {"id": str(pg.id), "title": pg.title, "slug": pg.slug, "content": pg.content,
                "children": [node(c) for c in pages if c.parent_id == pg.id]}

    return [node(p) for p in pages if p.parent_id is None or p.parent_id not in ids]


def _public_entries(space, kind):
    return [
        {
            "id": str(e.id),
            "title": e.title,
            "description": e.description,
            "created_at": e.created_at.isoformat(),
            "version_label": e.version.label if e.version_id else None,
        }
        for e in DocEntry.all_objects.filter(space=space, kind=kind, status="publie")
        .select_related("version")
        .order_by("order", "created_at")
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
        "contributors": _public_entries(space, "contributeurs"),
        # Personnalisation (session du 2026-09-23) — vide = habillage Awtodo
        # par défaut, voir `docs/charte-graphique.md`.
        "accent_color": space.accent_color,
        "header_content": space.header_content,
        "footer_content": space.footer_content,
    }


# --- Présentation (dicts sérialisés pour l'API authentifiée) --------------
# La logique de mise en forme vit ici, pas dans la vue (CLAUDE.md règle 1) :
# la vue se contente d'appeler le service et de renvoyer `Response(...)`.


def _page_dict(page, children=None):
    return {
        "id": str(page.id),
        "parent_id": str(page.parent_id) if page.parent_id else None,
        "title": page.title,
        "slug": page.slug,
        "content": page.content,
        "order": page.order,
        "status": page.status,
        "status_display": page.get_status_display(),
        "created_at": page.created_at.isoformat(),
        "updated_at": page.updated_at.isoformat(),
        "children": children or [],
    }


def _pages_tree(space):
    pages = list(
        DocPage.all_objects.filter(space=space).exclude(status="archive").order_by("order", "created_at")
    )
    by_parent = {}
    for page in pages:
        by_parent.setdefault(page.parent_id, []).append(page)

    def node(page):
        return _page_dict(page, [node(child) for child in by_parent.get(page.id, [])])

    return [node(page) for page in by_parent.get(None, [])]


def _entry_dict(entry):
    return {
        "id": str(entry.id),
        "kind": entry.kind,
        "title": entry.title,
        "description": entry.description,
        "order": entry.order,
        "source": entry.source,
        "source_task_id": str(entry.source_task_id) if entry.source_task_id else None,
        "source_incident_id": str(entry.source_incident_id) if entry.source_incident_id else None,
        "version_id": str(entry.version_id) if entry.version_id else None,
        "version_label": entry.version.label if entry.version_id else None,
        "status": entry.status,
        "status_display": entry.get_status_display(),
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


def _pending_dict(pending):
    src = pending.task or pending.incident
    return {
        "id": str(pending.id),
        "kind": pending.kind,
        "source_label": "Tâche" if pending.task_id else "Incident",
        "source_title": src.title if src else "",
        "created_at": pending.created_at.isoformat(),
    }


def _space_dict(space, request=None):
    public_url = None
    if space.is_public and space.public_token and request is not None:
        public_url = request.build_absolute_uri(f"/docs/{space.public_token}")
    return {
        "id": str(space.id),
        "is_public": space.is_public,
        "public_token": space.public_token,
        "public_url": public_url,
        "custom_slug": space.custom_slug,
        "accent_color": space.accent_color,
        "header_content": space.header_content,
        "footer_content": space.footer_content,
    }


def get_documentation_bundle(*, actor, project, request=None):
    space = get_or_create_space(actor=actor, project=project)
    entries = list(
        DocEntry.all_objects.filter(space=space)
        .exclude(status="archive")
        .select_related("version")
        .order_by("order", "created_at")
    )
    pendings = list(
        PendingDocEntry.objects.filter(space=space, status="en_attente").select_related("task", "incident")
    )
    return {
        "space": _space_dict(space, request),
        "pages": _pages_tree(space),
        "features": [_entry_dict(e) for e in entries if e.kind == "fonctionnalite"],
        "resolutions": [_entry_dict(e) for e in entries if e.kind == "resolution"],
        "contributors": [_entry_dict(e) for e in entries if e.kind == "contributeurs"],
        "pending_features": [_pending_dict(p) for p in pendings if p.kind == "fonctionnalite"],
        "pending_resolutions": [_pending_dict(p) for p in pendings if p.kind == "resolution"],
    }
