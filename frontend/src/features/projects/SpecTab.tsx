import { Document, HeadingLevel, Packer, Paragraph } from "docx";
import { FileDown, Pencil } from "lucide-react";
import { useEffect, useState } from "react";
import { getSpecSections, updateSpecSection } from "../../api/client";
import { Checkbox } from "../../components/Checkbox";
import { MarkdownView } from "../../components/MarkdownView";
import { SkeletonRows } from "../../components/Skeleton";
import { useToast } from "../../context/ToastContext";
import type { Project, SpecSection, SpecSectionKey } from "../../types/watodo";
import "./SpecTab.css";

// Nom de fichier sûr sur tous les OS (Windows interdit notamment : / \ : * ? " < > |).
function sanitizeFilename(value: string): string {
  return value.replace(/[/\\:*?"<>|]/g, "-").trim();
}

// Génération 100% navigateur (bibliothèque `docx`, aucun changement backend)
// — l'objectif explicite est un fichier réellement rééditable dans Word, pas
// un rendu soigné : un `Document` avec un titre par section active suffit,
// la mise en forme fine reste à la charge de l'utilisateur dans Word.
async function exportSpecToDocx(project: Project, sections: SpecSection[]) {
  const activeSections = sections.filter((section) => section.is_active);
  const children: Paragraph[] = [];

  for (const section of activeSections) {
    children.push(new Paragraph({ text: section.label, heading: HeadingLevel.HEADING_1 }));
    const lines = section.content ? section.content.split("\n") : [""];
    for (const line of lines) {
      children.push(new Paragraph({ text: line }));
    }
  }

  const doc = new Document({ sections: [{ children }] });
  const blob = await Packer.toBlob(doc);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${sanitizeFilename(project.name)} — Cahier des charges.docx`;
  link.click();
  URL.revokeObjectURL(url);
}

interface SpecTabProps {
  project: Project;
}

interface SpecSectionBlockProps {
  section: SpecSection;
  canEdit: boolean;
  isEditing: boolean;
  draft: string;
  saving: boolean;
  onEditStart: () => void;
  onDraftChange: (value: string) => void;
  onSave: () => void;
  onCancel: () => void;
}

function SpecSectionBlock({
  section,
  canEdit,
  isEditing,
  draft,
  saving,
  onEditStart,
  onDraftChange,
  onSave,
  onCancel,
}: SpecSectionBlockProps) {
  return (
    <div className="spec-tab__block">
      <div className="spec-tab__block-header">
        <h3>{section.label}</h3>
        {!isEditing && canEdit && (
          <button type="button" className="spec-tab__block-edit" onClick={onEditStart}>
            <Pencil size={13} strokeWidth={1.75} aria-hidden="true" />
            Modifier
          </button>
        )}
      </div>
      {isEditing ? (
        <div className="spec-tab__block-editor">
          <textarea
            className="spec-tab__block-textarea"
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            rows={6}
            autoFocus
            disabled={saving}
          />
          <div className="spec-tab__block-actions">
            <button type="button" className="spec-tab__block-cancel" onClick={onCancel} disabled={saving}>
              Annuler
            </button>
            <button type="button" className="spec-tab__block-save" onClick={onSave} disabled={saving}>
              {saving ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        </div>
      ) : section.content ? (
        <MarkdownView content={section.content} />
      ) : (
        <p className="spec-tab__block-empty">Vide pour l'instant.</p>
      )}
    </div>
  );
}

export function SpecTab({ project }: SpecTabProps) {
  const { showToast } = useToast();
  const [sections, setSections] = useState<SpecSection[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingKey, setPendingKey] = useState<SpecSectionKey | null>(null);
  const [editingKey, setEditingKey] = useState<SpecSectionKey | null>(null);
  const [draft, setDraft] = useState("");
  const [exporting, setExporting] = useState(false);

  const canEdit = project.permissions.can_edit_spec;

  useEffect(() => {
    let cancelled = false;
    getSpecSections(project.id)
      .then((data) => {
        if (!cancelled) setSections(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Le chargement a échoué.");
      });
    return () => {
      cancelled = true;
    };
  }, [project.id]);

  function applyUpdate(updated: SpecSection) {
    setSections((current) =>
      (current ?? []).map((section) => (section.section_key === updated.section_key ? updated : section)),
    );
  }

  async function handleToggle(key: SpecSectionKey, nextActive: boolean) {
    setPendingKey(key);
    setError(null);
    try {
      applyUpdate(await updateSpecSection(project.id, key, { is_active: nextActive }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "La mise à jour a échoué.");
    } finally {
      setPendingKey(null);
    }
  }

  function handleEditStart(section: SpecSection) {
    setEditingKey(section.section_key);
    setDraft(section.content);
  }

  function handleEditCancel() {
    setEditingKey(null);
    setDraft("");
  }

  async function handleEditSave(key: SpecSectionKey) {
    setPendingKey(key);
    setError(null);
    try {
      applyUpdate(await updateSpecSection(project.id, key, { content: draft }));
      setEditingKey(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'enregistrement a échoué.");
    } finally {
      setPendingKey(null);
    }
  }

  const activeSections = (sections ?? []).filter((section) => section.is_active);

  async function handleExport() {
    setExporting(true);
    setError(null);
    try {
      await exportSpecToDocx(project, activeSections);
      showToast("Cahier des charges exporté.");
    } catch {
      setError("L'export a échoué.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="spec-tab">
      <div className="spec-tab__toolbar">
        <button
          type="button"
          className="spec-tab__export"
          onClick={handleExport}
          disabled={exporting || activeSections.length === 0}
        >
          <FileDown size={14} strokeWidth={1.75} aria-hidden="true" />
          {exporting ? "Export…" : "Exporter en .docx"}
        </button>
      </div>

      {error && <p className="spec-tab__message spec-tab__message--error">{error}</p>}

      <div className="spec-tab__layout">
        <nav className="spec-tab__summary" aria-label="Sommaire du cahier des charges">
          <h3 className="spec-tab__summary-title">Sommaire</h3>
          {sections === null ? (
            <SkeletonRows rows={6} />
          ) : (
            <ul className="spec-tab__summary-list">
              {sections.map((section) => (
                <li key={section.section_key}>
                  <label className="spec-tab__summary-item">
                    <Checkbox
                      checked={section.is_active}
                      disabled={!canEdit || pendingKey === section.section_key}
                      onCheckedChange={(checked) => handleToggle(section.section_key, checked)}
                      aria-label={section.label}
                    />
                    {section.label}
                  </label>
                </li>
              ))}
            </ul>
          )}
        </nav>

        <div className="spec-tab__notebook">
          {sections === null ? (
            <SkeletonRows rows={8} />
          ) : activeSections.length === 0 ? (
            <p className="spec-tab__message">
              Cochez une ou plusieurs sections dans le sommaire pour commencer le cahier des charges.
            </p>
          ) : (
            activeSections.map((section) => (
              <SpecSectionBlock
                key={section.section_key}
                section={section}
                canEdit={canEdit}
                isEditing={editingKey === section.section_key}
                draft={draft}
                saving={pendingKey === section.section_key}
                onEditStart={() => handleEditStart(section)}
                onDraftChange={setDraft}
                onSave={() => handleEditSave(section.section_key)}
                onCancel={handleEditCancel}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
