// Voir docs/modeles-et-api.md > "Filtre d'état généralisé" : la combobox
// "Afficher" est le même pattern partout où des statuts terminaux existent —
// une seule définition par entité ici, réutilisée par tous les écrans
// (Tâches, Kanban, Incidents, Projets).
export interface StatusFilterOption {
  value: string;
  label: string;
  defaultChecked: boolean;
}

export const TASK_STATUS_FILTER_OPTIONS: StatusFilterOption[] = [
  { value: "en_attente_validation", label: "En attente de validation", defaultChecked: true },
  { value: "disponible", label: "Disponible", defaultChecked: true },
  { value: "assignee", label: "Assignée", defaultChecked: true },
  { value: "en_cours", label: "En cours", defaultChecked: true },
  { value: "archivee", label: "Archivée", defaultChecked: false },
  { value: "rejetee", label: "Rejetée", defaultChecked: false },
];

export const INCIDENT_STATUS_FILTER_OPTIONS: StatusFilterOption[] = [
  { value: "signale", label: "Signalé", defaultChecked: true },
  { value: "en_cours", label: "En cours", defaultChecked: true },
  { value: "resolu", label: "Résolu", defaultChecked: true },
  { value: "archive", label: "Archivé", defaultChecked: false },
];

export const PROJECT_STATUS_FILTER_OPTIONS: StatusFilterOption[] = [
  { value: "actif", label: "Actif", defaultChecked: true },
  { value: "cloture", label: "Clôturé", defaultChecked: false },
];

export function defaultStatusSelection(options: StatusFilterOption[]): Set<string> {
  return new Set(options.filter((option) => option.defaultChecked).map((option) => option.value));
}
