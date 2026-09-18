import { useEffect, useState } from "react";
import { useCurrentUser } from "../context/CurrentUserContext";

function storageKey(listKey: string, userId: string | undefined): string {
  return `awtodo:columns:${listKey}:${userId ?? "anon"}`;
}

/**
 * Colonnes affichées sur une liste (Tâches, Incidents…), personnalisables
 * par utilisateur et mémorisées en cache local (pas en base — préférence
 * d'affichage par appareil, pas une donnée à synchroniser entre postes, voir
 * docs/organisation-et-comptes.md > "Colonnes personnalisables des listes").
 */
export function useColumnPreferences<K extends string>(
  listKey: string,
  allKeys: readonly K[],
  defaultVisible: readonly K[],
): [Set<K>, (next: Set<K>) => void] {
  const { currentUser } = useCurrentUser();
  const [visible, setVisible] = useState<Set<K>>(() => new Set(defaultVisible));

  useEffect(() => {
    let next: Set<K> = new Set(defaultVisible);
    try {
      const raw = window.localStorage.getItem(storageKey(listKey, currentUser?.id));
      if (raw) {
        const parsed = JSON.parse(raw) as string[];
        const known = new Set<string>(allKeys);
        next = new Set(parsed.filter((key): key is K => known.has(key)));
      }
    } catch {
      // localStorage indisponible (navigation privée, quota…) — repli sur les défauts.
    }
    setVisible(next);
    // `allKeys`/`defaultVisible` sont des constantes au niveau module côté
    // appelant — seuls `listKey`/l'utilisateur courant font varier la clé.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listKey, currentUser?.id]);

  function update(next: Set<K>) {
    setVisible(next);
    try {
      window.localStorage.setItem(storageKey(listKey, currentUser?.id), JSON.stringify(Array.from(next)));
    } catch {
      // ignore — la préférence ne persistera pas, sans bloquer l'affichage.
    }
  }

  return [visible, update];
}
