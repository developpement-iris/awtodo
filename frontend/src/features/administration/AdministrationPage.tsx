import { useState } from "react";
import { SectionSidebar } from "../../components/SectionSidebar";
import { useCurrentUser } from "../../context/CurrentUserContext";
import type { PermissionCapabilityKey } from "../../types/watodo";
import { BrandingSection } from "./BrandingSection";
import { GroupsSection } from "./GroupsSection";
import { IntegrationsSection } from "./IntegrationsSection";
import { InvitationsSection } from "./InvitationsSection";
import { MembersSection } from "./MembersSection";
import { OrganisationsSection } from "./OrganisationsSection";
import { ProfilesSection } from "./ProfilesSection";
import "./AdministrationPage.css";

type Tab = "members" | "groups" | "invitations" | "integrations" | "branding" | "profiles" | "organisations";

export function AdministrationPage() {
  const { currentUser } = useCurrentUser();

  // Même droit que le backend (`is_organisation_admin`) : admin d'organisation
  // OU admin de plateforme, indépendamment de l'organisation_role personnel
  // de ce dernier — voir le bug corrigé le 2026-09-21 sur set_organisation_role.
  const isOrgAdmin = Boolean(currentUser?.is_platform_admin || currentUser?.organisation_role === "admin");
  // Profils de droits personnalisés (session du 2026-09-28) — capacités
  // *additives* à ces rôles fixes, jamais un remplacement : chaque écran
  // reste visible soit par rôle historique, soit par capacité accordée.
  const hasCapability = (key: PermissionCapabilityKey) => currentUser?.capabilities.includes(key) ?? false;

  const canSeeMembers = isOrgAdmin || hasCapability("manage_members");
  const canSeeGroups =
    currentUser?.organisation_role === "admin" ||
    currentUser?.organisation_role === "chef_de_projet" ||
    hasCapability("manage_groups");
  const canSeeInvitations = canSeeGroups || hasCapability("manage_invitations");
  const canSeeIntegrations = isOrgAdmin || hasCapability("manage_integrations");
  const canSeeBranding = isOrgAdmin || hasCapability("manage_branding");
  // La création/gestion des profils eux-mêmes reste réservée à un vrai admin
  // d'organisation — une capacité ne peut jamais s'accorder elle-même
  // (demande explicite : "le premier [profil] serait attribué à
  // l'administrateur de l'organisation seulement").
  const canSeeProfiles = isOrgAdmin;
  const canSeeOrganisations = currentUser?.is_platform_admin ?? false;

  const tabs: { id: Tab; label: string }[] = [
    ...(canSeeMembers ? [{ id: "members" as Tab, label: "Membres" }] : []),
    ...(canSeeGroups ? [{ id: "groups" as Tab, label: "Groupes" }] : []),
    ...(canSeeInvitations ? [{ id: "invitations" as Tab, label: "Invitations" }] : []),
    ...(canSeeIntegrations ? [{ id: "integrations" as Tab, label: "Intégrations" }] : []),
    ...(canSeeBranding ? [{ id: "branding" as Tab, label: "Marque" }] : []),
    ...(canSeeProfiles ? [{ id: "profiles" as Tab, label: "Profils" }] : []),
    ...(canSeeOrganisations ? [{ id: "organisations" as Tab, label: "Organisations" }] : []),
  ];

  const [tab, setTab] = useState<Tab | null>(tabs[0]?.id ?? null);
  const activeTab = tab && tabs.some((item) => item.id === tab) ? tab : tabs[0]?.id ?? null;

  if (!currentUser) {
    return (
      <p className="administration-page__message">
        Choisissez un utilisateur (menu en haut à droite) pour accéder à l'administration.
      </p>
    );
  }

  if (tabs.length === 0) {
    return (
      <p className="administration-page__message">
        Vous n'avez aucun droit d'administration sur cette organisation.
      </p>
    );
  }

  return (
    <div className="administration-page">
      <div className="administration-page__body">
        <SectionSidebar
          items={tabs}
          activeId={activeTab ?? tabs[0].id}
          onSelect={setTab}
          ariaLabel="Sections de l'administration"
        />

        <div className="administration-page__panel">
          {activeTab === "members" && <MembersSection currentUser={currentUser} />}
          {activeTab === "groups" && <GroupsSection currentUser={currentUser} />}
          {activeTab === "invitations" && <InvitationsSection currentUser={currentUser} />}
          {activeTab === "integrations" && <IntegrationsSection />}
          {activeTab === "branding" && <BrandingSection />}
          {activeTab === "profiles" && <ProfilesSection />}
          {activeTab === "organisations" && <OrganisationsSection />}
        </div>
      </div>
    </div>
  );
}
