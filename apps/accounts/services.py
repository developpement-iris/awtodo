import re

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.html import escape

from .models import PASSWORD_RESET_TOKEN_LIFETIME, Invitation, Organisation, PasswordResetRequest, Team, TeamMembership, User


class AccountPermissionError(Exception):
    """L'acteur n'a pas le droit d'effectuer cette action."""


class AccountValidationError(Exception):
    """Les données fournies ne permettent pas d'effectuer cette action."""


def _require_actor(actor):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise AccountPermissionError("Utilisateur non identifié.")


def authenticate_user(*, username, password):
    """Connexion par mot de passe (voir CLAUDE.md > "Stack technique" > Auth —
    en attendant le SSO Microsoft, une authentification directe reste
    nécessaire pour activer/utiliser un compte). `django.contrib.auth.authenticate`
    fonctionne nativement avec `User(AbstractUser)`, aucune logique de hachage
    à écrire. `AccountValidationError` (pas `AccountPermissionError`) : c'est
    une saisie utilisateur incorrecte, pas un problème de droits — cohérent
    avec le découpage 400/403 déjà en place ailleurs dans ce fichier."""
    user = authenticate(username=username, password=password)
    if user is None:
        raise AccountValidationError("Identifiants invalides.")
    if user.account_status != "active":
        raise AccountValidationError("Ce compte n'est pas encore activé.")
    return user


def set_organisation_role(*, actor, target_user, role):
    """Portée organisation (User.organisation_role) — à ne pas confondre avec
    User.is_platform_admin (portée plateforme) ni ProjectMembership.role
    (portée projet), voir CLAUDE.md > "Organisation"."""
    _require_actor(actor)
    if actor.organisation_role != "admin":
        raise AccountPermissionError("Seul un administrateur de l'organisation peut changer ce rôle.")
    if target_user.organisation_id != actor.organisation_id:
        raise AccountPermissionError("Cet utilisateur n'appartient pas à votre organisation.")
    valid_roles = {choice for choice, _ in User._meta.get_field("organisation_role").choices}
    if role not in valid_roles:
        raise AccountValidationError("Rôle d'organisation invalide.")

    target_user.organisation_role = role
    target_user.save(update_fields=["organisation_role"])
    return target_user


def _derive_username(email):
    base = re.sub(r"[^a-z0-9._-]", "", email.split("@")[0].lower()) or "utilisateur"
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        counter += 1
        username = f"{base}{counter}"
    return username


def create_organisation(*, actor, organisation_name, admin_name, admin_email):
    """Réservé à is_platform_admin (portée plateforme). Crée l'organisation
    ET son premier admin dans la même transaction — le flux d'invitation
    classique (voir "Comptes et invitations") suppose un admin déjà existant
    dans l'organisation cible, impossible ici puisque l'organisation vient
    de naître. Pas de username dans le formulaire (nom + email seulement,
    comme spécifié) — dérivé de l'email, désambiguïsé si déjà pris."""
    _require_actor(actor)
    if not actor.is_platform_admin:
        raise AccountPermissionError("Seul un administrateur de la plateforme peut créer une organisation.")
    if not organisation_name or not organisation_name.strip():
        raise AccountValidationError("Le nom de l'organisation est obligatoire.")
    if not admin_name or not admin_name.strip():
        raise AccountValidationError("Le nom du premier administrateur est obligatoire.")
    if not admin_email or not admin_email.strip():
        raise AccountValidationError("L'email du premier administrateur est obligatoire.")

    name_parts = admin_name.strip().split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    with transaction.atomic():
        organisation = Organisation.objects.create(name=organisation_name.strip())
        admin_user = User.objects.create_user(
            username=_derive_username(admin_email),
            email=admin_email.strip(),
            first_name=first_name,
            last_name=last_name,
            organisation=organisation,
            organisation_role="admin",
        )
    return organisation, admin_user


def create_team(*, actor, name, description=""):
    """Portée organisation : admin/chef_de_projet uniquement (voir CLAUDE.md
    > "Écran Administration (organisation)" > "Groupes"). Le créateur devient
    automatiquement membre de son propre groupe — sinon un chef de projet ne
    pourrait pas y rattacher de projet collaboratif juste après (contrainte
    "le créateur doit être membre du groupe", voir apps.projects.services)."""
    _require_actor(actor)
    if actor.organisation_role not in {"admin", "chef_de_projet"}:
        raise AccountPermissionError("Seul un administrateur ou chef de projet d'organisation peut créer un groupe.")
    if not name or not name.strip():
        raise AccountValidationError("Le nom du groupe est obligatoire.")

    with transaction.atomic():
        team = Team.objects.create(
            name=name.strip(), description=description, organisation=actor.organisation, created_by=actor
        )
        TeamMembership.objects.create(team=team, user=actor)
    return team


def _is_team_manager(actor, team):
    """"Administrateur du groupe" (session du 2026-08-07) : le créateur du
    groupe (portée groupe, comme avant), **ou** un administrateur de
    l'organisation/de la plateforme (portée large, cohérente avec les autres
    overrides déjà en place ailleurs — `accessible_projects`,
    `organisation_role=admin` sur les invitations...). Élargit volontairement
    la règle précédente ("réservé au créateur du groupe") : un admin
    d'organisation ou de plateforme doit pouvoir gérer n'importe quel groupe,
    pas seulement ceux qu'il a lui-même créés."""
    return team.created_by_id == actor.id or actor.is_platform_admin or actor.organisation_role == "admin"


def _ensure_can_manage_team(actor, team):
    _require_actor(actor)
    if not _is_team_manager(actor, team):
        raise AccountPermissionError(
            "Seul le créateur du groupe ou un administrateur peut gérer ce groupe."
        )


def can_manage_team(user, team):
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return _is_team_manager(user, team)


def add_team_member(*, actor, team, user):
    """Réactive implicitement une adhésion retirée : `TeamMembership.objects`
    (manager actif) ne verra jamais la ligne `removed`, donc `get_or_create`
    en crée naturellement une nouvelle plutôt que de raviver l'ancienne —
    cohérent avec "aucune suppression physique" (l'ancienne ligne retirée
    reste telle quelle, en historique)."""
    _ensure_can_manage_team(actor, team)
    if user.organisation_id != team.organisation_id:
        raise AccountValidationError("Cet utilisateur n'appartient pas à la même organisation que le groupe.")

    membership, _ = TeamMembership.objects.get_or_create(team=team, user=user)
    return membership


def remove_team_member(*, actor, team, user):
    _ensure_can_manage_team(actor, team)

    membership = TeamMembership.objects.filter(team=team, user=user).first()
    if membership is None:
        raise AccountValidationError("Cet utilisateur n'est pas membre actif de ce groupe.")

    membership.status = "removed"
    membership.save(update_fields=["status"])
    return membership


def rename_team(*, actor, team, name):
    _ensure_can_manage_team(actor, team)
    if not name or not name.strip():
        raise AccountValidationError("Le nom du groupe est obligatoire.")
    name = name.strip()

    if Team.objects.exclude(pk=team.pk).filter(name=name).exists():
        raise AccountValidationError("Un groupe porte déjà ce nom.")

    team.name = name
    team.save(update_fields=["name"])
    return team


def _send_invitation_email(invitation):
    # Backend console par défaut en dev (voir config/settings/dev.py) — un
    # vrai SMTP (sandbox type Mailtrap, ou un relais réel) reste opt-in via
    # `.env` (voir `.env.example`), rien ne change ici selon le backend
    # utilisé. Email HTML + texte brut (session du 2026-08-06, soir) : un
    # vrai bouton cliquable, pas juste un chemin relatif imprimé en texte —
    # `/invitations/{token}/` seul n'était pas un lien valide dans un client
    # mail réel, `FRONTEND_BASE_URL` (config/settings/dev.py) le rend absolu.
    # Appel synchrone assumé pour l'instant, backend console OU sandbox de
    # test dev uniquement : le premier n'effectue aucune I/O réseau réelle
    # (juste un print), le second est un aller-retour SMTP local ponctuel
    # pour tester le flux, pas un volume de production. La règle "aucun
    # appel synchrone vers un système externe" (CLAUDE.md, règle
    # d'architecture n°2) reste vraie pour la cible finale : quand un vrai
    # ESP transactionnel sera branché en prod, cet appel devra passer par un
    # signal Django → tâche Celery async (Celery n'est pour l'instant qu'une
    # dépendance déclarée, pas encore câblé dans ce projet).
    activation_url = f"{settings.FRONTEND_BASE_URL}/invitations/{invitation.token}/"
    organisation_name = escape(invitation.organisation.name)

    text_body = (
        f"Vous avez été invité·e à rejoindre {invitation.organisation.name} sur Awtodo.\n"
        f"Activez votre compte : {activation_url}"
    )
    html_body = (
        '<div style="font-family: sans-serif; color: #191033; max-width: 480px;">'
        '<h1 style="font-size: 18px; margin: 0 0 16px;">Awtodo</h1>'
        f"<p>Vous avez été invité·e à rejoindre <strong>{organisation_name}</strong> sur Awtodo.</p>"
        f'<p><a href="{activation_url}" style="display: inline-block; background: #2C1B63; '
        'color: #EDEBF7; text-decoration: none; padding: 12px 24px; border-radius: 6px; '
        'font-weight: 600;">Activer mon compte</a></p>'
        '<p style="font-size: 12px; color: #4B4270;">'
        f"Si le bouton ne fonctionne pas, copiez ce lien dans votre navigateur : {activation_url}</p>"
        "</div>"
    )

    send_mail(
        subject="Invitation à rejoindre Awtodo",
        message=text_body,
        from_email=None,
        recipient_list=[invitation.email],
        fail_silently=True,
        html_message=html_body,
    )


def create_invitation(*, actor, email, first_name="", last_name="", team=None, project=None):
    """Deux flux distincts selon `team`/`project` (voir CLAUDE.md > "Comptes
    et invitations") :
    - `project` fourni : compte externe scopé à ce projet — réservé à un chef
      de projet de CE projet précis (`ProjectMembership.role`, pas
      `organisation_role`). Import local de `apps.projects.models` : voir la
      note sur `Invitation.project` dans models.py, même justification.
    - `project` absent : compte interne — réservé à `organisation_role=admin`
      (n'importe quel groupe) ou `chef_de_projet` (uniquement vers un groupe
      dont il est `created_by`)."""
    _require_actor(actor)

    if project is not None:
        from apps.projects.models import ProjectMembership

        if not ProjectMembership.objects.filter(project=project, user=actor, role="chef_de_projet").exists():
            raise AccountPermissionError("Seul un chef de projet de ce projet peut inviter un compte externe.")
        account_type = "externe"
        organisation = project.organisation
    else:
        if actor.organisation_role == "admin":
            pass
        elif actor.organisation_role == "chef_de_projet":
            if team is None or team.created_by_id != actor.id:
                raise AccountPermissionError("Un chef de projet ne peut inviter que vers un groupe qu'il a créé.")
        else:
            raise AccountPermissionError("Vous n'avez pas le droit d'inviter de nouveaux comptes.")
        account_type = "interne"
        organisation = actor.organisation

    if not email or not email.strip():
        raise AccountValidationError("L'email est obligatoire.")

    with transaction.atomic():
        user = User.objects.filter(email__iexact=email.strip()).first()
        if user is None:
            user = User.objects.create_user(
                username=_derive_username(email),
                email=email.strip(),
                first_name=first_name,
                last_name=last_name,
                organisation=organisation,
                account_type=account_type,
                account_status="pending",
            )

        invitation = Invitation.objects.create(
            email=email.strip(),
            user=user,
            organisation=organisation,
            team=team,
            project=project,
            invited_by=actor,
        )

    _send_invitation_email(invitation)
    return invitation


def accept_invitation(*, token, password=None):
    """Public (pas d'acteur à authentifier — l'invité n'a par définition pas
    encore de compte utilisable). Idempotence volontairement stricte : une
    invitation déjà `accepted`/`revoked`/`expired` ne peut plus être acceptée
    à nouveau.

    `password` : choisi par l'invité pour activer un vrai moyen de connexion
    (session du 2026-08-06 — voir CLAUDE.md > "Stack technique" > Auth).
    Avant cette passe, l'invité n'avait ensuite aucune façon de "devenir
    lui-même" hors du sélecteur de test `X-Debug-User-Id` ; `set_password`
    donne au compte, créé sans mot de passe utilisable par `create_invitation`
    (`User.objects.create_user(...)` sans `password`), un vrai moyen de
    connexion (`authenticate_user`). `password=None` par défaut (pas un
    paramètre positionnel obligatoire) pour ne pas changer l'ordre des
    vérifications existantes : token introuvable/invitation invalide restent
    détectés avant la validation du mot de passe."""
    try:
        invitation = Invitation.objects.get(token=token)
    except Invitation.DoesNotExist:
        raise AccountValidationError("Invitation introuvable.")
    if invitation.status != "pending":
        raise AccountValidationError("Cette invitation n'est plus valide.")

    if not password:
        raise AccountValidationError("Un mot de passe est requis pour activer le compte.")
    try:
        validate_password(password, user=invitation.user)
    except DjangoValidationError as exc:
        raise AccountValidationError(" ".join(exc.messages))

    with transaction.atomic():
        user = invitation.user
        user.set_password(password)
        user.account_status = "active"
        user.save(update_fields=["password", "account_status"])

        if invitation.team_id:
            TeamMembership.objects.get_or_create(team=invitation.team, user=user)
        if invitation.project_id:
            from apps.projects.models import ProjectMembership

            ProjectMembership.objects.get_or_create(project=invitation.project, user=user, role="membre")

        invitation.status = "accepted"
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["status", "accepted_at"])
    return invitation


def resend_invitation(*, actor, invitation):
    """Un admin peut renvoyer une invitation (voir CLAUDE.md > "Comptes et
    invitations" > "Création de compte interne") : l'ancienne est marquée
    `expired` (jamais supprimée), une nouvelle est créée avec un nouveau
    token. Réservé à celui qui a émis l'invitation ou à un admin
    d'organisation — cohérent avec les droits d'invitation eux-mêmes."""
    _require_actor(actor)
    if invitation.status != "pending":
        raise AccountValidationError("Seule une invitation en attente peut être renvoyée.")
    if actor.id != invitation.invited_by_id and actor.organisation_role != "admin":
        raise AccountPermissionError("Vous ne pouvez pas renvoyer cette invitation.")

    with transaction.atomic():
        invitation.status = "expired"
        invitation.save(update_fields=["status"])

        new_invitation = Invitation.objects.create(
            email=invitation.email,
            user=invitation.user,
            organisation=invitation.organisation,
            team=invitation.team,
            project=invitation.project,
            invited_by=actor,
        )

    _send_invitation_email(new_invitation)
    return new_invitation


def _send_password_reset_email(reset):
    # Même raisonnement que `_send_invitation_email` (email synchrone, backend
    # console/sandbox uniquement pour l'instant — voir sa docstring pour le
    # détail complet, non répété ici). Couleurs `#191033`/`#2C1B63`/`#EDEBF7`
    # reprises telles quelles de `_send_invitation_email` — reste de l'ancienne
    # palette cyan/violet-galaxie (v3), jamais mise à jour vers la palette
    # brique/brun actuelle même dans l'email d'invitation. Pas corrigé ici non
    # plus : cohérence entre les deux emails transactionnels priorisée sur la
    # correction d'un détail de marque hors du périmètre de cette passe.
    reset_url = f"{settings.FRONTEND_BASE_URL}/reset-password/{reset.token}/"
    hours = int(PASSWORD_RESET_TOKEN_LIFETIME.total_seconds() // 3600)

    text_body = (
        "Vous avez demandé la réinitialisation de votre mot de passe Awtodo.\n"
        f"Choisissez un nouveau mot de passe : {reset_url}\n"
        f"Ce lien expire dans {hours} heure(s). Si vous n'êtes pas à l'origine de cette demande, ignorez cet email."
    )
    html_body = (
        '<div style="font-family: sans-serif; color: #191033; max-width: 480px;">'
        '<h1 style="font-size: 18px; margin: 0 0 16px;">Awtodo</h1>'
        "<p>Vous avez demandé la réinitialisation de votre mot de passe.</p>"
        f'<p><a href="{reset_url}" style="display: inline-block; background: #2C1B63; '
        'color: #EDEBF7; text-decoration: none; padding: 12px 24px; border-radius: 6px; '
        'font-weight: 600;">Choisir un nouveau mot de passe</a></p>'
        '<p style="font-size: 12px; color: #4B4270;">'
        f"Si le bouton ne fonctionne pas, copiez ce lien dans votre navigateur : {reset_url}<br>"
        f"Ce lien expire dans {hours} heure(s). Si vous n'êtes pas à l'origine de cette demande, ignorez cet email."
        "</p>"
        "</div>"
    )

    send_mail(
        subject="Réinitialisation de votre mot de passe Awtodo",
        message=text_body,
        from_email=None,
        recipient_list=[reset.user.email],
        fail_silently=True,
        html_message=html_body,
    )


def request_password_reset(*, identifier):
    """Public par nature (voir `authenticate_user`/`accept_invitation` pour le
    même raisonnement) — la personne a justement perdu l'accès à son compte,
    il n'y a pas d'acteur à authentifier.

    `identifier` : identifiant OU email, comme le login (voir
    `LoginPage.tsx`) — recherché sur les deux champs plutôt que de forcer
    l'utilisateur à se souvenir lequel il utilise d'habitude.

    **Pas d'énumération de comptes** : retourne toujours `None` silencieusement
    si aucun compte actif ne correspond (pas d'`AccountValidationError` sur ce
    cas précis) — la vue appelante renvoie le même message générique dans les
    deux cas, seul le fait qu'un email parte réellement varie. Un compte
    `pending` n'est délibérément pas concerné : il n'a pas encore de mot de
    passe à réinitialiser, c'est le flux d'invitation (`accept_invitation`)
    qui s'applique.

    Toute demande de reset encore `pending` pour cet utilisateur est marquée
    `expired` avant d'en créer une nouvelle (même pattern que
    `resend_invitation`) — un seul lien valide à la fois, les anciens emails
    reçus ne fonctionnent plus une fois une nouvelle demande faite."""
    if not identifier or not identifier.strip():
        raise AccountValidationError("Identifiant ou email requis.")
    identifier = identifier.strip()

    user = User.objects.filter(
        Q(username__iexact=identifier) | Q(email__iexact=identifier), account_status="active"
    ).first()
    if user is None:
        return None

    with transaction.atomic():
        PasswordResetRequest.objects.filter(user=user, status="pending").update(status="expired")
        reset = PasswordResetRequest.objects.create(user=user)

    # Mode "lien direct" (phase de test, pas d'ESP branché — voir
    # `PASSWORD_RESET_DIRECT_LINK` dans les settings) : on n'envoie pas
    # d'email, la vue renvoie le chemin de réinitialisation et le frontend y
    # redirige. Le jeton est quand même créé/tourné comme d'habitude.
    if not getattr(settings, "PASSWORD_RESET_DIRECT_LINK", False):
        _send_password_reset_email(reset)
    return reset


def confirm_password_reset(*, token, password=None):
    """Public, même raisonnement que `accept_invitation` (aucune session
    utilisable à ce stade). Idempotence stricte comme les invitations : une
    demande déjà `used`/`expired` ne peut pas resservir, et `is_expired`
    (calculé sur `created_at`, voir models.py) est revérifié ici même si le
    `status` stocké est encore `pending` — c'est la vérification qui fait foi,
    pas un balayage périodique qui mettrait `status` à jour tout seul."""
    try:
        reset = PasswordResetRequest.objects.select_related("user").get(token=token)
    except PasswordResetRequest.DoesNotExist:
        raise AccountValidationError("Lien de réinitialisation introuvable.")
    if reset.status != "pending":
        raise AccountValidationError("Ce lien de réinitialisation n'est plus valide.")
    if reset.is_expired:
        raise AccountValidationError("Ce lien de réinitialisation a expiré.")

    if not password:
        raise AccountValidationError("Un mot de passe est requis.")
    try:
        validate_password(password, user=reset.user)
    except DjangoValidationError as exc:
        raise AccountValidationError(" ".join(exc.messages))

    with transaction.atomic():
        user = reset.user
        user.set_password(password)
        user.save(update_fields=["password"])

        reset.status = "used"
        reset.used_at = timezone.now()
        reset.save(update_fields=["status", "used_at"])
    return reset
