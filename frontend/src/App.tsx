import { useEffect, useState } from "react";
import { AppShell } from "./layout/AppShell";
import type { BreadcrumbItem } from "./layout/Breadcrumb";
import { CommandPalette } from "./components/CommandPalette";
import { AdministrationPage } from "./features/administration/AdministrationPage";
import { LoginPage } from "./features/auth/LoginPage";
import { HomePage } from "./features/home/HomePage";
import { PublicDocsPage } from "./features/docs/PublicDocsPage";
import { InvitationAcceptPage } from "./features/invitations/InvitationAcceptPage";
import { ProjectDetailView } from "./features/projects/ProjectDetailView";
import { ProjectsGrid } from "./features/projects/ProjectsGrid";
import { GlobalStatsPage } from "./features/stats/GlobalStatsPage";
import { PlanningPage } from "./features/planning/PlanningPage";
import { TasksListPage } from "./features/tasks/TasksListPage";
import { IncidentsPage } from "./features/incidents/IncidentsPage";
import { useCurrentUser } from "./context/CurrentUserContext";
import { useTheme } from "./theme/useTheme";
import type { ViewName } from "./types/navigation";
import type { Project } from "./types/watodo";

// Pas de librairie de routing dans ce projet (navigation interne 100% en
// state React, voir `Route` ci-dessous) — la page d'acceptation d'invitation
// est la seule vue qui doit être accessible par une vraie URL (l'invité n'a
// pas de compte utilisable pour naviguer dans l'app). Contournement minimal :
// un match d'URL au chargement, en dehors de l'état de navigation habituel,
// plutôt qu'ajouter une dépendance de routing pour une seule page publique.
const INVITATION_PATH_PATTERN = /^\/invitations\/([^/]+)\/?$/;
// Documentation publique d'un projet — voir CLAUDE.md > Stack technique >
// Auth : seule exception à « la connexion est la porte d'entrée obligatoire ».
// Le match est fait AVANT toute garde d'authentification (le lecteur n'a pas
// forcément de compte).
const PUBLIC_DOCS_PATH_PATTERN = /^\/docs\/([^/]+)\/?$/;

type Route =
  | { name: "home" }
  | { name: "projects" }
  | { name: "project"; project: Project }
  | { name: "tasks"; focusTaskId?: string }
  | { name: "incidents"; focusIncidentId?: string }
  | { name: "planning" }
  | { name: "stats" }
  | { name: "administration" }
  | { name: "login" };

function activeViewFor(route: Route): ViewName | null {
  if (route.name === "home" || route.name === "login") return null;
  return route.name === "project" ? "projects" : route.name;
}

// Remplace l'ancien titre de page unique du Topbar (voir Topbar.tsx > logo
// Awtodo fixe) — même rôle de "où suis-je", porté maintenant par le fil
// d'Ariane sous la barre. Vide sur l'accueil/connexion : rien à situer.
function breadcrumbItemsFor(
  route: Route,
  handlers: { toHome: () => void; toProjects: () => void },
): BreadcrumbItem[] {
  switch (route.name) {
    case "home":
    case "login":
      return [];
    case "projects":
      return [{ label: "Accueil", onClick: handlers.toHome }, { label: "Projets" }];
    case "project":
      return [
        { label: "Accueil", onClick: handlers.toHome },
        { label: "Projets", onClick: handlers.toProjects },
        { label: route.project.name },
      ];
    case "tasks":
      return [{ label: "Accueil", onClick: handlers.toHome }, { label: "Tâches" }];
    case "incidents":
      return [{ label: "Accueil", onClick: handlers.toHome }, { label: "Incidents" }];
    case "planning":
      return [{ label: "Accueil", onClick: handlers.toHome }, { label: "Planning" }];
    case "stats":
      return [{ label: "Accueil", onClick: handlers.toHome }, { label: "Statistiques" }];
    case "administration":
      return [{ label: "Accueil", onClick: handlers.toHome }, { label: "Administration" }];
  }
}

function App() {
  const { currentUser, isRestoring } = useCurrentUser();
  const [route, setRoute] = useState<Route>({ name: "home" });
  const [theme, toggleTheme] = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [createProjectTrigger, setCreateProjectTrigger] = useState(0);
  const [createIncidentTrigger, setCreateIncidentTrigger] = useState(0);

  function handleNavigate(view: ViewName, options?: { taskId?: string; incidentId?: string }) {
    if (view === "tasks" && options?.taskId) {
      setRoute({ name: "tasks", focusTaskId: options.taskId });
      return;
    }
    if (view === "incidents" && options?.incidentId) {
      setRoute({ name: "incidents", focusIncidentId: options.incidentId });
      return;
    }
    setRoute({ name: view } as Route);
  }

  function handleNavigateHome() {
    setRoute({ name: "home" });
  }

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const isShortcut = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k";
      if (isShortcut) {
        event.preventDefault();
        setPaletteOpen((current) => !current);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  const showAdministration = Boolean(
    currentUser &&
      (currentUser.organisation_role === "admin" ||
        currentUser.organisation_role === "chef_de_projet" ||
        currentUser.is_platform_admin),
  );

  const publicDocsToken = window.location.pathname.match(PUBLIC_DOCS_PATH_PATTERN)?.[1];
  if (publicDocsToken) {
    return <PublicDocsPage token={publicDocsToken} />;
  }

  const invitationToken = window.location.pathname.match(INVITATION_PATH_PATTERN)?.[1];
  if (invitationToken) {
    return <InvitationAcceptPage token={invitationToken} />;
  }

  // Restauration initiale (liste des utilisateurs + reprise d'un token
  // stocké, voir CurrentUserContext) : écran neutre le temps que ça
  // résolve, pour ne pas flasher la page de connexion à chaque rechargement
  // d'un utilisateur pourtant déjà identifié (démo ou connexion réelle).
  if (isRestoring) {
    return <div className="app-loading" />;
  }

  // La connexion est la porte d'entrée du site : tant qu'aucune identité
  // n'est établie (connexion réelle ou sélection du mode démo), rien
  // d'autre ne s'affiche — pas de bouton "Annuler" ici, il n'y a nulle part
  // où revenir. Une fois `currentUser` non nul (login() ou
  // setCurrentUserId() dans LoginPage), ce garde-fou ne se déclenche plus et
  // l'app normale s'affiche.
  if (!currentUser) {
    return <LoginPage onSuccess={() => setRoute({ name: "home" })} />;
  }

  // Page pleine (pas de sidebar/topbar), même traitement que
  // InvitationAcceptPage ci-dessus — un écran de connexion n'a pas vocation
  // à s'afficher dans le chrome habituel de l'app. Atteinte volontairement
  // depuis UserMenu ("Se connecter") en étant déjà identifié — distinct du
  // garde-fou ci-dessus, qui ne propose pas d'annuler.
  if (route.name === "login") {
    return (
      <LoginPage onSuccess={() => setRoute({ name: "home" })} onCancel={() => setRoute({ name: "home" })} />
    );
  }

  const commandPalette = (
    <CommandPalette
      open={paletteOpen}
      onClose={() => setPaletteOpen(false)}
      onNavigate={handleNavigate}
      onNavigateHome={handleNavigateHome}
      onCreateProject={() => {
        setRoute({ name: "projects" });
        setCreateProjectTrigger((current) => current + 1);
      }}
      onCreateIncident={() => {
        setRoute({ name: "incidents" });
        setCreateIncidentTrigger((current) => current + 1);
      }}
      theme={theme}
      onToggleTheme={toggleTheme}
    />
  );

  // Écran d'accueil v3 (session du 10/08/2026, panneau oblique) : plein
  // viewport, sans chrome d'app (Topbar/BinderTabs/Breadcrumb) — même
  // traitement que LoginPage ci-dessus, plutôt qu'un simple `hideNav` sur
  // AppShell comme avant cette passe (l'écran a désormais son propre bouton
  // de déconnexion, sa propre navigation en "onglets diagonaux"). La palette
  // de commandes (Ctrl/Cmd+K) reste disponible, son état vit dans ce
  // composant, pas dans AppShell.
  if (route.name === "home") {
    return (
      <>
        <HomePage onNavigate={handleNavigate} />
        {commandPalette}
      </>
    );
  }

  return (
    <AppShell
      activeView={activeViewFor(route)}
      onNavigate={handleNavigate}
      onNavigateHome={handleNavigateHome}
      breadcrumbItems={breadcrumbItemsFor(route, {
        toHome: handleNavigateHome,
        toProjects: () => setRoute({ name: "projects" }),
      })}
      theme={theme}
      onToggleTheme={toggleTheme}
      onOpenCommandPalette={() => setPaletteOpen(true)}
      onLoginClick={() => setRoute({ name: "login" })}
      showAdministration={showAdministration}
    >
      <div key={route.name === "project" ? `project-${route.project.id}` : route.name} className="view-transition">
        {route.name === "projects" && (
          <ProjectsGrid
            onSelectProject={(project) => setRoute({ name: "project", project })}
            createTrigger={createProjectTrigger}
          />
        )}
        {route.name === "project" && (
          <ProjectDetailView project={route.project} onBack={() => setRoute({ name: "projects" })} />
        )}
        {route.name === "tasks" && <TasksListPage focusTaskId={route.focusTaskId} />}
        {route.name === "planning" && <PlanningPage />}
        {route.name === "incidents" && (
          <IncidentsPage createTrigger={createIncidentTrigger} focusIncidentId={route.focusIncidentId} />
        )}
        {route.name === "stats" && <GlobalStatsPage />}
        {route.name === "administration" && <AdministrationPage />}
      </div>

      {commandPalette}
    </AppShell>
  );
}

export default App;
