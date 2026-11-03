import { useEffect, useState } from "react";
import { useCurrentUser } from "../context/CurrentUserContext";

function storageKey(userId: string | undefined): string {
  return `awtodo:project-favorites:${userId ?? "anon"}`;
}

/**
 * Projets épinglés en favoris, par utilisateur, mémorisés en cache local
 * (même choix que `useColumnPreferences` : préférence d'affichage par
 * appareil, pas une donnée métier partagée — voir docs/charte-graphique.md >
 * "Écran Projets — répertoire").
 */
export function useProjectFavorites(): [Set<string>, (projectId: string) => void] {
  const { currentUser } = useCurrentUser();
  const [favorites, setFavorites] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    let next = new Set<string>();
    try {
      const raw = window.localStorage.getItem(storageKey(currentUser?.id));
      if (raw) next = new Set(JSON.parse(raw) as string[]);
    } catch {
      // localStorage indisponible — aucun favori, sans bloquer l'affichage.
    }
    setFavorites(next);
  }, [currentUser?.id]);

  function toggle(projectId: string) {
    setFavorites((current) => {
      const next = new Set(current);
      if (next.has(projectId)) next.delete(projectId);
      else next.add(projectId);
      try {
        window.localStorage.setItem(storageKey(currentUser?.id), JSON.stringify(Array.from(next)));
      } catch {
        // ignore — le favori ne persistera pas au rechargement.
      }
      return next;
    });
  }

  return [favorites, toggle];
}
