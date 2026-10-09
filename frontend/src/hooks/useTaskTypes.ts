import { useEffect, useState } from "react";
import { getTaskTypes } from "../api/client";
import type { Task, TaskType } from "../types/watodo";

// Types actifs proposés pour un projet (ceux de son groupe, sinon les siens).
// Cache module par projet : une liste de tâches qui ouvre plusieurs
// accordéons du même projet ne refait pas la requête. Vidé par
// `invalidateTaskTypes` quand l'éditeur de types modifie une liste.
const cache = new Map<string, Promise<TaskType[]>>();
const listeners = new Set<() => void>();

export function invalidateTaskTypes() {
  cache.clear();
  listeners.forEach((listener) => listener());
}

function load(projectId: string): Promise<TaskType[]> {
  let pending = cache.get(projectId);
  if (!pending) {
    pending = getTaskTypes({ project: projectId }).then((list) => list.types);
    pending.catch(() => cache.delete(projectId));
    cache.set(projectId, pending);
  }
  return pending;
}

// Options de Combobox. Le type courant d'une tâche reste listé même s'il a été
// archivé depuis (sinon le sélecteur afficherait une valeur vide).
export function taskTypeOptions(types: TaskType[], current?: Pick<Task, "task_type" | "task_type_display">) {
  const options = types.map((t) => ({ value: t.key, label: t.label }));
  if (current && !options.some((o) => o.value === current.task_type)) {
    options.push({ value: current.task_type, label: current.task_type_display });
  }
  return options;
}

export function useTaskTypes(projectId: string | null | undefined): TaskType[] {
  const [types, setTypes] = useState<TaskType[]>([]);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const listener = () => setVersion((v) => v + 1);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  useEffect(() => {
    if (!projectId) {
      setTypes([]);
      return;
    }
    let cancelled = false;
    load(projectId)
      .then((loaded) => {
        if (!cancelled) setTypes(loaded);
      })
      .catch(() => {
        if (!cancelled) setTypes([]);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, version]);

  return types;
}
