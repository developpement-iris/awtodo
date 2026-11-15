// Clé de comparaison d'une catégorie (domaine, service) : sans casse ni
// accents, espaces réduits — miroir de `_category_key` côté serveur
// (apps/projects/services.py), pour que suggestions et filtres traitent
// « Pôle planning » et « pole  Planning » comme la même valeur.
export function categoryKey(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}
