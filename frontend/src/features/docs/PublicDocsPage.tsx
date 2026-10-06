import { useEffect, useMemo, useState } from "react";
import { getPublicDocs } from "../../api/client";
import { MarkdownView } from "../../components/MarkdownView";
import type { PublicDocs, PublicDocsNode } from "../../types/watodo";
import "./PublicDocsPage.css";

type Section = "documentation" | "support";

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
  const [activeSection, setActiveSection] = useState<Section>("documentation");
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
  const flatSupportPages = useMemo(() => (docs ? flatten(docs.support_pages) : []), [docs]);

  function switchSection(section: Section) {
    setActiveSection(section);
    if (section === "support") {
      const firstSupportPage = flatSupportPages[0]?.node;
      setSelection(firstSupportPage ? { kind: "page", id: firstSupportPage.id } : null);
    } else {
      const firstPage = flatPages[0]?.node;
      if (firstPage) setSelection({ kind: "page", id: firstPage.id });
      else if (docs?.features.length) setSelection({ kind: "features" });
      else if (docs?.resolutions.length) setSelection({ kind: "resolutions" });
      else setSelection(null);
    }
  }

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

  const activePages = activeSection === "documentation" ? flatPages : flatSupportPages;
  const currentPage =
    selection?.kind === "page" ? activePages.find((row) => row.node.id === selection.id)?.node : null;

  // Personnalisation par projet (session du 2026-09-23) — override du jeton
  // d'accent en cascade CSS pure, vide = habillage Awtodo par défaut.
  const themeStyle = docs.accent_color ? ({ "--color-accent": docs.accent_color } as React.CSSProperties) : undefined;

  return (
    <div className="public-docs-shell" style={themeStyle}>
      {/* Deux onglets "classeur", même habillage que la navigation interne
          Awtodo (binder-tabs) — demande explicite (session du 2026-10-06) de
          reprendre exactement ce design sur la page publique. Les classes
          sont réutilisées directement plutôt que le composant `BinderTabs`,
          couplé à la navigation interne (`ViewName`). */}
      <div className="binder-tabs public-docs__top-tabs" role="tablist" aria-label="Sections de la documentation publique">
        <button
          type="button"
          role="tab"
          aria-selected={activeSection === "documentation"}
          className={`binder-tab${activeSection === "documentation" ? " binder-tab--active" : ""}`}
          onClick={() => switchSection("documentation")}
        >
          Documentation
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeSection === "support"}
          className={`binder-tab${activeSection === "support" ? " binder-tab--active" : ""}`}
          onClick={() => switchSection("support")}
        >
          Support d'utilisation
        </button>
      </div>

      <div className="public-docs">
        <aside className="public-docs__nav">
          <div className="public-docs__brand">{docs.project_name}</div>
          {docs.header_content && <p className="public-docs__header-note">{docs.header_content}</p>}
          {activePages.map(({ node, depth }) => (
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
          {activeSection === "documentation" && docs.features.length > 0 && (
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
          {activeSection === "documentation" && docs.resolutions.length > 0 && (
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
          {activeSection === "documentation" && docs.contributors.length > 0 && (
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
          {activeSection === "support" && activePages.length === 0 && (
            <p className="public-docs__header-note">Pas encore de support d'utilisation publié.</p>
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
              <EntrySection title="Contributeurs" entries={docs.contributors} contributorRows={docs.contributors[0]?.contributor_rows ?? null} />
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
            {docs.contributors.length > 0 && (
              <EntrySection
                title="Contributeurs"
                entries={docs.contributors}
                contributorRows={docs.contributors[0]?.contributor_rows ?? null}
              />
            )}
            {flatSupportPages.map(({ node }) => (
              <article key={node.id} className="public-docs__article">
                <h1>{node.title}</h1>
                <MarkdownView content={node.content} />
              </article>
            ))}
          </div>
        </main>
      </div>
    </div>
  );
}

function EntrySection({
  title,
  entries,
  contributorRows,
}: {
  title: string;
  entries: PublicDocs["features"];
  contributorRows?: PublicDocs["contributors"][number]["contributor_rows"];
}) {
  // Fiche "contributeurs" personnalisée à la main (session du 2026-10-06) :
  // une liste structurée nom/rôle plutôt que le Markdown auto-généré.
  if (contributorRows && contributorRows.length > 0) {
    return (
      <article className="public-docs__article">
        <h1>{title}</h1>
        <ul className="public-docs__contributor-list">
          {contributorRows.map((row, index) => (
            <li key={index} className="public-docs__contributor-row">
              <span className="public-docs__contributor-name">{row.name}</span>
              {row.role && <span className="public-docs__contributor-role">{row.role}</span>}
            </li>
          ))}
        </ul>
      </article>
    );
  }

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
