// Couleur d'accent personnalisée par utilisateur (session du 2026-09-23,
// écran Réglages) — remplace `--color-accent` app-wide via une variable CSS
// posée sur `:root`, jamais en dur dans un composant. `--color-accent-contrast`
// est recalculé (luminance relative WCAG) plutôt que fixé : une couleur
// choisie librement par l'utilisateur peut être claire ou foncée, contrairement
// à la teinte de marque fixe qui n'avait besoin que d'un blanc.

function relativeLuminance(hex: string): number | null {
  const match = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!match) return null;
  const value = match[1];
  const channel = (start: number) => {
    const c = parseInt(value.slice(start, start + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(0) + 0.7152 * channel(2) + 0.0722 * channel(4);
}

function contrastTextFor(hex: string): string {
  const luminance = relativeLuminance(hex);
  if (luminance === null) return "#FFFFFF";
  // Seuil usuel (~0.44) pour décider noir/blanc à partir de la luminance
  // relative — plus fiable qu'un simple seuil sur la somme RGB.
  return luminance > 0.44 ? "#1A1A1A" : "#FFFFFF";
}

export function applyAccentColor(hex: string): void {
  const root = document.documentElement.style;
  if (!hex) {
    root.removeProperty("--color-accent");
    root.removeProperty("--color-accent-contrast");
    return;
  }
  root.setProperty("--color-accent", hex);
  root.setProperty("--color-accent-contrast", contrastTextFor(hex));
}
