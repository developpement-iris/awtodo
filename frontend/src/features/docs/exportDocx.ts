import { Document, HeadingLevel, Packer, Paragraph } from "docx";
import type { DocEntry, DocPage } from "../../types/watodo";

// Nom de fichier sûr sur tous les OS (mêmes règles que SpecTab).
function sanitizeFilename(value: string): string {
  return value.replace(/[/\\:*?"<>|]/g, "-").trim();
}

function pushLines(children: Paragraph[], text: string) {
  const lines = text ? text.split("\n") : [""];
  for (const line of lines) children.push(new Paragraph({ text: line }));
}

function pushPage(children: Paragraph[], page: DocPage, level: 1 | 2) {
  children.push(
    new Paragraph({
      text: page.title,
      heading: level === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
    }),
  );
  pushLines(children, page.content);
  for (const child of page.children) pushPage(children, child, 2);
}

// Génération 100% navigateur (lib `docx`, aucun backend) — objectif : un
// fichier réellement rééditable dans Word, pas un rendu léché. Voir aussi
// SpecTab.exportSpecToDocx.
export async function exportDocsToDocx(
  projectName: string,
  pages: DocPage[],
  features: DocEntry[],
  resolutions: DocEntry[],
): Promise<void> {
  const children: Paragraph[] = [];

  for (const page of pages) pushPage(children, page, 1);

  const entrySection = (label: string, entries: DocEntry[]) => {
    if (entries.length === 0) return;
    children.push(new Paragraph({ text: label, heading: HeadingLevel.HEADING_1 }));
    for (const entry of entries) {
      children.push(new Paragraph({ text: entry.title, heading: HeadingLevel.HEADING_2 }));
      pushLines(children, entry.description);
    }
  };

  entrySection("Fonctionnalités", features);
  entrySection("Résolution d'incidents", resolutions);

  const doc = new Document({ sections: [{ children }] });
  const blob = await Packer.toBlob(doc);
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${sanitizeFilename(projectName)} — Documentation.docx`;
  link.click();
  URL.revokeObjectURL(link.href);
}
