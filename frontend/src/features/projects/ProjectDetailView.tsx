import { ArrowLeft, Check, Copy, Lock, Unlock } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { closeProject, reopenProject } from "../../api/client";
import { SectionSidebar } from "../../components/SectionSidebar";
import { StatusBadge } from "../../components/StatusBadge";
import { useToast } from "../../context/ToastContext";
import { projectStatusIcon, projectStatusTone } from "../../lib/badges";
import { IncidentsPage } from "../incidents/IncidentsPage";
import { TasksTab } from "../tasks/TasksTab";
import type { Project } from "../../types/watodo";
import { BudgetingTab } from "./BudgetingTab";
import { DocumentationTab } from "./DocumentationTab";
import { NotesTab } from "./NotesTab";
import { ProjectPlanningTab } from "../planning/ProjectPlanningTab";
import { ProjectAdminTab } from "./ProjectAdminTab";
import { SpecTab } from "./SpecTab";
import { StatsTab } from "./StatsTab";
import "./ProjectDetailView.css";

type Tab =
  | "tasks"
  | "spec"
  | "notepad"
  | "maintenance"
  | "planning"
  | "documentation"
  | "stats"
  | "budgeting"
  | "administration";

const TABS: { id: Tab; label: string }[] = [
  { id: "tasks", label: "Tâches" },
  { id: "spec", label: "Cahier des charges" },
  { id: "notepad", label: "Bloc-notes" },
  { id: "maintenance", label: "Incidents" },
  { id: "planning", label: "Planning" },
  { id: "documentation", label: "Documentation" },
  { id: "stats", label: "Statistiques" },
  { id: "budgeting", label: "Budgétisation" },
  { id: "administration", label: "Administration" },
];

interface ProjectDetailViewProps {
  project: Project;
  onBack: () => void;
}

export function ProjectDetailView({ project: initialProject, onBack }: ProjectDetailViewProps) {
  const { showToast } = useToast();
  const [project, setProject] = useState(initialProject);
  const [tab, setTab] = useState<Tab>("tasks");
  // Un membre `lecteur` (voir docs/organisation-et-comptes.md > "Rôle
  // Lecteur") ne voit que Tâches / Cahier des charges / Bloc-notes, tout en
  // lecture seule. `can_contribute` (faux pour un lecteur) masque le reste.
  const contributorOnlyTabs: Tab[] = [
    "maintenance",
    "planning",
    "documentation",
    "stats",
    "budgeting",
    "administration",
  ];
  const visibleTabs = TABS.filter((item) => {
    // L'onglet Documentation est en plus réservé au chef de projet (rédaction
    // + gestion du lien public) — voir CLAUDE.md > Roadmap (session 2026-09-03).
    if (item.id === "documentation" && !project.permissions.can_edit_documentation) return false;
    if (!project.permissions.can_contribute && contributorOnlyTabs.includes(item.id)) return false;
    return true;
  });
  const [lifecycleSubmitting, setLifecycleSubmitting] = useState(false);
  const [lifecycleError, setLifecycleError] = useState<string | null>(null);
  const [idCopied, setIdCopied] = useState(false);

  async function handleCopyId() {
    try {
      await navigator.clipboard.writeText(project.id);
      setIdCopied(true);
      showToast("Identifiant du projet copié.");
      setTimeout(() => setIdCopied(false), 1500);
    } catch {
      showToast("Impossible de copier l'identifiant.");
    }
  }

  async function handleClose() {
    setLifecycleSubmitting(true);
    setLifecycleError(null);
    try {
      setProject(await closeProject(project.id));
      showToast("Projet clôturé.");
    } catch (err) {
      setLifecycleError(err instanceof Error ? err.message : "La clôture a échoué.");
    } finally {
      setLifecycleSubmitting(false);
    }
  }

  async function handleReopen() {
    setLifecycleSubmitting(true);
    setLifecycleError(null);
    try {
      setProject(await reopenProject(project.id));
      showToast("Projet réouvert.");
    } catch (err) {
      setLifecycleError(err instanceof Error ? err.message : "La réouverture a échoué.");
    } finally {
      setLifecycleSubmitting(false);
    }
  }

  return (
    <div className="project-detail">
      <button className="project-detail__back" onClick={onBack}>
        <ArrowLeft size={15} strokeWidth={1.75} aria-hidden="true" />
        Retour aux projets
      </button>

      <div className="project-detail__header">
        <h1 className="project-detail__title">{project.name}</h1>
        <div className="project-detail__header-actions">
          <StatusBadge
            label={project.status_display}
            tone={projectStatusTone(project.status)}
            icon={projectStatusIcon(project.status)}
          />
          {project.permissions.can_close && (
            <motion.button
              type="button"
              className="project-detail__lifecycle"
              onClick={handleClose}
              disabled={lifecycleSubmitting}
              whileTap={{ scale: 0.96 }}
            >
              <Lock size={14} strokeWidth={1.75} aria-hidden="true" />
              Clôturer
            </motion.button>
          )}
          {project.permissions.can_reopen && (
            <motion.button
              type="button"
              className="project-detail__lifecycle"
              onClick={handleReopen}
              disabled={lifecycleSubmitting}
              whileTap={{ scale: 0.96 }}
            >
              <Unlock size={14} strokeWidth={1.75} aria-hidden="true" />
              Réouvrir
            </motion.button>
          )}
        </div>
      </div>
      {lifecycleError && <p className="project-detail__lifecycle-error">{lifecycleError}</p>}
      {project.description && <p className="project-detail__description">{project.description}</p>}
      {project.team_name && <p className="project-detail__team">Groupe : {project.team_name}</p>}
      <p className="project-detail__id">
        ID projet : <code>{project.id}</code>
        <button
          type="button"
          className="project-detail__id-copy"
          onClick={handleCopyId}
          aria-label="Copier l'identifiant du projet"
        >
          {idCopied ? (
            <Check size={13} strokeWidth={1.75} aria-hidden="true" />
          ) : (
            <Copy size={13} strokeWidth={1.75} aria-hidden="true" />
          )}
        </button>
      </p>

      <div className="project-detail__body">
        <SectionSidebar items={visibleTabs} activeId={tab} onSelect={setTab} ariaLabel="Sections du projet" />

        <div className="project-detail__panel">
          {tab === "tasks" && <TasksTab project={project} />}
          {tab === "spec" && <SpecTab project={project} />}
          {tab === "notepad" && <NotesTab project={project} onSaved={setProject} />}
          {tab === "maintenance" && <IncidentsPage scopedProject={project} />}
          {tab === "planning" && <ProjectPlanningTab project={project} />}
          {tab === "documentation" && <DocumentationTab project={project} />}
          {tab === "stats" && <StatsTab project={project} />}
          {tab === "budgeting" && <BudgetingTab project={project} />}
          {tab === "administration" && <ProjectAdminTab project={project} onUpdated={setProject} />}
        </div>
      </div>
    </div>
  );
}
