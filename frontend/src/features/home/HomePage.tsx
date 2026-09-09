import { AlertTriangle, BarChart3, CalendarDays, FolderKanban, ListChecks, LogOut, ShieldCheck, type LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { getIncidents, getProjects, getTasks } from "../../api/client";
import awtodoLogo from "../../assets/awtodo-logo.png";
import { Skeleton } from "../../components/Skeleton";
import { StatusBadge } from "../../components/StatusBadge";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { incidentStatusIcon, incidentStatusTone, priorityTone } from "../../lib/badges";
import type { ViewName } from "../../types/navigation";
import type { Incident, Project, Task } from "../../types/watodo";
import "./HomePage.css";

interface HomePageProps {
  onNavigate: (view: ViewName, options?: { incidentId?: string }) => void;
}

const URGENT_PRIORITIES = new Set(["haute", "critique"]);

// Salutation dactylo (voir docs/charte-graphique.md > "Écran d'accueil —
// panneau oblique") : tape, marque un temps plein, s'efface, marque un temps
// vide, retape — en boucle continue (retour direct, remplace le
// comportement "une seule fois au montage" de `typeOnce()` dans
// `maquette-accueil-v3-oblique.html`, jugé trop statique). `currentUser` est
// garanti non-null ici (App.tsx bloque tout accès aux routes internes tant
// qu'aucune identité n'est établie), mais on reste défensif comme le reste
// de cet écran.
const GREETING_TYPE_SPEED = 70;
const GREETING_ERASE_SPEED = 40;
const GREETING_HOLD_FULL = 1800;
const GREETING_HOLD_EMPTY = 500;

function TypewriterGreeting({ name }: { name: string }) {
  const text = name ? `Bonjour, ${name} !` : "Bonjour !";
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setCount(text.length);
      return;
    }

    let cancelled = false;
    let timer = 0;

    function typeForward(i: number) {
      if (cancelled) return;
      setCount(i);
      if (i < text.length) {
        timer = window.setTimeout(() => typeForward(i + 1), GREETING_TYPE_SPEED);
      } else {
        timer = window.setTimeout(() => eraseBackward(i), GREETING_HOLD_FULL);
      }
    }

    function eraseBackward(i: number) {
      if (cancelled) return;
      setCount(i);
      if (i > 0) {
        timer = window.setTimeout(() => eraseBackward(i - 1), GREETING_ERASE_SPEED);
      } else {
        timer = window.setTimeout(() => typeForward(0), GREETING_HOLD_EMPTY);
      }
    }

    typeForward(0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [text]);

  return (
    <span className="home-page__greeting">
      {text.slice(0, count)}
      <span className="home-page__greeting-cursor" aria-hidden="true" />
    </span>
  );
}

// Onglets "accès rapide" positionnés le long de la diagonale — la formule
// garde chaque onglet aligné sur cette pente, quel que soit le nombre
// d'onglets réellement affichés (Administration est conditionnel),
// contrairement à la maquette de référence qui codait 5 positions en dur.
//
// `OBLIQUE_OUTER_TOP`/`OBLIQUE_SLOPE` doivent rester synchronisés avec le
// bord extérieur de `.home-page__bg-seam` dans HomePage.css (valeur au
// sommet de l'écran / pente sur toute la hauteur) — pas de valeur dupliquée
// en dur ici, sinon les onglets se décalent de la diagonale au moindre
// changement de largeur du panneau gauche (voir passe du 11/08/2026).
//
// `TAB_OVERLAP_PX` : le chevauchement doit rester positif sur TOUTE la
// hauteur de chaque carte, pas seulement à son bord supérieur (point de
// référence de ce calcul) — la diagonale recule d'environ 15 à 19px sur la
// hauteur d'une carte (~100px) aux ratios d'écran habituels, et le survol
// (voir `.home-page__tab:hover` translateX) en retranche 14 de plus. 48px de
// marge au repos couvre les deux avec une marge de sécurité confortable —
// c'est un compromis pragmatique (le calque oblique est une ligne droite à
// pente fixe, un vrai alignement au pixel près demanderait un clip-path par
// carte dépendant du ratio d'écran, hors de proportion pour cet habillage).
const TAB_TOP_MIN = 16;
const TAB_TOP_MAX = 80;
const OBLIQUE_OUTER_TOP = 53.6;
const OBLIQUE_SLOPE = 8;
const TAB_OVERLAP_PX = 48;

function tabPosition(index: number, total: number) {
  const top = total > 1 ? TAB_TOP_MIN + ((TAB_TOP_MAX - TAB_TOP_MIN) * index) / (total - 1) : (TAB_TOP_MIN + TAB_TOP_MAX) / 2;
  const outerEdge = OBLIQUE_OUTER_TOP - OBLIQUE_SLOPE * (top / 100);
  return { top: `${top}%`, left: `calc(${outerEdge}% - ${TAB_OVERLAP_PX}px)` };
}

interface QuickAccessTab {
  key: string;
  icon: LucideIcon;
  name: string;
  /** Info dynamique courte (compteur…) — absente pour les menus qui n'en ont
   * pas (Tâches/Statistiques/Administration). */
  meta?: React.ReactNode;
  /** Descriptif fixe de l'utilité du menu — toujours présent. */
  description: string;
  incident?: boolean;
  onClick: () => void;
}

export function HomePage({ onNavigate }: HomePageProps) {
  const { currentUser, isAuthenticated, logout, clearCurrentUser } = useCurrentUser();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [myTasks, setMyTasks] = useState<Task[] | null>(null);
  const [totalTaskCount, setTotalTaskCount] = useState<number | null>(null);
  const [activeIncidents, setActiveIncidents] = useState<Incident[] | null>(null);

  useEffect(() => {
    getProjects()
      .then(setProjects)
      .catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    getIncidents()
      .then((data) =>
        setActiveIncidents(
          data.filter((incident) => incident.status !== "resolu" && URGENT_PRIORITIES.has(incident.priority)),
        ),
      )
      .catch(() => setActiveIncidents([]));
  }, []);

  useEffect(() => {
    if (!currentUser) {
      setMyTasks([]);
      setTotalTaskCount(0);
      return;
    }
    getTasks({ assignee: currentUser.id })
      .then((data) => {
        setTotalTaskCount(data.length);
        setMyTasks(data.filter((task) => URGENT_PRIORITIES.has(task.priority)));
      })
      .catch(() => {
        setMyTasks([]);
        setTotalTaskCount(0);
      });
  }, [currentUser]);

  const hasUrgentItems = (myTasks?.length ?? 0) > 0 || (activeIncidents?.length ?? 0) > 0;
  const backlogCount = (myTasks?.length ?? 0) + (activeIncidents?.length ?? 0);

  // Pas d'onglets classeur (BinderTabs) sur l'accueil — cet écran n'a plus du
  // tout le chrome d'app (voir App.tsx, rendu hors AppShell comme LoginPage)
  // depuis cette passe. Les onglets ci-dessous sont donc le seul accès à la
  // navigation, ils doivent reprendre TOUS les menus, y compris
  // Statistiques/Administration. Même condition que `showAdministration`
  // dans App.tsx.
  const showAdministration = Boolean(
    currentUser &&
      (currentUser.organisation_role === "admin" ||
        currentUser.organisation_role === "chef_de_projet" ||
        currentUser.is_platform_admin),
  );

  function handleLogout() {
    if (isAuthenticated) {
      logout();
    } else {
      clearCurrentUser();
    }
  }

  const tabs: QuickAccessTab[] = [
    {
      key: "projects",
      icon: FolderKanban,
      name: "Projets",
      meta: projects === null ? <Skeleton width="30px" height="11px" /> : `${projects.length} au total`,
      description: "Vue d'ensemble et suivi de vos projets",
      onClick: () => onNavigate("projects"),
    },
    {
      key: "tasks",
      icon: ListChecks,
      name: "Tâches",
      description: "Vos tâches, filtrées et priorisées",
      onClick: () => onNavigate("tasks"),
    },
    {
      key: "incidents",
      icon: AlertTriangle,
      name: "Incidents",
      meta: activeIncidents === null ? <Skeleton width="30px" height="11px" /> : `${activeIncidents.length} actifs`,
      description: "Signalement et suivi des incidents en cours",
      incident: true,
      onClick: () => onNavigate("incidents"),
    },
    {
      key: "planning",
      icon: CalendarDays,
      name: "Planning",
      description: "Votre calendrier et le planning des projets",
      onClick: () => onNavigate("planning"),
    },
    {
      key: "stats",
      icon: BarChart3,
      name: "Statistiques",
      description: "Indicateurs d'activité et budgets",
      onClick: () => onNavigate("stats"),
    },
    ...(showAdministration
      ? [
          {
            key: "administration",
            icon: ShieldCheck,
            name: "Administration",
            description: "Comptes, groupes et invitations",
            onClick: () => onNavigate("administration"),
          } satisfies QuickAccessTab,
        ]
      : []),
  ];

  return (
    <div className="home-page">
      <div className="home-page__bg-left" />
      <div className="home-page__bg-seam" />
      <div className="home-page__bg-right" />

      <button type="button" className="home-page__logout" onClick={handleLogout} aria-label="Se déconnecter">
        <LogOut size={16} strokeWidth={1.75} aria-hidden="true" />
      </button>

      <div className="home-page__greeting-wrap">
        <TypewriterGreeting name={currentUser?.first_name || currentUser?.username || ""} />
      </div>

      <div className="home-page__content-left">
        {/* Logo posé directement sur le dégradé de marque (pas de chip fixe
            nécessaire ici, contrairement au Topbar sur fond thémé) — seule
            mention de la marque sur cet écran. */}
        <img src={awtodoLogo} alt="Awtodo" className="home-page__brand-logo" />

        <p className="home-page__lead">Ce que je peux faire maintenant…</p>

        {/* Carte "post-it" incorporée au panneau oblique (fond translucide
            teinté crème, pas un aplat neutre posé par-dessus) — voir
            docs/charte-graphique.md. */}
        <section className="home-page__postit">
          <h2 className="home-page__postit-title">Backlog</h2>

          {!currentUser && (
            <p className="home-page__postit-note">
              Choisissez un utilisateur (menu en haut à droite) pour voir vos tâches prioritaires.
            </p>
          )}

          {(myTasks === null || activeIncidents === null) && (
            <div className="home-page__postit-skeleton">
              <Skeleton height="40px" />
              <Skeleton height="40px" />
            </div>
          )}

          {myTasks !== null && activeIncidents !== null && !hasUrgentItems && currentUser && (
            <p className="home-page__postit-note">Rien d'urgent pour l'instant.</p>
          )}

          {hasUrgentItems && (
            <ul className="home-page__postit-list">
              {myTasks?.map((task) => (
                <li key={task.id}>
                  <button type="button" className="home-page__postit-item" onClick={() => onNavigate("tasks")}>
                    <span className="home-page__postit-item-title">{task.title}</span>
                    <StatusBadge label={task.priority_display} tone={priorityTone(task.priority)} />
                  </button>
                </li>
              ))}
              {activeIncidents?.map((incident) => (
                <li key={incident.id}>
                  <button
                    type="button"
                    className="home-page__postit-item"
                    onClick={() => onNavigate("incidents", { incidentId: incident.id })}
                  >
                    <span className="home-page__postit-item-title">{incident.title}</span>
                    <StatusBadge
                      label={incident.status_display}
                      tone={incidentStatusTone(incident.status)}
                      icon={incidentStatusIcon(incident.status)}
                    />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="home-page__stats-row">
          <div className="home-page__stat">
            <span className="home-page__stat-value">
              {totalTaskCount === null ? <Skeleton width="26px" height="24px" /> : totalTaskCount}
            </span>
            <span className="home-page__stat-label">Tâches</span>
          </div>
          <div className="home-page__stat">
            <span className="home-page__stat-value">
              {projects === null ? <Skeleton width="26px" height="24px" /> : projects.length}
            </span>
            <span className="home-page__stat-label">Projets</span>
          </div>
          <div className="home-page__stat">
            <span className="home-page__stat-value">
              {myTasks === null || activeIncidents === null ? <Skeleton width="26px" height="24px" /> : backlogCount}
            </span>
            <span className="home-page__stat-label">Backlog</span>
          </div>
        </div>
      </div>

      <div className="home-page__content-right">
        {tabs.map((tab, index) => {
          const pos = tabPosition(index, tabs.length);
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              type="button"
              className={`home-page__tab${tab.incident ? " home-page__tab--incident" : ""}`}
              style={{ top: pos.top, left: pos.left }}
              onClick={tab.onClick}
            >
              <span className="home-page__tab-row">
                <Icon size={19} strokeWidth={1.8} aria-hidden="true" />
                <span className="home-page__tab-name">{tab.name}</span>
              </span>
              {tab.meta && <span className="home-page__tab-meta">{tab.meta}</span>}
              <span className="home-page__tab-desc">{tab.description}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
