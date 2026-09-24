import { useEffect, useMemo, useState } from "react";
import { getPublicDocs } from "../../api/client";
import { MarkdownView } from "../../components/MarkdownView";
import type { PublicDocs, PublicDocsNode } from "../../types/watodo";
import "./PublicDocsPage.css";

type Selection =
  | { kind: "page"; id: string }
  | { kind: "features" }
  | { kind: "resolutions" }
  | { kind: "contributors" };

function flatten(nodes: PublicDocsNode[], depth = 0): { node: PublicDocsNode; depth: number }[] {
  return nodes.flatMap((node) => [{ node, depth }, ...flatten(node.children, depth + 1)]);
}

export function PublicDocsPage({ token }: { token: string }) {
  const [docs, setDocs] = useState<PublicDocs | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "missing">("loading");
  const [selection, setSelection] = useState<Selection | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPublicDocs(token)
      .then((data) => {
        if (cancelled) return;
        setDocs(data);
        setState("ready");
        const firstPage = flatten(data.pages)[0]?.node;
        if (firstPage) setSelection({ kind: "page", id: firstPage.id });
        else if (data.features.length) setSelection({ kind: "features" });
        else if (data.resolutions.length) setSelection({ kind: "resolutions" });
      })
      .catch(() => {
        if (!cancelled) setState("missing");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const flatPages = useMemo(() => (docs ? flatten(docs.pages) : []), [docs]);

  if (state === "loading") {
    return <div className="public-docs public-docs--center">Chargement…</div>;
  }

  if (state === "missing" || !docs) {
    return (
      <div className="public-docs public-docs--center">
        <div>
          <h1 className="public-docs__404-title">Documentation introuvable</h1>
          <p className="public-docs__404-text">
            Cette documentation n'existe pas ou n'est plus partagée.
          </p>
        </div>
      </div>
    );
  }

  const currentPage =
    selection?.kind === "page" ? flatPages.find((row) => row.node.id === selection.id)?.node : null;

  // Personnalisation par projet (session du 2026-09-23) — override du jeton
  // d'accent en cascade CSS pure, vide = habillage Awtodo par défaut.
  const themeStyle = docs.accent_color ? ({ "--color-accent": docs.accent_color } as React.CSSProperties) : undefined;

  return (
    <div className="public-docs" style={themeStyle}>
      <aside className="public-docs__nav">
        <div className="public-docs__brand">{docs.project_name}</div>
        {docs.header_content && <p className="public-docs__header-note">{docs.header_content}</p>}
        {flatPages.map(({ node, depth }) => (
          <button
            key={node.id}
            type="button"
            className={`public-docs__nav-item${
              selection?.kind === "page" && selection.id === node.id
                ? " public-docs__nav-item--active"
                : ""
            }`}
            style={{ paddingLeft: `calc(var(--space-4) + ${depth * 14}px)` }}
            onClick={() => setSelection({ kind: "page", id: node.id })}
          >
            {node.title}
          </button>
        ))}
        {docs.features.length > 0 && (
          <button
            type="button"
            className={`public-docs__nav-item${
              selection?.kind === "features" ? " public-docs__nav-item--active" : ""
            }`}
            onClick={() => setSelection({ kind: "features" })}
          >
            Fonctionnalités
          </button>
        )}
        {docs.resolutions.length > 0 && (
          <button
            type="button"
            className={`public-docs__nav-item${
              selection?.kind === "resolutions" ? " public-docs__nav-item--active" : ""
            }`}
            onClick={() => setSelection({ kind: "resolutions" })}
          >
            Résolution d'incidents
          </button>
        )}
        {docs.contributors.length > 0 && (
          <button
            type="button"
            className={`public-docs__nav-item${
              selection?.kind === "contributors" ? " public-docs__nav-item--active" : ""
            }`}
            onClick={() => setSelection({ kind: "contributors" })}
          >
            Contributeurs
          </button>
        )}
        {docs.footer_content && <p className="public-docs__footer-note">{docs.footer_content}</p>}
        <p className="public-docs__footer">Documentation propulsée par Awtodo</p>
      </aside>

      <main className="public-docs__content">
        <div className="public-docs__screen">
          {currentPage && (
            <article className="public-docs__article">
              <h1>{currentPage.title}</h1>
              <MarkdownView content={currentPage.content} />
            </article>
          )}
          {selection?.kind === "features" && (
            <EntrySection title="Fonctionnalités" entries={docs.features} />
          )}
          {selection?.kind === "resolutions" && (
            <EntrySection title="Résolution d'incidents" entries={docs.resolutions} />
          )}
          {selection?.kind === "contributors" && (
            <EntrySection title="Contributeurs" entries={docs.contributors} />
          )}
        </div>

        {/* Version imprimable : toutes les sections à la suite (masquée à l'écran). */}
        <div className="public-docs__print-only">
          {flatPages.map(({ node }) => (
            <article key={node.id} className="public-docs__article">
              <h1>{node.title}</h1>
              <MarkdownView content={node.content} />
            </article>
          ))}
          {docs.features.length > 0 && <EntrySection title="Fonctionnalités" entries={docs.features} />}
          {docs.resolutions.length > 0 && (
            <EntrySection title="Résolution d'incidents" entries={docs.resolutions} />
          )}
          {docs.contributors.length > 0 && <EntrySection title="Contributeurs" entries={docs.contributors} />}
        </div>
      </main>
    </div>
  );
}

function EntrySection({
  title,
  entries,
}: {
  title: string;
  entries: PublicDocs["features"];
}) {
  return (
    <article className="public-docs__article">
      <h1>{title}</h1>
      {entries.map((entry) => (
        <section key={entry.id} className="public-docs__entry">
          <div className="public-docs__entry-head">
            <h2>{entry.title}</h2>
            {entry.version_label && (
              <span className="public-docs__version-badge">{entry.version_label}</span>
            )}
          </div>
          <p className="public-docs__entry-date">{new Date(entry.created_at).toLocaleDateString("fr-FR")}</p>
          <MarkdownView content={entry.description} />
        </section>
      ))}
    </article>
  );
}
