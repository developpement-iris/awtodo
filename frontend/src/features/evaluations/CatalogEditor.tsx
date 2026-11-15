import { ChevronDown } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  archiveCatalogQuestion,
  createCatalogQuestion,
  getEvaluationCatalog,
  moveCatalogQuestion,
  restoreCatalogQuestion,
  updateCatalogQuestion,
  type EvaluationScope,
} from "../../api/client";
import { Checkbox } from "../../components/Checkbox";
import { useToast } from "../../context/ToastContext";
import type { EvaluationCatalog, EvaluationQuestion, EvaluationQuestionInput, EvaluationSection } from "../../types/watodo";
import { SECTION_LABELS } from "./answerFormat";
import { QuestionSectionList } from "./QuestionSectionList";
import "./CatalogEditor.css";

interface CatalogEditorProps {
  scope: EvaluationScope;
  /** Replié par défaut dans une carte de groupe, déplié dans un onglet. */
  collapsible?: boolean;
}

const SECTIONS: EvaluationSection[] = ["client", "interne"];

/** Questions génériques d'évaluation d'un groupe ou d'un projet sans groupe
 * (session du 2026-11-13). Droits calculés par le serveur (`can_manage`). */
export function CatalogEditor({ scope, collapsible = false }: CatalogEditorProps) {
  const { showToast } = useToast();
  const [open, setOpen] = useState(!collapsible);
  const [data, setData] = useState<EvaluationCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const scopeKey = "team" in scope ? `team:${scope.team}` : `project:${scope.project}`;

  const reload = useCallback(() => {
    getEvaluationCatalog(scope, true)
      .then((catalog) => {
        setData(catalog);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Impossible de charger les questions."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scopeKey]);

  useEffect(() => {
    if (open) reload();
  }, [open, reload]);

  async function act(action: () => Promise<unknown>, success?: string) {
    try {
      await action();
      reload();
      if (success) showToast(success);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Action impossible.");
    }
  }

  const active = data?.questions.filter((question) => question.status === "active") ?? [];
  const archived = data?.questions.filter((question) => question.status === "archived") ?? [];
  const canManage = data?.can_manage ?? false;

  const body = (
    <div className="catalog-editor__body">
      <p className="catalog-editor__hint">
        Ces questions sont copiées dans chaque nouvelle fiche d'évaluation. Les fiches déjà créées ne changent pas.
      </p>
      {error ? (
        <p className="catalog-editor__hint">{error}</p>
      ) : data === null ? (
        <p className="catalog-editor__hint">Chargement…</p>
      ) : (
        <>
          {SECTIONS.map((section) => (
            <QuestionSectionList
              key={section}
              section={section}
              title={SECTION_LABELS[section]}
              questions={active.filter((question) => question.section === section)}
              all={active}
              archived={showArchived ? archived.filter((question) => question.section === section) : []}
              editable={() => canManage}
              canAdd={canManage}
              canReorder={canManage}
              lockTypeOnEdit
              onCreate={async (input: EvaluationQuestionInput) => {
                await createCatalogQuestion(scope, input);
                reload();
                showToast("Question ajoutée.");
              }}
              onUpdate={async (question, input) => {
                // Le type d'une question du catalogue est figé : on ne le renvoie pas.
                const { answer_type: _answerType, section: _section, ...changes } = input;
                void _answerType;
                void _section;
                await updateCatalogQuestion(question.id, changes);
                reload();
                showToast("Question modifiée.");
              }}
              onArchive={(question: EvaluationQuestion) => act(() => archiveCatalogQuestion(question.id), "Question retirée.")}
              onRestore={(question) => act(() => restoreCatalogQuestion(question.id), "Question restaurée.")}
              onMove={(question, direction) => act(() => moveCatalogQuestion(question.id, direction))}
              emptyLabel="Aucune question dans cette partie."
            />
          ))}
          {canManage && archived.length > 0 && (
            <label className="catalog-editor__toggle">
              <Checkbox checked={showArchived} onCheckedChange={setShowArchived} aria-label="Afficher les questions retirées" />
              <span>Afficher les questions retirées ({archived.length})</span>
            </label>
          )}
        </>
      )}
    </div>
  );

  if (!collapsible) return <div className="catalog-editor">{body}</div>;

  return (
    <div className="catalog-editor catalog-editor--collapsible">
      <button type="button" className="catalog-editor__toggle-button" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        Questions d'évaluation
        <ChevronDown
          size={14}
          strokeWidth={1.75}
          className={`catalog-editor__chevron${open ? " catalog-editor__chevron--open" : ""}`}
          aria-hidden="true"
        />
      </button>
      {open && body}
    </div>
  );
}
