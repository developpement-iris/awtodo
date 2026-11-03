import {
  Archive,
  type LucideIcon,
  AlertTriangle,
  Ban,
  CheckCircle2,
  CircleDot,
  Clock,
  Code2,
  PenLine,
  RefreshCw,
  Rocket,
  Search,
  User,
  XCircle,
} from "lucide-react";
import type { ProjectPhase } from "../types/watodo";

/*
 * Une couleur = un seul axe de sens (règle CLAUDE.md). Chaque axe a sa
 * propre famille de tones, jamais partagée avec un autre axe — à l'exception
 * de "neutral" et "positive" dont la signification ("rien à signaler" /
 * "sain") reste identique partout où ils apparaissent.
 *
 * Les statuts "neutres" (en_attente_validation / archivée / rejetée)
 * partagent la même teinte : c'est l'icône, pas la couleur, qui les
 * distingue.
 */
export type Tone =
  | "neutral"
  | "positive"
  | "priorityBasse"
  | "priorityMoyenne"
  | "priorityHaute"
  | "priorityCritique"
  | "taskAvailable"
  | "taskAssigned"
  | "taskInProgress"
  | "incidentReported"
  | "incidentInProgress";

const PRIORITY_TONES: Record<string, Tone> = {
  basse: "priorityBasse",
  moyenne: "priorityMoyenne",
  haute: "priorityHaute",
  critique: "priorityCritique",
};

const TASK_STATUS_TONES: Record<string, Tone> = {
  en_attente_validation: "neutral",
  disponible: "taskAvailable",
  assignee: "taskAssigned",
  en_cours: "taskInProgress",
  archivee: "neutral",
  rejetee: "neutral",
  annulee: "neutral",
};

const INCIDENT_STATUS_TONES: Record<string, Tone> = {
  signale: "incidentReported",
  en_cours: "incidentInProgress",
  resolu: "positive",
  archive: "neutral",
  annule: "neutral",
};

const PROJECT_STATUS_TONES: Record<string, Tone> = {
  actif: "positive",
  cloture: "neutral",
};

export function priorityTone(priority: string | null): Tone {
  if (!priority) return "neutral";
  return PRIORITY_TONES[priority] ?? "neutral";
}

/** basse → critique, pour les tris et la Roadmap (longueur/position indépendantes de cet ordre). */
export const PRIORITY_ORDER = ["basse", "moyenne", "haute", "critique"];

export function priorityRank(priority: string | null): number {
  if (!priority) return -1;
  const index = PRIORITY_ORDER.indexOf(priority);
  return index === -1 ? -1 : index;
}

export function statusTone(status: string): Tone {
  return TASK_STATUS_TONES[status] ?? "neutral";
}

export function incidentStatusTone(status: string): Tone {
  return INCIDENT_STATUS_TONES[status] ?? "neutral";
}

export function projectStatusTone(status: string): Tone {
  return PROJECT_STATUS_TONES[status] ?? "neutral";
}

const TASK_STATUS_ICONS: Record<string, LucideIcon> = {
  en_attente_validation: Clock,
  disponible: CircleDot,
  assignee: User,
  en_cours: RefreshCw,
  archivee: Archive,
  rejetee: XCircle,
  annulee: Ban,
};

const INCIDENT_STATUS_ICONS: Record<string, LucideIcon> = {
  signale: AlertTriangle,
  en_cours: RefreshCw,
  resolu: CheckCircle2,
  archive: Archive,
  annule: Ban,
};

const PROJECT_STATUS_ICONS: Record<string, LucideIcon> = {
  actif: CircleDot,
  cloture: Archive,
};

export function taskStatusIcon(status: string): LucideIcon | undefined {
  return TASK_STATUS_ICONS[status];
}

export function incidentStatusIcon(status: string): LucideIcon | undefined {
  return INCIDENT_STATUS_ICONS[status];
}

export function projectStatusIcon(status: string): LucideIcon | undefined {
  return PROJECT_STATUS_ICONS[status];
}

// Phase d'avancement d'un projet (session du 2026-11-03) — badge neutre +
// icône : aucun tone dédié, pour ne pas ouvrir un nouvel axe de couleur qui
// entrerait en collision avec statut/priorité sur la même carte.
export const PROJECT_PHASE_OPTIONS: { value: ProjectPhase; label: string }[] = [
  { value: "a_l_etude", label: "À l'étude" },
  { value: "en_ecriture", label: "En écriture" },
  { value: "developpement", label: "Développement" },
  { value: "livraison", label: "Livraison" },
];

const PROJECT_PHASE_ICONS: Record<string, LucideIcon> = {
  a_l_etude: Search,
  en_ecriture: PenLine,
  developpement: Code2,
  livraison: Rocket,
};

export function projectPhaseIcon(phase: string): LucideIcon | undefined {
  return PROJECT_PHASE_ICONS[phase];
}
