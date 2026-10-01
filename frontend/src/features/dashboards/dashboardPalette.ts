// Rampe monochrome sur `--color-accent` (même principe que les camemberts de
// l'onglet Budgétisation, voir docs/charte-graphique.md) — un widget du
// Dashboard n'a pas d'axe sémantique propre (contrairement à la priorité/au
// statut), donc pas de raison d'improviser une nouvelle palette arc-en-ciel.
export function paletteColor(index: number): string {
  const opacities = [92, 74, 58, 45, 34, 25];
  const opacity = opacities[index % opacities.length];
  return `color-mix(in srgb, var(--color-accent) ${opacity}%, var(--tone-neutral-text) ${100 - opacity}%)`;
}
