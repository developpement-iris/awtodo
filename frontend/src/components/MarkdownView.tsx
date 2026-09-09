import type { ReactNode } from "react";
import "./MarkdownView.css";

// Rendu markdown minimal, texte entièrement libre (CLAUDE.md > Cahier des
// charges / Bloc-notes) : pas d'éditeur WYSIWYG, rendu en lecture seule.
// Génère des éléments React plutôt que du HTML injecté — pas de surface XSS,
// pas de dépendance ajoutée pour un sous-ensemble de syntaxe volontairement
// restreint (titres, gras/italique, code inline, liens, listes).

const INLINE_PATTERN = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const parts = text.split(INLINE_PATTERN).filter((part) => part.length > 0);
  return parts.map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return <em key={key}>{part.slice(1, -1)}</em>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={key}>{part.slice(1, -1)}</code>;
    }
    const linkMatch = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part);
    if (linkMatch) {
      return (
        <a key={key} href={linkMatch[2]} target="_blank" rel="noreferrer">
          {linkMatch[1]}
        </a>
      );
    }
    return part;
  });
}

function renderLines(lines: string[], keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  lines.forEach((line, index) => {
    if (index > 0) nodes.push(<br key={`${keyPrefix}-br-${index}`} />);
    nodes.push(...renderInline(line, `${keyPrefix}-${index}`));
  });
  return nodes;
}

function isListLine(line: string, marker: RegExp): boolean {
  return marker.test(line);
}

const UNORDERED_MARKER = /^[-*]\s+/;
const ORDERED_MARKER = /^\d+\.\s+/;

export function MarkdownView({ content }: { content: string }) {
  if (!content.trim()) {
    return <p className="markdown-view__empty">Rien à afficher pour l'instant.</p>;
  }

  const blocks = content.replace(/\r\n/g, "\n").split(/\n{2,}/);

  return (
    <div className="markdown-view">
      {blocks.map((block, blockIndex) => {
        const lines = block.split("\n").filter((line) => line.length > 0);
        if (lines.length === 0) return null;
        const key = `block-${blockIndex}`;

        const headingMatch = /^(#{1,3})\s+(.*)$/.exec(lines[0]);
        if (headingMatch && lines.length === 1) {
          const level = headingMatch[1].length;
          const text = headingMatch[2];
          if (level === 1) return <h3 key={key}>{renderInline(text, key)}</h3>;
          if (level === 2) return <h4 key={key}>{renderInline(text, key)}</h4>;
          return <h5 key={key}>{renderInline(text, key)}</h5>;
        }

        if (lines.every((line) => isListLine(line, UNORDERED_MARKER))) {
          return (
            <ul key={key}>
              {lines.map((line, itemIndex) => (
                <li key={`${key}-${itemIndex}`}>{renderInline(line.replace(UNORDERED_MARKER, ""), `${key}-${itemIndex}`)}</li>
              ))}
            </ul>
          );
        }

        if (lines.every((line) => isListLine(line, ORDERED_MARKER))) {
          return (
            <ol key={key}>
              {lines.map((line, itemIndex) => (
                <li key={`${key}-${itemIndex}`}>{renderInline(line.replace(ORDERED_MARKER, ""), `${key}-${itemIndex}`)}</li>
              ))}
            </ol>
          );
        }

        return <p key={key}>{renderLines(lines, key)}</p>;
      })}
    </div>
  );
}
