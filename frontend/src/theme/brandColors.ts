// Couleurs de marque de l'organisation (session du 2026-09-28, écran
// Administration > Marque) — remplace l'ancienne préférence d'accent par
// utilisateur (session du 2026-09-23), jugée trop limitée : elle ne
// changeait que la bande de marque (BinderTabs/sidebar) + l'accent, jamais
// le fond/surface de l'appli. Deux couleurs indépendantes désormais :
//
// - `primary` recolore le fond/surface (`--color-bg`/`--color-surface`/
//   `--color-surface-raised`/`--color-border`/`--color-text*`) — une rampe
//   calculée depuis cette seule teinte, avec la même relation que la
//   charte par défaut entre ces tokens (surface toujours plus claire que
//   le fond, quel que soit le sens du thème).
// - `secondary` recolore la bande de marque fixe (BinderTabs/SectionSidebar)
//   + les boutons d'accent + le statut de tâche "en cours" — reprend
//   exactement la logique de l'ancien `applyAccentColor`.
//
// Les deux sont appliquées globalement (organisation), pas par utilisateur.

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
// puisqu'une couleur choisie librement peut être aussi bien claire que
// foncée.
function contrastTextFor(rgb: [number, number, number]): string {
  return relativeLuminance(rgb) > 0.44 ? "#1A1A1A" : "#FFFFFF";
}

function darken([r, g, b]: [number, number, number], amount: number): [number, number, number] {
  return [r * (1 - amount), g * (1 - amount), b * (1 - amount)];
}

function lighten([r, g, b]: [number, number, number], amount: number): [number, number, number] {
  return [r + (255 - r) * amount, g + (255 - g) * amount, b + (255 - b) * amount];
}

const SECONDARY_TOKENS = [
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
];

const PRIMARY_TOKENS = [
  "--color-bg",
  "--color-surface",
  "--color-surface-raised",
  "--color-border",
  "--color-text",
  "--color-text-muted",
  "--color-text-faint",
];

function applySecondaryColor(root: CSSStyleDeclaration, hex: string): void {
  const rgb = hexToRgb(hex);
  if (!rgb) {
    SECONDARY_TOKENS.forEach((token) => root.removeProperty(token));
    return;
  }

  const contrast = contrastTextFor(rgb);
  const strongHex = rgbToHex(darken(rgb, 0.18));
  const mutedRgba = contrast === "#FFFFFF" ? "rgba(255, 255, 255, 0.7)" : "rgba(26, 26, 26, 0.65)";
  const activeBgRgba = contrast === "#FFFFFF" ? "rgba(255, 255, 255, 0.14)" : "rgba(26, 26, 26, 0.1)";

  root.setProperty("--color-accent", hex);
  root.setProperty("--color-accent-strong", strongHex);
  root.setProperty("--color-accent-contrast", contrast);

  // Bande de marque (BinderTabs/SectionSidebar) — couleur constante quel
  // que soit le thème clair/sombre, comme la charte par défaut.
  root.setProperty("--sidebar-bg", hex);
  root.setProperty("--sidebar-text", contrast);
  root.setProperty("--sidebar-muted", mutedRgba);
  root.setProperty("--sidebar-active", contrast);
  root.setProperty("--sidebar-active-bg", activeBgRgba);

  // "En cours" == littéralement l'accent dans la charte par défaut (voir
  // tokens.css) — seul statut de tâche qui EST la couleur de marque, pas
  // une teinte dérivée : substitution directe légitime.
  root.setProperty("--task-status-inprogress-bg", hex);
  root.setProperty("--task-status-inprogress-text", contrast);
}

function applyPrimaryColor(root: CSSStyleDeclaration, hex: string): void {
  const rgb = hexToRgb(hex);
  if (!rgb) {
    PRIMARY_TOKENS.forEach((token) => root.removeProperty(token));
    return;
  }

  const isLight = relativeLuminance(rgb) > 0.5;
  // La surface est toujours un cran plus claire que le fond, dans les deux
  // sens de thème (déjà vrai dans la charte par défaut : blanc pur sur
  // fond crème en clair, gris-brun plus clair sur fond quasi noir en
  // sombre) — direction fixe, contrairement au texte/à la bordure, qui
  // doivent au contraire s'éloigner du fond pour rester lisibles (foncé sur
  // fond clair, clair sur fond sombre).
  const surface = rgbToHex(lighten(rgb, 0.05));
  const surfaceRaised = rgbToHex(lighten(rgb, 0.1));
  const contrastStep = isLight ? darken : lighten;
  const border = rgbToHex(contrastStep(rgb, isLight ? 0.14 : 0.2));
  const text = rgbToHex(contrastStep(rgb, 0.85));
  const textMuted = rgbToHex(contrastStep(rgb, 0.55));
  const textFaint = rgbToHex(contrastStep(rgb, 0.32));

  root.setProperty("--color-bg", hex);
  root.setProperty("--color-surface", surface);
  root.setProperty("--color-surface-raised", surfaceRaised);
  root.setProperty("--color-border", border);
  root.setProperty("--color-text", text);
  root.setProperty("--color-text-muted", textMuted);
  root.setProperty("--color-text-faint", textFaint);
}

export function applyBrandColors(primaryHex: string, secondaryHex: string): void {
  const root = document.documentElement.style;
  applyPrimaryColor(root, primaryHex);
  applySecondaryColor(root, secondaryHex);
}
