import { Check, Copy, FileDown, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  archiveDocEntry,
  archiveDocPage,
  createDocEntry,
  createDocPage,
  createEntryFromPending,
  enablePublicDocLink,
  getDocumentation,
  ignorePendingDocEntry,
  publishDocEntry,
  publishDocPage,
  revokePublicDocLink,
  rotatePublicDocLink,
  seedFeaturesFromSpec,
  unpublishDocEntry,
  unpublishDocPage,
  updateDocEntry,
  updateDocPage,
} from "../../api/client";
import { MarkdownView } from "../../components/MarkdownView";
import { SkeletonRows } from "../../components/Skeleton";
import { useToast } from "../../context/ToastContext";
import type {
  DocEntry,
  DocEntryKind,
  DocPage,
  DocumentationBundle,
  Project,
} from "../../types/watodo";
import { exportDocsToDocx } from "../docs/exportDocx";
import "./DocumentationTab.css";

type View = "pages" | "fonctionnalite" | "resolution" | "queue" | "link";

interface DocumentationTabProps {
  project: Project;
}

// Aplatit l'arbre (2 niveaux) en liste avec profondeur, pour un sommaire lisible.
function flattenPages(pages: DocPage[], depth = 0): { page: DocPage; depth: number }[] {
  return pages.flatMap((page) => [
    { page, depth },
    ...flattenPages(page.children, depth + 1),
  ]);
}

export function DocumentationTab({ project }: DocumentationTabProps) {
  const { showToast } = useToast();
  const [bundle, setBundle] = useState<DocumentationBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("pages");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      setBundle(await getDocumentation(project.id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Le chargement a échoué.");
    }
  }, [project.id]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function run(action: () => Promise<unknown>, successMessage?: string) {
    setBusy(true);
    try {
      await action();
      await reload();
      if (successMessage) showToast(successMessage);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "L'opération a échoué.");
    } finally {
      setBusy(false);
    }
  }

  const pendingCount =
    (bundle?.pending_features.length ?? 0) + (bundle?.pending_resolutions.length ?? 0);

  const NAV: { id: View; label: string; badge?: number }[] = [
    { id: "pages", label: "Pages" },
    { id: "fonctionnalite", label: "Fonctionnalités" },
    { id: "resolution", label: "Résolution d'incidents" },
    { id: "queue", label: "À documenter", badge: pendingCount || undefined },
    { id: "link", label: "Lien public" },
  ];

  async function handleExport() {
    if (!bundle) return;
    try {
      await exportDocsToDocx(project.name, bundle.pages, bundle.features, bundle.resolutions);
      showToast("Documentation exportée.");
    } catch {
      showToast("L'export a échoué.");
    }
  }

  if (error) return <p className="doc-tab__message doc-tab__message--error">{error}</p>;
  if (!bundle) return <SkeletonRows rows={8} />;

  return (
    <div className="doc-tab">
      <div className="doc-tab__toolbar">
        <button
          type="button"
          className="doc-tab__ghost-btn"
          onClick={handleExport}
          disabled={busy}
        >
          <FileDown size={14} strokeWidth={1.75} aria-hidden="true" />
          Exporter en .docx
        </button>
      </div>

      <div className="doc-tab__layout">
        <nav className="doc-tab__nav" aria-label="Sections de la documentation">
          {NAV.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`doc-tab__nav-item${view === item.id ? " doc-tab__nav-item--active" : ""}`}
              onClick={() => setView(item.id)}
            >
              {item.label}
              {item.badge ? <span className="doc-tab__nav-badge">{item.badge}</span> : null}
            </button>
          ))}
        </nav>

        <div className="doc-tab__panel">
          {view === "pages" && (
            <PagesView projectId={project.id} bundle={bundle} busy={busy} run={run} />
          )}
          {(view === "fonctionnalite" || view === "resolution") && (
            <EntriesView
              projectId={project.id}
              kind={view}
              entries={view === "fonctionnalite" ? bundle.features : bundle.resolutions}
              busy={busy}
              run={run}
            />
          )}
          {view === "queue" && (
            <QueueView
              projectId={project.id}
              bundle={bundle}
              busy={busy}
              run={run}
              onGoToEntries={(kind) => setView(kind)}
            />
          )}
          {view === "link" && (
            <LinkView projectId={project.id} bundle={bundle} busy={busy} run={run} />
          )}
        </div>
      </div>
    </div>
  );
}

// --- Pages ----------------------------------------------------------------

interface PanelProps {
  projectId: string;
  bundle: DocumentationBundle;
  busy: boolean;
  run: (action: () => Promise<unknown>, successMessage?: string) => Promise<void>;
}

function PagesView({ projectId, bundle, busy, run }: PanelProps) {
  const flat = useMemo(() => flattenPages(bundle.pages), [bundle.pages]);
  const [selectedId, setSelectedId] = useState<string | null>(flat[0]?.page.id ?? null);
  const selectedRow = flat.find((row) => row.page.id === selectedId) ?? null;
  const selected = selectedRow?.page ?? null;
  const selectedIsRoot = selectedRow?.depth === 0;

  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    setEditing(false);
    setDraft(selected?.content ?? "");
  }, [selected?.id, selected?.content]);

  async function newPage(parentId: string | null) {
    const title = window.prompt(parentId ? "Titre de la sous-page" : "Titre de la page");
    if (!title) return;
    await run(() => createDocPage(projectId, { title, parent_id: parentId }), "Page créée.");
  }

  async function rename(page: DocPage) {
    const title = window.prompt("Nouveau titre", page.title);
    if (!title || title === page.title) return;
    await run(() => updateDocPage(projectId, page.id, { title }), "Page renommée.");
  }

  return (
    <div className="doc-tab__split">
      <div className="doc-tab__list">
        <div className="doc-tab__list-head">
          <span>Pages</span>
          <button type="button" className="doc-tab__icon-btn" onClick={() => newPage(null)} disabled={busy}>
            <Plus size={14} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>
        {flat.length === 0 && <p className="doc-tab__empty">Aucune page. Créez-en une.</p>}
        {flat.map(({ page, depth }) => (
          <button
            key={page.id}
            type="button"
            className={`doc-tab__list-item${page.id === selectedId ? " doc-tab__list-item--active" : ""}`}
            style={{ paddingLeft: `calc(var(--space-3) + ${depth * 16}px)` }}
            onClick={() => setSelectedId(page.id)}
          >
            <span className="doc-tab__list-item-title">{page.title}</span>
            <StatusDot status={page.status} />
          </button>
        ))}
      </div>

      <div className="doc-tab__editor">
        {!selected ? (
          <p className="doc-tab__empty">Sélectionnez une page.</p>
        ) : (
          <>
            <div className="doc-tab__editor-head">
              <h3>{selected.title}</h3>
              <div className="doc-tab__editor-actions">
                {selectedIsRoot && (
                  <button
                    type="button"
                    className="doc-tab__ghost-btn"
                    onClick={() => newPage(selected.id)}
                    disabled={busy}
                  >
                    <Plus size={13} strokeWidth={2} aria-hidden="true" />
                    Sous-page
                  </button>
                )}
                <button type="button" className="doc-tab__ghost-btn" onClick={() => rename(selected)} disabled={busy}>
                  Renommer
                </button>
                <button
                  type="button"
                  className="doc-tab__ghost-btn"
                  onClick={() =>
                    run(
                      () =>
                        selected.status === "publie"
                          ? unpublishDocPage(projectId, selected.id)
                          : publishDocPage(projectId, selected.id),
                      selected.status === "publie" ? "Page dépubliée." : "Page publiée.",
                    )
                  }
                  disabled={busy}
                >
                  {selected.status === "publie" ? "Dépublier" : "Publier"}
                </button>
                <button
                  type="button"
                  className="doc-tab__ghost-btn doc-tab__ghost-btn--danger"
                  onClick={() => {
                    if (window.confirm("Archiver cette page ?")) {
                      void run(() => archiveDocPage(projectId, selected.id), "Page archivée.");
                      setSelectedId(null);
                    }
                  }}
                  disabled={busy}
                >
                  <Trash2 size={13} strokeWidth={1.75} aria-hidden="true" />
                </button>
              </div>
            </div>

            {editing ? (
              <div className="doc-tab__form">
                <textarea
                  className="doc-tab__textarea"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  rows={16}
                  autoFocus
                  disabled={busy}
                />
                <div className="doc-tab__form-actions">
                  <button
                    type="button"
                    className="doc-tab__ghost-btn"
                    onClick={() => {
                      setEditing(false);
                      setDraft(selected.content);
                    }}
                    disabled={busy}
                  >
                    Annuler
                  </button>
                  <button
                    type="button"
                    className="doc-tab__primary-btn"
                    onClick={() =>
                      run(async () => {
                        await updateDocPage(projectId, selected.id, { content: draft });
                        setEditing(false);
                      }, "Page enregistrée.")
                    }
                    disabled={busy}
                  >
                    Enregistrer
                  </button>
                </div>
              </div>
            ) : (
              <div className="doc-tab__preview" onDoubleClick={() => setEditing(true)}>
                <MarkdownView content={selected.content} />
                <button type="button" className="doc-tab__ghost-btn" onClick={() => setEditing(true)}>
                  Modifier le contenu
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// --- Fiches (fonctionnalités / résolutions) ------------------------------

interface EntriesViewProps {
  projectId: string;
  kind: DocEntryKind;
  entries: DocEntry[];
  busy: boolean;
  run: (action: () => Promise<unknown>, successMessage?: string) => Promise<void>;
}

function EntriesView({ projectId, kind, entries, busy, run }: EntriesViewProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  function startEdit(entry: DocEntry) {
    setEditingId(entry.id);
    setTitle(entry.title);
    setDescription(entry.description);
  }

  async function newEntry() {
    const value = window.prompt(
      kind === "fonctionnalite" ? "Titre de la fonctionnalité" : "Titre de la résolution",
    );
    if (!value) return;
    await run(() => createDocEntry(projectId, { kind, title: value }), "Fiche créée.");
  }

  return (
    <div className="doc-tab__entries">
      <div className="doc-tab__list-head">
        <span>{kind === "fonctionnalite" ? "Fonctionnalités" : "Résolution d'incidents"}</span>
        <div className="doc-tab__editor-actions">
          {kind === "fonctionnalite" && (
            <button
              type="button"
              className="doc-tab__ghost-btn"
              onClick={() =>
                run(async () => {
                  const { created } = await seedFeaturesFromSpec(projectId);
                  return created;
                }, "Fiches créées depuis le cahier des charges.")
              }
              disabled={busy}
            >
              Amorcer depuis le cahier des charges
            </button>
          )}
          <button type="button" className="doc-tab__primary-btn" onClick={newEntry} disabled={busy}>
            <Plus size={13} strokeWidth={2} aria-hidden="true" />
            Nouvelle fiche
          </button>
        </div>
      </div>

      {entries.length === 0 && <p className="doc-tab__empty">Aucune fiche pour l'instant.</p>}

      {entries.map((entry) => (
        <article key={entry.id} className="doc-tab__card">
          {editingId === entry.id ? (
            <div className="doc-tab__form">
              <input
                className="doc-tab__input"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                disabled={busy}
              />
              <textarea
                className="doc-tab__textarea"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={6}
                disabled={busy}
              />
              <div className="doc-tab__form-actions">
                <button type="button" className="doc-tab__ghost-btn" onClick={() => setEditingId(null)} disabled={busy}>
                  Annuler
                </button>
                <button
                  type="button"
                  className="doc-tab__primary-btn"
                  onClick={() =>
                    run(async () => {
                      await updateDocEntry(projectId, entry.id, { title, description });
                      setEditingId(null);
                    }, "Fiche enregistrée.")
                  }
                  disabled={busy}
                >
                  Enregistrer
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="doc-tab__card-head">
                <h4>{entry.title}</h4>
                <StatusDot status={entry.status} />
              </div>
              <MarkdownView content={entry.description} />
              <div className="doc-tab__editor-actions">
                <button type="button" className="doc-tab__ghost-btn" onClick={() => startEdit(entry)} disabled={busy}>
                  Modifier
                </button>
                <button
                  type="button"
                  className="doc-tab__ghost-btn"
                  onClick={() =>
                    run(
                      () =>
                        entry.status === "publie"
                          ? unpublishDocEntry(projectId, entry.id)
                          : publishDocEntry(projectId, entry.id),
                      entry.status === "publie" ? "Fiche dépubliée." : "Fiche publiée.",
                    )
                  }
                  disabled={busy}
                >
                  {entry.status === "publie" ? "Dépublier" : "Publier"}
                </button>
                <button
                  type="button"
                  className="doc-tab__ghost-btn doc-tab__ghost-btn--danger"
                  onClick={() => {
                    if (window.confirm("Archiver cette fiche ?"))
                      void run(() => archiveDocEntry(projectId, entry.id), "Fiche archivée.");
                  }}
                  disabled={busy}
                >
                  <Trash2 size={13} strokeWidth={1.75} aria-hidden="true" />
                </button>
              </div>
            </>
          )}
        </article>
      ))}
    </div>
  );
}

// --- File « À documenter » ----------------------------------------------

interface QueueViewProps extends PanelProps {
  onGoToEntries: (kind: DocEntryKind) => void;
}

function QueueView({ projectId, bundle, busy, run, onGoToEntries }: QueueViewProps) {
  const groups: { kind: DocEntryKind; label: string; items: DocumentationBundle["pending_features"] }[] = [
    { kind: "fonctionnalite", label: "Fonctionnalités livrées", items: bundle.pending_features },
    { kind: "resolution", label: "Incidents résolus", items: bundle.pending_resolutions },
  ];

  return (
    <div className="doc-tab__entries">
      {groups.map((group) => (
        <section key={group.kind}>
          <div className="doc-tab__list-head">
            <span>{group.label}</span>
          </div>
          {group.items.length === 0 && <p className="doc-tab__empty">Rien en attente.</p>}
          {group.items.map((item) => (
            <article key={item.id} className="doc-tab__card doc-tab__card--row">
              <div>
                <p className="doc-tab__pending-title">{item.source_title}</p>
                <p className="doc-tab__pending-meta">
                  {item.source_label} · {new Date(item.created_at).toLocaleDateString("fr-FR")}
                </p>
              </div>
              <div className="doc-tab__editor-actions">
                <button
                  type="button"
                  className="doc-tab__primary-btn"
                  onClick={() =>
                    run(async () => {
                      await createEntryFromPending(projectId, item.id);
                      onGoToEntries(group.kind);
                    }, "Fiche créée.")
                  }
                  disabled={busy}
                >
                  Créer la fiche
                </button>
                <button
                  type="button"
                  className="doc-tab__ghost-btn"
                  onClick={() => {
                    if (window.confirm("Ignorer cette entrée ?"))
                      void run(() => ignorePendingDocEntry(projectId, item.id), "Entrée ignorée.");
                  }}
                  disabled={busy}
                >
                  Ignorer
                </button>
              </div>
            </article>
          ))}
        </section>
      ))}
    </div>
  );
}

// --- Lien public --------------------------------------------------------

function LinkView({ projectId, bundle, busy, run }: PanelProps) {
  const { showToast } = useToast();
  const [copied, setCopied] = useState(false);
  const { public_url: url } = bundle.space;

  async function copy() {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      showToast("Lien copié.");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      showToast("Impossible de copier le lien.");
    }
  }

  return (
    <div className="doc-tab__link">
      {url ? (
        <>
          <p className="doc-tab__link-hint">
            Toute personne disposant de ce lien peut lire les pages et fiches <strong>publiées</strong>,
            sans compte Awtodo.
          </p>
          <div className="doc-tab__link-row">
            <input className="doc-tab__input" value={url} readOnly onFocus={(e) => e.target.select()} />
            <button type="button" className="doc-tab__icon-btn" onClick={copy} aria-label="Copier le lien">
              {copied ? <Check size={14} strokeWidth={2} /> : <Copy size={14} strokeWidth={1.75} />}
            </button>
          </div>
          <div className="doc-tab__editor-actions">
            <button
              type="button"
              className="doc-tab__ghost-btn"
              onClick={() => {
                if (window.confirm("Régénérer le lien ? L'ancien cessera de fonctionner."))
                  void run(() => rotatePublicDocLink(projectId), "Nouveau lien généré.");
              }}
              disabled={busy}
            >
              <RefreshCw size={13} strokeWidth={1.75} aria-hidden="true" />
              Régénérer
            </button>
            <button
              type="button"
              className="doc-tab__ghost-btn doc-tab__ghost-btn--danger"
              onClick={() => {
                if (window.confirm("Révoquer le lien public ?"))
                  void run(() => revokePublicDocLink(projectId), "Lien révoqué.");
              }}
              disabled={busy}
            >
              Révoquer
            </button>
          </div>
        </>
      ) : (
        <>
          <p className="doc-tab__link-hint">
            Aucun lien public actif. En l'activant, vous créez une URL non devinable donnant accès en
            lecture seule aux pages publiées.
          </p>
          <button
            type="button"
            className="doc-tab__primary-btn"
            onClick={() => run(() => enablePublicDocLink(projectId), "Lien public activé.")}
            disabled={busy}
          >
            Activer le lien public
          </button>
        </>
      )}
    </div>
  );
}

function StatusDot({ status }: { status: DocEntry["status"] }) {
  const label = status === "publie" ? "Publié" : status === "brouillon" ? "Brouillon" : "Archivé";
  return <span className={`doc-tab__status doc-tab__status--${status}`}>{label}</span>;
}
