import { useState } from "react";

export type SortDirection = "asc" | "desc";

/**
 * Tri par colonne d'une liste (Tâches/Incidents…) — retour direct : cliquer
 * un en-tête trie par cette colonne, recliquer inverse le sens. Ne stocke
 * que la clé + le sens, chaque écran fournit son propre comparateur (la
 * signification de "trier par X" diffère trop d'une colonne à l'autre —
 * priorité par rang, dates par ordre chronologique, texte par ordre
 * alphabétique — pour une abstraction commune au-delà de ce petit état).
 */
export function useSort<K extends string>(defaultKey: K | null = null) {
  const [sortKey, setSortKey] = useState<K | null>(defaultKey);
  const [direction, setDirection] = useState<SortDirection>("asc");

  function toggle(key: K) {
    if (sortKey === key) {
      setDirection((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setDirection("asc");
    }
  }

  return { sortKey, direction, toggle };
}
