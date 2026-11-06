import os
import re
import secrets

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.text import slugify

from apps.common.audit import record_event
from apps.projects.models import Project, SpecSection
from apps.projects.services import contributor_projects, is_project_manager, is_project_member

from .models import DocAttachment, DocEntry, DocPage, DocSpace, PendingDocEntry


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


_THEME_ZONES = ("background", "content", "sidebar", "tabs", "header", "footer")
# `<zone>` : couleur de fond, `<zone>_text` : couleur du texte (absente = calculée
# selon le fond pour rester lisible).
THEME_COLOR_ZONES = frozenset({*_THEME_ZONES, *(f"{zone}_text" for zone in _THEME_ZONES)})
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _ensure_hex_color(value):
    if not _HEX_COLOR_RE.match(value):
        raise DocsValidationError(f"Couleur invalide : « {value} » (format attendu : #RRGGBB).")


def update_space_appearance(
    *, actor, project, accent_color=None, header_content=None, footer_content=None,
    theme_colors=None, show_powered_by=None,
):
    """Personnalisation de la page publique (session du 2026-09-23, couleurs
    par zone et mention Awtodo le 2026-11-05) — mise à jour partielle, comme
    `apps.accounts.services.update_planning_preferences` : chaîne vide
    valide (retire la personnalisation de ce champ), `None` = champ non
    fourni. `theme_colors` se fusionne zone par zone. Ouvert aussi aux clés
    API de l'organisation : une automatisation modifie ainsi une page publique
    sans intervention humaine, d'où la trace dans l'historique du projet."""
    _require_automation_writer(actor, project)
    space = _automation_space(project)
    update_fields = []
    if accent_color is not None:
        if accent_color:
            _ensure_hex_color(accent_color)
        space.accent_color = accent_color
        update_fields.append("accent_color")
    if theme_colors is not None:
        merged = dict(space.theme_colors)
        for zone, color in theme_colors.items():
            if zone not in THEME_COLOR_ZONES:
                raise DocsValidationError(f"Zone de couleur inconnue : « {zone} ».")
            if color:
                _ensure_hex_color(color)
                merged[zone] = color
            else:
                merged.pop(zone, None)
        space.theme_colors = merged
        update_fields.append("theme_colors")
    if show_powered_by is not None:
        space.show_powered_by = show_powered_by
        update_fields.append("show_powered_by")
    if header_content is not None:
        space.header_content = header_content
        update_fields.append("header_content")
    if footer_content is not None:
        space.footer_content = footer_content
        update_fields.append("footer_content")
    if update_fields:
        space.save(update_fields=[*update_fields, "updated_at"])
        record_event(
            space, actor=actor, verb="appearance_updated", description="Personnalisation de la documentation modifiée",
            project=project, organisation=project.organisation,
        )
    return space


def get_space_for_appearance(*, actor, project):
    _require_automation_reader(actor, project)
    return _automation_space(project)


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
    except (DocPage.DoesNotExist, DjangoValidationError):
        raise DocsValidationError("Page introuvable.")


def create_page(*, actor, project, title, parent_id=None, content="", section="documentation"):
    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    if not title or not title.strip():
        raise DocsValidationError("Le titre est obligatoire.")
    if section not in dict(DocPage.SECTION_CHOICES):
        raise DocsValidationError("Section de documentation invalide.")
    parent = None
    if parent_id:
        parent = _get_page(space, parent_id)
        if parent.parent_id is not None:
            raise DocsValidationError("La documentation est limitée à 2 niveaux de pages.")
        if parent.section != section:
            raise DocsValidationError("Une page ne peut avoir un parent que dans la même section.")
    max_order = (
        DocPage.all_objects.filter(space=space, parent=parent)
        .order_by("-order").values_list("order", flat=True).first()
    )
    page = DocPage.objects.create(
        space=space, section=section, parent=parent, title=title.strip(),
        slug=_unique_slug(space, title), content=content or "", order=(max_order or 0) + 1,
    )
    record_event(
        page, actor=actor, verb="created", description=f"Page de documentation créée : « {page.title} »", project=project
    )
    return page


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
            if new_parent.section != page.section:
                raise DocsValidationError("Une page ne peut avoir un parent que dans la même section.")
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


# --- Pièces jointes du « Support d'utilisation » --------------------------
# Déposables par un chef de projet ou par une clé API de l'organisation du
# projet (session du 2026-11-05). La clé API n'a accès qu'à ces endpoints-là
# et à la personnalisation, pas au reste de la documentation.


MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024

_ZIP_SIGNATURES = (b"PK\x03\x04",)
_OLE_SIGNATURES = (bytes.fromhex("d0cf11e0a1b11ae1"),)
_OFFICE = "application/vnd.openxmlformats-officedocument"

# Extension -> (type renvoyé au téléchargement, signatures acceptées). Le type
# annoncé par le client n'est jamais repris. `None` : format texte sans
# signature. HTML et SVG exclus : ils peuvent embarquer du script.
_ATTACHMENT_FORMATS = {
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".png": ("image/png", (bytes.fromhex("89504e470d0a1a0a"),)),
    ".jpg": ("image/jpeg", (bytes.fromhex("ffd8ff"),)),
    ".jpeg": ("image/jpeg", (bytes.fromhex("ffd8ff"),)),
    ".gif": ("image/gif", (b"GIF87a", b"GIF89a")),
    ".webp": ("image/webp", (b"RIFF",)),
    ".docx": (f"{_OFFICE}.wordprocessingml.document", _ZIP_SIGNATURES),
    ".xlsx": (f"{_OFFICE}.spreadsheetml.sheet", _ZIP_SIGNATURES),
    ".pptx": (f"{_OFFICE}.presentationml.presentation", _ZIP_SIGNATURES),
    ".doc": ("application/msword", _OLE_SIGNATURES),
    ".xls": ("application/vnd.ms-excel", _OLE_SIGNATURES),
    ".ppt": ("application/vnd.ms-powerpoint", _OLE_SIGNATURES),
    ".zip": ("application/zip", _ZIP_SIGNATURES),
    ".txt": ("text/plain", None),
    ".csv": ("text/csv", None),
    ".md": ("text/markdown", None),
}


def _is_org_service_account(actor, project):
    return (
        getattr(actor, "is_service_account", False)
        and getattr(actor, "is_authenticated", False)
        and actor.organisation_id == project.organisation_id
    )


def automation_projects(actor):
    """Portée des endpoints ouverts aux automatisations (pièces jointes,
    personnalisation) : celle de la documentation pour une personne, les
    projets de son organisation pour une clé API."""
    if getattr(actor, "is_service_account", False) and getattr(actor, "is_authenticated", False):
        return Project.all_objects.filter(organisation_id=actor.organisation_id)
    return contributor_projects(actor)


def _require_automation_reader(actor, project):
    if not _is_org_service_account(actor, project):
        _require_member(actor, project)


def _require_automation_writer(actor, project):
    if not _is_org_service_account(actor, project):
        _require_manager(actor, project)


def _clean_filename(filename):
    base = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = "".join(char for char in base if char.isprintable()).strip()
    stem, extension = os.path.splitext(base)
    return f"{stem[:200]}{extension}"


def _detect_attachment_type(filename, data):
    extension = os.path.splitext(filename)[1].lower()
    known = _ATTACHMENT_FORMATS.get(extension)
    if known is None:
        raise DocsValidationError(
            "Format non accepté — PDF, image (PNG, JPEG, GIF, WebP), Word, Excel, PowerPoint, ZIP ou texte."
        )
    content_type, signatures = known
    matches = b"\0" not in data if signatures is None else data.startswith(signatures)
    if not matches:
        raise DocsValidationError("Le contenu de ce fichier ne correspond pas à son extension.")
    return content_type


def _automation_space(project):
    space, _ = DocSpace.objects.get_or_create(project=project)
    return space


def upload_attachment(*, actor, project, page_id, filename, data):
    _require_automation_writer(actor, project)
    page = _get_page(_automation_space(project), page_id)
    if page.section != "support" or page.status == "archive":
        raise DocsValidationError("Les pièces jointes ne concernent que les pages actives du support d'utilisation.")
    if not data:
        raise DocsValidationError("Aucun fichier reçu.")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise DocsValidationError(f"Fichier trop lourd — {MAX_ATTACHMENT_BYTES // (1024 * 1024)} Mo maximum.")
    cleaned = _clean_filename(filename)
    content_type = _detect_attachment_type(cleaned, data)
    attachment = DocAttachment.objects.create(
        page=page, filename=cleaned, content_type=content_type, size=len(data), data=data, uploaded_by=actor
    )
    record_event(
        attachment, actor=actor, verb="created", description=f"Pièce jointe ajoutée : « {cleaned} »",
        project=project, organisation=project.organisation,
    )
    return attachment


def _get_attachment(project, page_id, attachment_id):
    try:
        return DocAttachment.objects.get(id=attachment_id, page_id=page_id, page__space__project=project)
    except (DocAttachment.DoesNotExist, DjangoValidationError):
        raise DocsValidationError("Pièce jointe introuvable.")


def get_attachment(*, actor, project, page_id, attachment_id):
    _require_automation_reader(actor, project)
    return _get_attachment(project, page_id, attachment_id)


def archive_attachment(*, actor, project, page_id, attachment_id):
    _require_automation_writer(actor, project)
    attachment = _get_attachment(project, page_id, attachment_id)
    attachment.status = "archive"
    attachment.save(update_fields=["status", "updated_at"])
    record_event(
        attachment, actor=actor, verb="removed", description=f"Pièce jointe retirée : « {attachment.filename} »",
        project=project, organisation=project.organisation,
    )
    return attachment


def list_support_pages(*, actor, project):
    """Pages du support et leurs pièces jointes, sans le contenu Markdown —
    permet à un appelant API de retrouver l'id de la page visée."""
    _require_automation_reader(actor, project)
    space = _automation_space(project)
    attachments = _attachments_by_page(page__space=space)
    pages = DocPage.all_objects.filter(space=space, section="support").exclude(status="archive")
    return [
        {
            "id": str(page.id),
            "parent_id": str(page.parent_id) if page.parent_id else None,
            "title": page.title,
            "slug": page.slug,
            "status": page.status,
            "attachments": attachments.get(page.id, []),
        }
        for page in pages.order_by("order", "created_at")
    ]


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
    entry = DocEntry.objects.create(
        space=space, kind=kind, title=title.strip()[:200], description=description or "",
        source=source, source_task=source_task, source_incident=source_incident, version=version,
        order=(max_order or 0) + 1,
    )
    record_event(
        entry, actor=actor, verb="created", description=f"Fiche de documentation créée : « {entry.title} »", project=project
    )
    return entry


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
    documenter".

    Écrase aussi une éventuelle liste personnalisée (`contributor_rows`,
    session du 2026-10-06) — c'est le sens même du bouton "Régénérer" :
    revenir à l'instantané automatique. La confirmation avant perte de la
    personnalisation est de la responsabilité du frontend, pas de ce
    service."""
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
        entry.contributor_rows = None
        entry.save(update_fields=["description", "contributor_rows", "updated_at"])
    return entry


def update_contributors_entry(*, actor, project, rows):
    """Liste personnalisée de contributeurs (session du 2026-10-06, retour
    direct : "on doit pouvoir personnaliser qui on met et quel rôle on leur
    attribue") — `rows` : liste de `{"name": str, "role": str}`, un nom
    libre et un rôle en texte libre (pas forcément un rôle `ProjectMembership`
    réel, ni même quelqu'un ayant un compte Awtodo).

    Régénère aussi `description` en Markdown à partir de `rows` (même format
    que `generate_contributors_entry`, sans le regroupement par rôle réel) —
    garde le rendu cohérent pour tout consommateur qui n'afficherait que ce
    champ (ex. d'anciens exports), même si l'affichage courant (interne et
    public) lit `contributor_rows` en priorité quand il est renseigné."""
    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    if not isinstance(rows, list):
        raise DocsValidationError("Liste de contributeurs invalide.")
    cleaned = []
    for row in rows:
        if not isinstance(row, dict):
            raise DocsValidationError("Liste de contributeurs invalide.")
        name = str(row.get("name") or "").strip()[:200]
        role = str(row.get("role") or "").strip()[:100]
        if not name:
            raise DocsValidationError("Chaque contributeur doit avoir un nom.")
        cleaned.append({"name": name, "role": role})

    description = "\n".join(f"- **{row['name']}** — {row['role']}" if row["role"] else f"- {row['name']}" for row in cleaned)

    entry, _created = DocEntry.all_objects.get_or_create(
        space=space, kind="contributeurs",
        defaults={"title": _CONTRIBUTORS_TITLE, "source": "manuelle"},
    )
    entry.contributor_rows = cleaned
    entry.description = description
    entry.save(update_fields=["contributor_rows", "description", "updated_at"])
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


def create_resolution_entry_from_incident(*, incident):
    """Remontée automatique d'un incident résolu (session du 2026-10-06,
    retour direct : "les incidents résolus [doivent être] automatiquement
    remontés [...] mais avec une main sur l'affichage") — crée directement la
    fiche de résolution en **brouillon**, sans passer par la file "à
    documenter" (étape de conversion manuelle conservée, elle, pour les
    tâches terminées — portée volontairement limitée aux incidents).
    "Main sur l'affichage" = `publish_entry`/`unpublish_entry`, déjà en
    place sur n'importe quelle fiche.

    Appelée depuis le signal `incident_resolved` — pas d'`actor` (action
    système, pas de garde de permission), pas de création d'espace à la
    volée : si aucun `DocSpace` n'existe encore pour ce projet (personne n'a
    jamais ouvert l'onglet Documentation), on ne force rien, même
    comportement que l'ancien flux `PendingDocEntry`."""
    if not incident.project_id:
        return None
    space = DocSpace.objects.filter(project_id=incident.project_id).first()
    if space is None:
        return None
    if DocEntry.all_objects.filter(space=space, kind="resolution", source_incident=incident).exists():
        return None
    max_order = (
        DocEntry.all_objects.filter(space=space, kind="resolution")
        .order_by("-order").values_list("order", flat=True).first()
    )
    return DocEntry.objects.create(
        space=space, kind="resolution", title=incident.title[:200],
        description=getattr(incident, "resolution_comment", "") or incident.description or "",
        source="incident", source_incident=incident, status="brouillon",
        order=(max_order or 0) + 1,
    )


def ignore_pending(*, actor, project, pending_id):
    _require_manager(actor, project)
    space = get_or_create_space(actor=actor, project=project)
    pending = _get_pending(space, pending_id)
    pending.status = "ignoree"
    pending.save(update_fields=["status", "updated_at"])


# --- Agrégat public (lecture seule, AllowAny) -----------------------------


def _public_pages(space, section):
    pages = list(
        DocPage.all_objects.filter(space=space, section=section, status="publie").order_by("order", "created_at")
    )
    ids = {p.id for p in pages}
    attachments = _attachments_by_page(page__in=ids)

    def node(pg):
        return {"id": str(pg.id), "title": pg.title, "slug": pg.slug, "content": pg.content,
                "attachments": attachments.get(pg.id, []),
                "children": [node(c) for c in pages if c.parent_id == pg.id]}

    return [node(p) for p in pages if p.parent_id is None or p.parent_id not in ids]


def _public_entries(space, kind):
    return [
        {
            "id": str(e.id),
            "title": e.title,
            "description": e.description,
            "contributor_rows": e.contributor_rows,
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
        "pages": _public_pages(space, "documentation"),
        "support_pages": _public_pages(space, "support"),
        "features": _public_entries(space, "fonctionnalite"),
        "resolutions": _public_entries(space, "resolution"),
        "contributors": _public_entries(space, "contributeurs"),
        # Personnalisation (session du 2026-09-23) — vide = habillage Awtodo
        # par défaut, voir `docs/charte-graphique.md`.
        "accent_color": space.accent_color,
        "header_content": space.header_content,
        "footer_content": space.footer_content,
        "theme_colors": space.theme_colors,
        "show_powered_by": space.show_powered_by,
    }


def get_public_attachment(token, attachment_id):
    """Fichier d'une page publiée d'un espace public, `None` dans tous les
    autres cas (lien révoqué, brouillon, pièce retirée, autre projet)."""
    if not token:
        return None
    return DocAttachment.objects.filter(
        id=attachment_id,
        page__status="publie",
        page__section="support",
        page__space__public_token=token,
        page__space__is_public=True,
    ).first()


# --- Présentation (dicts sérialisés pour l'API authentifiée) --------------
# La logique de mise en forme vit ici, pas dans la vue (CLAUDE.md règle 1) :
# la vue se contente d'appeler le service et de renvoyer `Response(...)`.


def attachment_dict(attachment):
    return {
        "id": str(attachment.id),
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "size": attachment.size,
        "created_at": attachment.created_at.isoformat(),
    }


def _attachments_by_page(**filters):
    grouped = {}
    for attachment in DocAttachment.objects.filter(**filters).defer("data").order_by("created_at"):
        grouped.setdefault(attachment.page_id, []).append(attachment_dict(attachment))
    return grouped


def _page_dict(page, children=None, attachments=None):
    if attachments is None:
        attachments = _attachments_by_page(page=page).get(page.id, [])
    return {
        "id": str(page.id),
        "parent_id": str(page.parent_id) if page.parent_id else None,
        "section": page.section,
        "title": page.title,
        "slug": page.slug,
        "content": page.content,
        "order": page.order,
        "status": page.status,
        "status_display": page.get_status_display(),
        "created_at": page.created_at.isoformat(),
        "updated_at": page.updated_at.isoformat(),
        "attachments": attachments,
        "children": children or [],
    }


def _pages_tree(space, section):
    pages = list(
        DocPage.all_objects.filter(space=space, section=section)
        .exclude(status="archive").order_by("order", "created_at")
    )
    by_parent = {}
    for page in pages:
        by_parent.setdefault(page.parent_id, []).append(page)
    attachments = _attachments_by_page(page__space=space, page__section=section)

    def node(page):
        return _page_dict(page, [node(child) for child in by_parent.get(page.id, [])], attachments.get(page.id, []))

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
        "contributor_rows": entry.contributor_rows,
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
        "theme_colors": space.theme_colors,
        "show_powered_by": space.show_powered_by,
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
        "pages": _pages_tree(space, "documentation"),
        "support_pages": _pages_tree(space, "support"),
        "features": [_entry_dict(e) for e in entries if e.kind == "fonctionnalite"],
        "resolutions": [_entry_dict(e) for e in entries if e.kind == "resolution"],
        "contributors": [_entry_dict(e) for e in entries if e.kind == "contributeurs"],
        "pending_features": [_pending_dict(p) for p in pendings if p.kind == "fonctionnalite"],
        "pending_resolutions": [_pending_dict(p) for p in pendings if p.kind == "resolution"],
    }


def get_pending_doc_count(*, actor, project=None):
    """Dette documentaire — taille de la file "à documenter", widget par
    défaut du Dashboard (session du 2026-10-01, voir apps.dashboards.catalog).
    `project=None` = portée globale, scopée à `contributor_projects` comme les
    autres stats globales (un lecteur n'y entre pas)."""
    if project is not None:
        _require_member(actor, project)
        return PendingDocEntry.objects.filter(status="en_attente", space__project=project).count()

    if actor is None or not getattr(actor, "is_authenticated", False):
        raise DocsPermissionError("Utilisateur non identifié.")
    return PendingDocEntry.objects.filter(
        status="en_attente", space__project__in=contributor_projects(actor)
    ).count()
