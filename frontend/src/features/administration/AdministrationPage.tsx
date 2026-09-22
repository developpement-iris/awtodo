import { useState } from "react";
import { SectionSidebar } from "../../components/SectionSidebar";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { GroupsSection } from "./GroupsSection";
import { IntegrationsSection } from "./IntegrationsSection";
import { InvitationsSection } from "./InvitationsSection";
import { MembersSection } from "./MembersSection";
import { OrganisationsSection } from "./OrganisationsSection";
import "./AdministrationPage.css";

type Tab = "members" | "groups" | "invitations" | "integrations" | "organisations";

export function AdministrationPage() {
  const { currentUser } = useCurrentUser();

  const canSeeMembers = currentUser?.organisation_role === "admin";
  const canSeeGroups = currentUser?.organisation_role === "admin" || currentUser?.organisation_role === "chef_de_projet";
  const canSeeInvitations = canSeeGroups;
  // Même droit que le backend (`is_organisation_admin`) : admin d'organisation
  // OU admin de plateforme, indépendamment de l'organisation_role personnel
  // de ce dernier — voir le bug corrigé le 2026-09-21 sur set_organisation_role.
  const canSeeIntegrations = Boolean(currentUser?.is_platform_admin || currentUser?.organisation_role === "admin");
  const canSeeOrganisations = currentUser?.is_platform_admin ?? false;

  const tabs: { id: Tab; label: string }[] = [
    ...(canSeeMembers ? [{ id: "members" as Tab, label: "Membres" }] : []),
    ...(canSeeGroups ? [{ id: "groups" as Tab, label: "Groupes" }] : []),
    ...(canSeeInvitations ? [{ id: "invitations" as Tab, label: "Invitations" }] : []),
    ...(canSeeIntegrations ? [{ id: "integrations" as Tab, label: "Intégrations" }] : []),
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
          {activeTab === "organisations" && <OrganisationsSection />}
        </div>
      </div>
    </div>
  );
}
