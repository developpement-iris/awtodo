// Couleur d'interface personnalisée par utilisateur (session du 2026-09-23,
// écran Réglages — corrigée le 2026-09-24 : "le but est que ça change la
// couleur de TOUT le site, que ça remplace la charte graphique", la première
// passe ne remplaçait que `--color-accent` (boutons/liens), pas assez).
//
// Remplace toute la **famille de marque** (accent + sidebar/topbar + le
// statut de tâche "en cours", qui est littéralement la couleur d'accent
// réutilisée telle quelle dans les jetons — voir tokens.css) par la couleur
// choisie, avec les variantes (foncé, contraste texte) recalculées à la
// volée puisqu'une couleur libre n'a pas les nuances pré-choisies à la main
// de la charte par défaut.
//
// Volontairement PAS touché : les axes sémantiques (priorité, statut
// d'incident, positif/erreur) et les tons "assigned"/"available" du statut
// de tâche (teintes distinctes, pas la couleur d'accent elle-même) — la
// règle du projet "une couleur = un axe" doit rester vraie indépendamment de
// la couleur de marque choisie, sinon la priorité "critique" ou un badge de
// statut perdrait sa signification en cas de collision avec l'accent choisi.

function hexToRgb(hex: string): [number, number, number] | null {
  const match = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!match) return null;
  const v = match[1];
  return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
}

function rgbToHex([r, g, b]: [number, number, number]): string {
  const clamp = (n: number) => Math.max(0, Math.min(255, Math.round(n)));
  return `#${[r, g, b].map((c) => clamp(c).toString(16).padStart(2, "0")).join("")}`;
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const channel = (c: number) => {
    const v = c / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

// Seuil usuel (~0.44) pour décider noir/blanc à partir de la luminance
// relative — plus fiable qu'un simple seuil sur la somme RGB, nécessaire ici
// puisqu'une couleur choisie librement peut être aussi bien claire que foncée
// (contrairement à la teinte de marque fixe, qui n'avait besoin que de blanc).
function contrastTextFor(rgb: [number, number, number]): string {
  return relativeLuminance(rgb) > 0.44 ? "#1A1A1A" : "#FFFFFF";
}

function darken([r, g, b]: [number, number, number], amount: number): [number, number, number] {
  return [r * (1 - amount), g * (1 - amount), b * (1 - amount)];
}

export function applyAccentColor(hex: string): void {
  const root = document.documentElement.style;
  const rgb = hexToRgb(hex);
  if (!rgb) {
    [
      "--color-accent",
      "--color-accent-strong",
      "--color-accent-contrast",
      "--sidebar-bg",
      "--sidebar-text",
      "--sidebar-muted",
      "--sidebar-active",
      "--sidebar-active-bg",
      "--task-status-inprogress-bg",
      "--task-status-inprogress-text",
    ].forEach((token) => root.removeProperty(token));
    return;
  }

  const contrast = contrastTextFor(rgb);
  const strongHex = rgbToHex(darken(rgb, 0.18));
  const mutedRgba = contrast === "#FFFFFF" ? "rgba(255, 255, 255, 0.7)" : "rgba(26, 26, 26, 0.65)";
  const activeBgRgba = contrast === "#FFFFFF" ? "rgba(255, 255, 255, 0.14)" : "rgba(26, 26, 26, 0.1)";

  root.setProperty("--color-accent", hex);
  root.setProperty("--color-accent-strong", strongHex);
  root.setProperty("--color-accent-contrast", contrast);

  // Topbar/onglets classeur — couleur constante quel que soit le thème
  // clair/sombre (voir tokens.css), donc jamais besoin de variante ici.
  root.setProperty("--sidebar-bg", hex);
  root.setProperty("--sidebar-text", contrast);
  root.setProperty("--sidebar-muted", mutedRgba);
  root.setProperty("--sidebar-active", contrast);
  root.setProperty("--sidebar-active-bg", activeBgRgba);

  // "En cours" == littéralement l'accent dans les deux thèmes (voir
  // tokens.css) — seul statut de tâche qui EST la couleur de marque, pas une
  // teinte dérivée : substitution directe légitime.
  root.setProperty("--task-status-inprogress-bg", hex);
  root.setProperty("--task-status-inprogress-text", contrast);
}
