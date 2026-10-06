import { Check, Copy, FileDown, Paperclip, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  archiveDocEntry,
  archiveDocPage,
  createDocEntry,
  createDocPage,
  createEntryFromPending,
  enablePublicDocLink,
  generateContributorsEntry,
  getDocumentation,
  getProjectVersions,
  ignorePendingDocEntry,
  publishDocEntry,
  publishDocPage,
  revokePublicDocLink,
  rotatePublicDocLink,
  seedFeaturesFromSpec,
  setDocPublicSlug,
  unpublishDocEntry,
  unpublishDocPage,
  updateContributorsEntry,
  updateDocEntry,
  updateDocPage,
  updateDocSpaceAppearance,
} from "../../api/client";
import { Combobox } from "../../components/Combobox";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { MarkdownView } from "../../components/MarkdownView";
import { PromptDialog } from "../../components/PromptDialog";
import { SkeletonRows } from "../../components/Skeleton";
import { useToast } from "../../context/ToastContext";
import type {
  ContributorRow,
  DocEntry,
  DocEntryKind,
  DocPage,
  DocPageSection,
  DocumentationBundle,
  Project,
  ProjectVersion,
} from "../../types/watodo";
import { exportDocsToDocx } from "../docs/exportDocx";
import "./DocumentationTab.css";

type View =
  | "pages"
  | "support"
  | "fonctionnalite"
  | "resolution"
  | "contributors"
  | "queue"
  | "link"
  | "appearance";

// Filtre texte insensible à la casse/accents — même principe simple que les
// autres recherches côté front de l'app (pas d'endpoint dédié, le volume de
// contenu par projet reste modeste). Retour direct : "pas de recherche dans
// les pages/fiches" (session du 2026-09-23).
function normalize(value: string): string {
  return value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function matches(query: string, ...fields: string[]): boolean {
  if (!query.trim()) return true;
  const needle = normalize(query);
  return fields.some((f) => normalize(f).includes(needle));
}

// Insère une image ou un PDF encodé en base64 directement dans le Markdown
// (session du 2026-09-23, PDF ajouté le 2026-10-06 — "c'est léger, ça
// pèsera pas beaucoup", vidéos différées jusqu'à l'infra AWS) — aucun
// stockage fichier (S3/boto3) n'est disponible tant que l'infra AWS n'est
// pas tranchée (voir CLAUDE.md > Stack technique), solution retenue
// explicitement avec l'utilisateur en attendant. Limite de taille pour ne
// pas faire exploser la page.
const MAX_ATTACHMENT_BYTES = 1_500_000;

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

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
  const [versions, setVersions] = useState<ProjectVersion[]>([]);
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

  useEffect(() => {
    getProjectVersions(project.id)
      .then(setVersions)
      .catch(() => undefined);
  }, [project.id]);

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
    { id: "support", label: "Support d'utilisation" },
    { id: "fonctionnalite", label: "Fonctionnalités" },
    { id: "resolution", label: "Résolution d'incidents" },
    { id: "contributors", label: "Contributeurs" },
    { id: "queue", label: "À documenter", badge: pendingCount || undefined },
    { id: "link", label: "Lien public" },
    { id: "appearance", label: "Personnalisation" },
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
            <PagesView
              projectId={project.id}
              pages={bundle.pages}
              section="documentation"
              busy={busy}
              run={run}
            />
          )}
          {view === "support" && (
            <PagesView
              projectId={project.id}
              pages={bundle.support_pages}
              section="support"
              busy={busy}
              run={run}
            />
          )}
          {(view === "fonctionnalite" || view === "resolution") && (
            <EntriesView
              projectId={project.id}
              kind={view}
              entries={view === "fonctionnalite" ? bundle.features : bundle.resolutions}
              versions={versions}
              busy={busy}
              run={run}
            />
          )}
          {view === "contributors" && (
            <ContributorsView projectId={project.id} entry={bundle.contributors[0] ?? null} busy={busy} run={run} />
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
          {view === "appearance" && (
            <AppearanceView projectId={project.id} bundle={bundle} busy={busy} run={run} />
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

interface PagesViewProps {
  projectId: string;
  pages: DocPage[];
  section: DocPageSection;
  busy: boolean;
  run: (action: () => Promise<unknown>, successMessage?: string) => Promise<void>;
}

function PagesView({ projectId, pages, section, busy, run }: PagesViewProps) {
  const flat = useMemo(() => flattenPages(pages), [pages]);
  const [selectedId, setSelectedId] = useState<string | null>(flat[0]?.page.id ?? null);
  const selectedRow = flat.find((row) => row.page.id === selectedId) ?? null;
  const selected = selectedRow?.page ?? null;
  const selectedIsRoot = selectedRow?.depth === 0;

  const [query, setQuery] = useState("");
  const visible = useMemo(
    () => flat.filter(({ page }) => matches(query, page.title, page.content)),
    [flat, query],
  );

  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState(false);
  const [imageBusy, setImageBusy] = useState(false);
  const { showToast: showImageToast } = useToast();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // `undefined` = fermé ; `null` = page racine ; un id = sous-page de cette page.
  const [newPageParentId, setNewPageParentId] = useState<string | null | undefined>(undefined);
  const [renameTarget, setRenameTarget] = useState<DocPage | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<DocPage | null>(null);

  useEffect(() => {
    setEditing(false);
    setDraft(selected?.content ?? "");
  }, [selected?.id, selected?.content]);

  async function insertAttachment(file: File | undefined) {
    if (!file) return;
    if (file.size > MAX_ATTACHMENT_BYTES) {
      showImageToast("Fichier trop lourd (max ~1,5 Mo) — la doc n'a pas encore de stockage de fichiers dédié.");
      return;
    }
    setImageBusy(true);
    try {
      const dataUrl = await readFileAsDataUrl(file);
      const isPdf = file.type === "application/pdf";
      const markdown = isPdf ? `\n[📄 ${file.name}](${dataUrl})\n` : `\n![${file.name}](${dataUrl})\n`;
      const el = textareaRef.current;
      if (el) {
        const pos = el.selectionStart ?? draft.length;
        setDraft(draft.slice(0, pos) + markdown + draft.slice(pos));
      } else {
        setDraft(draft + markdown);
      }
    } catch {
      showImageToast("Impossible de lire ce fichier.");
    } finally {
      setImageBusy(false);
    }
  }

  return (
    <div className="doc-tab__split">
      <div className="doc-tab__list">
        <div className="doc-tab__list-head">
          <span>Pages</span>
          <button type="button" className="doc-tab__icon-btn" onClick={() => setNewPageParentId(null)} disabled={busy}>
            <Plus size={14} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>
        <div className="doc-tab__search">
          <Search size={13} strokeWidth={1.75} aria-hidden="true" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Rechercher une page…"
            aria-label="Rechercher une page"
          />
        </div>
        {flat.length === 0 && <p className="doc-tab__empty">Aucune page. Créez-en une.</p>}
        {flat.length > 0 && visible.length === 0 && <p className="doc-tab__empty">Aucun résultat.</p>}
        {visible.map(({ page, depth }) => (
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
              <div>
                <h3>{selected.title}</h3>
                <p className="doc-tab__timestamp">
                  Modifiée le {new Date(selected.updated_at).toLocaleString("fr-FR")}
                </p>
              </div>
              <div className="doc-tab__editor-actions">
                {selectedIsRoot && (
                  <button
                    type="button"
                    className="doc-tab__ghost-btn"
                    onClick={() => setNewPageParentId(selected.id)}
                    disabled={busy}
                  >
                    <Plus size={13} strokeWidth={2} aria-hidden="true" />
                    Sous-page
                  </button>
                )}
                <button type="button" className="doc-tab__ghost-btn" onClick={() => setRenameTarget(selected)} disabled={busy}>
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
                  onClick={() => setArchiveTarget(selected)}
                  disabled={busy}
                >
                  <Trash2 size={13} strokeWidth={1.75} aria-hidden="true" />
                </button>
              </div>
            </div>

            {editing ? (
              <div className="doc-tab__form">
                <label className="doc-tab__ghost-btn doc-tab__image-btn">
                  <Paperclip size={13} strokeWidth={1.75} aria-hidden="true" />
                  {imageBusy ? "Chargement…" : "Insérer une image ou un PDF"}
                  <input
                    type="file"
                    accept="image/*,application/pdf"
                    hidden
                    disabled={busy || imageBusy}
                    onChange={(e) => {
                      void insertAttachment(e.target.files?.[0]);
                      e.target.value = "";
                    }}
                  />
                </label>
                <textarea
                  ref={textareaRef}
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

      {newPageParentId !== undefined && (
        <PromptDialog
          title={newPageParentId ? "Nouvelle sous-page" : "Nouvelle page"}
          label="Titre"
          confirmLabel="Créer"
          onCancel={() => setNewPageParentId(undefined)}
          onConfirm={(title) => {
            const parentId = newPageParentId;
            setNewPageParentId(undefined);
            void run(() => createDocPage(projectId, { title, parent_id: parentId, section }), "Page créée.");
          }}
        />
      )}

      {renameTarget && (
        <PromptDialog
          title="Renommer la page"
          label="Titre"
          initialValue={renameTarget.title}
          confirmLabel="Renommer"
          onCancel={() => setRenameTarget(null)}
          onConfirm={(title) => {
            const page = renameTarget;
            setRenameTarget(null);
            if (title !== page.title) void run(() => updateDocPage(projectId, page.id, { title }), "Page renommée.");
          }}
        />
      )}

      {archiveTarget && (
        <ConfirmDialog
          title="Archiver cette page ?"
          confirmLabel="Archiver"
          danger
          onCancel={() => setArchiveTarget(null)}
          onConfirm={() => {
            const page = archiveTarget;
            setArchiveTarget(null);
            void run(() => archiveDocPage(projectId, page.id), "Page archivée.");
            setSelectedId(null);
          }}
        />
      )}
    </div>
  );
}

// --- Fiches (fonctionnalités / résolutions) ------------------------------

interface EntriesViewProps {
  projectId: string;
  kind: DocEntryKind;
  entries: DocEntry[];
  versions: ProjectVersion[];
  busy: boolean;
  run: (action: () => Promise<unknown>, successMessage?: string) => Promise<void>;
}

function EntriesView({ projectId, kind, entries, versions, busy, run }: EntriesViewProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [query, setQuery] = useState("");
  const [newEntryOpen, setNewEntryOpen] = useState(false);
  const [archiveTarget, setArchiveTarget] = useState<DocEntry | null>(null);

  const visible = useMemo(
    () => entries.filter((e) => matches(query, e.title, e.description)),
    [entries, query],
  );

  function startEdit(entry: DocEntry) {
    setEditingId(entry.id);
    setTitle(entry.title);
    setDescription(entry.description);
  }

  const versionOptions = [
    { value: "", label: "Aucune version" },
    ...versions.map((v) => ({ value: v.id, label: v.label })),
  ];

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
          <button type="button" className="doc-tab__primary-btn" onClick={() => setNewEntryOpen(true)} disabled={busy}>
            <Plus size={13} strokeWidth={2} aria-hidden="true" />
            Nouvelle fiche
          </button>
        </div>
      </div>

      <div className="doc-tab__search">
        <Search size={13} strokeWidth={1.75} aria-hidden="true" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Rechercher une fiche…"
          aria-label="Rechercher une fiche"
        />
      </div>

      {entries.length === 0 && <p className="doc-tab__empty">Aucune fiche pour l'instant.</p>}
      {entries.length > 0 && visible.length === 0 && <p className="doc-tab__empty">Aucun résultat.</p>}

      {visible.map((entry) => (
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
              <label className="doc-tab__field">
                <span>Version</span>
                <Combobox
                  options={versionOptions}
                  value={entry.version_id ?? ""}
                  onChange={(value) =>
                    void run(
                      () => updateDocEntry(projectId, entry.id, { version_id: value || null }),
                      "Version mise à jour.",
                    )
                  }
                  clearable={false}
                />
              </label>
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
              <p className="doc-tab__timestamp">
                {entry.version_label && <span className="doc-tab__version-badge">{entry.version_label}</span>}
                Créée le {new Date(entry.created_at).toLocaleDateString("fr-FR")}
              </p>
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
                  onClick={() => setArchiveTarget(entry)}
                  disabled={busy}
                >
                  <Trash2 size={13} strokeWidth={1.75} aria-hidden="true" />
                </button>
              </div>
            </>
          )}
        </article>
      ))}

      {newEntryOpen && (
        <PromptDialog
          title={kind === "fonctionnalite" ? "Nouvelle fonctionnalité" : "Nouvelle résolution"}
          label="Titre"
          confirmLabel="Créer"
          onCancel={() => setNewEntryOpen(false)}
          onConfirm={(value) => {
            setNewEntryOpen(false);
            void run(() => createDocEntry(projectId, { kind, title: value }), "Fiche créée.");
          }}
        />
      )}

      {archiveTarget && (
        <ConfirmDialog
          title="Archiver cette fiche ?"
          confirmLabel="Archiver"
          danger
          onCancel={() => setArchiveTarget(null)}
          onConfirm={() => {
            const target = archiveTarget;
            setArchiveTarget(null);
            void run(() => archiveDocEntry(projectId, target.id), "Fiche archivée.");
          }}
        />
      )}
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
  const [ignoreTarget, setIgnoreTarget] = useState<DocumentationBundle["pending_features"][number] | null>(null);

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
                  onClick={() => setIgnoreTarget(item)}
                  disabled={busy}
                >
                  Ignorer
                </button>
              </div>
            </article>
          ))}
        </section>
      ))}

      {ignoreTarget && (
        <ConfirmDialog
          title="Ignorer cette entrée ?"
          confirmLabel="Ignorer"
          onCancel={() => setIgnoreTarget(null)}
          onConfirm={() => {
            const target = ignoreTarget;
            setIgnoreTarget(null);
            void run(() => ignorePendingDocEntry(projectId, target.id), "Entrée ignorée.");
          }}
        />
      )}
    </div>
  );
}

// --- Lien public --------------------------------------------------------

function LinkView({ projectId, bundle, busy, run }: PanelProps) {
  const { showToast } = useToast();
  const [copied, setCopied] = useState(false);
  const [slug, setSlug] = useState(bundle.space.custom_slug);
  const [rotateConfirmOpen, setRotateConfirmOpen] = useState(false);
  const [revokeConfirmOpen, setRevokeConfirmOpen] = useState(false);
  const { public_url: url } = bundle.space;

  useEffect(() => {
    setSlug(bundle.space.custom_slug);
  }, [bundle.space.custom_slug]);

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
          <label className="doc-tab__field">
            <span>
              Segment lisible de l'URL — le lien reste protégé par un suffixe aléatoire, changer ce
              segment régénère le lien (l'ancien cesse de fonctionner)
            </span>
            <div className="doc-tab__link-row">
              <input
                className="doc-tab__input"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                placeholder="mon-projet"
                disabled={busy}
              />
              <button
                type="button"
                className="doc-tab__ghost-btn"
                onClick={() => void run(() => setDocPublicSlug(projectId, slug), "Segment mis à jour.")}
                disabled={busy || slug === bundle.space.custom_slug}
              >
                Enregistrer
              </button>
            </div>
          </label>
          <div className="doc-tab__editor-actions">
            <button
              type="button"
              className="doc-tab__ghost-btn"
              onClick={() => setRotateConfirmOpen(true)}
              disabled={busy}
            >
              <RefreshCw size={13} strokeWidth={1.75} aria-hidden="true" />
              Régénérer
            </button>
            <button
              type="button"
              className="doc-tab__ghost-btn doc-tab__ghost-btn--danger"
              onClick={() => setRevokeConfirmOpen(true)}
              disabled={busy}
            >
              Révoquer
            </button>
          </div>

          {rotateConfirmOpen && (
            <ConfirmDialog
              title="Régénérer le lien ?"
              message="L'ancien lien cessera de fonctionner."
              confirmLabel="Régénérer"
              onCancel={() => setRotateConfirmOpen(false)}
              onConfirm={() => {
                setRotateConfirmOpen(false);
                void run(() => rotatePublicDocLink(projectId), "Nouveau lien généré.");
              }}
            />
          )}

          {revokeConfirmOpen && (
            <ConfirmDialog
              title="Révoquer le lien public ?"
              confirmLabel="Révoquer"
              danger
              onCancel={() => setRevokeConfirmOpen(false)}
              onConfirm={() => {
                setRevokeConfirmOpen(false);
                void run(() => revokePublicDocLink(projectId), "Lien révoqué.");
              }}
            />
          )}
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

// --- Contributeurs --------------------------------------------------------

interface ContributorsViewProps {
  projectId: string;
  entry: DocEntry | null;
  busy: boolean;
  run: (action: () => Promise<unknown>, successMessage?: string) => Promise<void>;
}

function ContributorsView({ projectId, entry, busy, run }: ContributorsViewProps) {
  const isManual = !!entry?.contributor_rows;
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState<ContributorRow[]>(entry?.contributor_rows ?? [{ name: "", role: "" }]);
  const [regenerateConfirmOpen, setRegenerateConfirmOpen] = useState(false);

  function startEdit() {
    setRows(entry?.contributor_rows && entry.contributor_rows.length > 0 ? entry.contributor_rows : [{ name: "", role: "" }]);
    setEditing(true);
  }

  function updateRow(index: number, field: keyof ContributorRow, value: string) {
    setRows((current) => current.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  }

  function addRow() {
    setRows((current) => [...current, { name: "", role: "" }]);
  }

  function removeRow(index: number) {
    setRows((current) => current.filter((_, i) => i !== index));
  }

  function handleGenerateClick() {
    if (isManual) {
      setRegenerateConfirmOpen(true);
      return;
    }
    void run(() => generateContributorsEntry(projectId), entry ? "Fiche actualisée." : "Fiche générée.");
  }

  async function handleSave() {
    const cleaned = rows.map((row) => ({ name: row.name.trim(), role: row.role.trim() })).filter((row) => row.name);
    if (cleaned.length === 0) return;
    await run(async () => {
      await updateContributorsEntry(projectId, cleaned);
      setEditing(false);
    }, "Contributeurs enregistrés.");
  }

  return (
    <div className="doc-tab__entries">
      <div className="doc-tab__list-head">
        <span>Contributeurs au projet</span>
        <div className="doc-tab__editor-actions">
          {!editing && (
            <button type="button" className="doc-tab__ghost-btn" onClick={startEdit} disabled={busy}>
              Personnaliser
            </button>
          )}
          <button type="button" className="doc-tab__primary-btn" onClick={handleGenerateClick} disabled={busy}>
            <RefreshCw size={13} strokeWidth={1.75} aria-hidden="true" />
            {entry ? "Actualiser" : "Générer"}
          </button>
        </div>
      </div>

      {regenerateConfirmOpen && (
        <ConfirmDialog
          title="Régénérer la fiche Contributeurs ?"
          message="Écrasera la liste personnalisée actuelle."
          confirmLabel="Régénérer"
          danger
          onCancel={() => setRegenerateConfirmOpen(false)}
          onConfirm={() => {
            setRegenerateConfirmOpen(false);
            void run(() => generateContributorsEntry(projectId), "Fiche actualisée.");
          }}
        />
      )}
      {!entry && !editing && (
        <p className="doc-tab__empty">
          Pas encore générée — liste les membres actifs du projet par rôle, à régénérer après tout
          changement d'équipe. Vous pouvez aussi personnaliser la liste à la main.
        </p>
      )}

      {editing ? (
        <div className="doc-tab__form">
          {rows.map((row, index) => (
            <div key={index} className="doc-tab__link-row">
              <input
                className="doc-tab__input"
                value={row.name}
                onChange={(e) => updateRow(index, "name", e.target.value)}
                placeholder="Nom"
                disabled={busy}
              />
              <input
                className="doc-tab__input"
                value={row.role}
                onChange={(e) => updateRow(index, "role", e.target.value)}
                placeholder="Rôle"
                disabled={busy}
              />
              <button
                type="button"
                className="doc-tab__icon-btn"
                onClick={() => removeRow(index)}
                disabled={busy}
                aria-label="Retirer ce contributeur"
              >
                <Trash2 size={13} strokeWidth={1.75} aria-hidden="true" />
              </button>
            </div>
          ))}
          <button type="button" className="doc-tab__ghost-btn" onClick={addRow} disabled={busy}>
            <Plus size={13} strokeWidth={2} aria-hidden="true" />
            Ajouter un contributeur
          </button>
          <div className="doc-tab__form-actions">
            <button type="button" className="doc-tab__ghost-btn" onClick={() => setEditing(false)} disabled={busy}>
              Annuler
            </button>
            <button type="button" className="doc-tab__primary-btn" onClick={handleSave} disabled={busy}>
              Enregistrer
            </button>
          </div>
        </div>
      ) : (
        entry && (
          <article className="doc-tab__card">
            <div className="doc-tab__card-head">
              <h4>{entry.title}</h4>
              <StatusDot status={entry.status} />
            </div>
            <p className="doc-tab__timestamp">
              {isManual ? "Personnalisée" : "Générée"} le {new Date(entry.updated_at).toLocaleString("fr-FR")}
            </p>
            <MarkdownView content={entry.description} />
            <div className="doc-tab__editor-actions">
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
            </div>
          </article>
        )
      )}
    </div>
  );
}

// --- Personnalisation -----------------------------------------------------

function AppearanceView({ projectId, bundle, busy, run }: PanelProps) {
  const { space } = bundle;
  const [accentColor, setAccentColor] = useState(space.accent_color);
  const [header, setHeader] = useState(space.header_content);
  const [footer, setFooter] = useState(space.footer_content);

  useEffect(() => {
    setAccentColor(space.accent_color);
    setHeader(space.header_content);
    setFooter(space.footer_content);
  }, [space.accent_color, space.header_content, space.footer_content]);

  const dirty = accentColor !== space.accent_color || header !== space.header_content || footer !== space.footer_content;

  return (
    <div className="doc-tab__form">
      <p className="doc-tab__link-hint">
        S'applique uniquement à la page publique — l'écran d'édition garde l'habillage Awtodo.
      </p>

      <label className="doc-tab__field">
        <span>Couleur d'accent</span>
        <div className="doc-tab__link-row">
          <input
            type="color"
            value={accentColor || "#753030"}
            onChange={(e) => setAccentColor(e.target.value)}
            disabled={busy}
            aria-label="Couleur d'accent de la documentation"
          />
          <button type="button" className="doc-tab__ghost-btn" onClick={() => setAccentColor("")} disabled={busy}>
            Par défaut
          </button>
        </div>
      </label>

      <label className="doc-tab__field">
        <span>En-tête (affiché en haut de la page publique)</span>
        <textarea
          className="doc-tab__textarea"
          value={header}
          onChange={(e) => setHeader(e.target.value)}
          rows={3}
          disabled={busy}
        />
      </label>

      <label className="doc-tab__field">
        <span>Pied de page</span>
        <textarea
          className="doc-tab__textarea"
          value={footer}
          onChange={(e) => setFooter(e.target.value)}
          rows={3}
          disabled={busy}
        />
      </label>

      <div className="doc-tab__form-actions">
        <button
          type="button"
          className="doc-tab__primary-btn"
          onClick={() =>
            run(
              () =>
                updateDocSpaceAppearance(projectId, {
                  accent_color: accentColor,
                  header_content: header,
                  footer_content: footer,
                }),
              "Personnalisation enregistrée.",
            )
          }
          disabled={busy || !dirty}
        >
          Enregistrer
        </button>
      </div>
    </div>
  );
}

function StatusDot({ status }: { status: DocEntry["status"] }) {
  const label = status === "publie" ? "Publié" : status === "brouillon" ? "Brouillon" : "Archivé";
  return <span className={`doc-tab__status doc-tab__status--${status}`}>{label}</span>;
}
