import {
  Archive,
  type LucideIcon,
  AlertTriangle,
  CheckCircle2,
  CircleDot,
  Clock,
  RefreshCw,
  User,
  XCircle,
} from "lucide-react";

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
};

const INCIDENT_STATUS_TONES: Record<string, Tone> = {
  signale: "incidentReported",
  en_cours: "incidentInProgress",
  resolu: "positive",
  archive: "neutral",
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
};

const INCIDENT_STATUS_ICONS: Record<string, LucideIcon> = {
  signale: AlertTriangle,
  en_cours: RefreshCw,
  resolu: CheckCircle2,
  archive: Archive,
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
