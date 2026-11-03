// Bibliothèque d'images d'illustration de projet (session du 2026-11-03),
// livrée avec le frontend (`public/covers/`) en attendant un vrai stockage de
// fichiers. Les clés doivent rester alignées sur
// `apps.projects.models.Project.COVER_IMAGE_CHOICES` (validées côté serveur).
// Images reprises de la maquette Folio fournie par l'utilisateur.
export const PROJECT_COVER_IMAGES: { key: string; label: string; src: string }[] = [
  { key: "refonte-site-web", label: "Site web", src: "/covers/refonte-site-web.webp" },
  { key: "application-mobile", label: "Application mobile", src: "/covers/application-mobile.webp" },
  { key: "identite-de-marque", label: "Identité de marque", src: "/covers/identite-de-marque.webp" },
  { key: "campagne-lancement", label: "Campagne", src: "/covers/campagne-lancement.webp" },
  { key: "portail-client", label: "Portail client", src: "/covers/portail-client.webp" },
  { key: "dashboard-analytics", label: "Tableau de bord", src: "/covers/dashboard-analytics.webp" },
];

export function coverImageSrc(key: string): string | undefined {
  return PROJECT_COVER_IMAGES.find((image) => image.key === key)?.src;
}
