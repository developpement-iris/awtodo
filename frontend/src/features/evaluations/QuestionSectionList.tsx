import { Archive, ArrowDown, ArrowUp, Pencil, Plus, RotateCcw } from "lucide-react";
import { useState } from "react";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import type { EvaluationQuestion, EvaluationQuestionInput, EvaluationSection } from "../../types/watodo";
import { ANSWER_TYPE_LABELS, describeCondition } from "./answerFormat";
import { QuestionDefinitionForm } from "./QuestionDefinitionForm";
import "./QuestionSectionList.css";

interface QuestionSectionListProps {
  section: EvaluationSection;
  title: string;
  /** Questions actives de la partie, dans l'ordre. */
  questions: EvaluationQuestion[];
  /** Toutes les questions actives (les deux parties), pour décrire les conditions. */
  all: EvaluationQuestion[];
  /** Questions archivées affichables (catalogue). */
  archived?: EvaluationQuestion[];
  editable: (question: EvaluationQuestion) => boolean;
  canAdd: boolean;
  canReorder: boolean;
  lockTypeOnEdit?: boolean;
  onCreate: (input: EvaluationQuestionInput) => Promise<void>;
  onUpdate: (question: EvaluationQuestion, input: EvaluationQuestionInput) => Promise<void>;
  onArchive: (question: EvaluationQuestion) => Promise<void>;
  onRestore?: (question: EvaluationQuestion) => Promise<void>;
  onMove: (question: EvaluationQuestion, direction: "up" | "down") => Promise<void>;
  emptyLabel?: string;
}

/** Liste des questions d'une partie (catalogue ou fiche), avec édition en place. */
export function QuestionSectionList({
  section,
  title,
  questions,
  all,
  archived = [],
  editable,
  canAdd,
  canReorder,
  lockTypeOnEdit = false,
  onCreate,
  onUpdate,
  onArchive,
  onRestore,
  onMove,
  emptyLabel = "Aucune question.",
}: QuestionSectionListProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState<EvaluationQuestion | null>(null);
  const [busy, setBusy] = useState(false);

  async function guard(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="question-list">
      <h4 className="question-list__title">
        {title}
        <small>{questions.length}</small>
      </h4>
      {questions.length === 0 && !adding && <p className="question-list__empty">{emptyLabel}</p>}
      <ol className="question-list__items">
        {questions.map((question, index) => {
          const condition = describeCondition(question, all);
          if (editingId === question.id) {
            return (
              <li key={question.id}>
                <QuestionDefinitionForm
                  section={section}
                  siblings={all}
                  initial={question}
                  lockType={lockTypeOnEdit}
                  onCancel={() => setEditingId(null)}
                  onSubmit={async (input) => {
                    await onUpdate(question, input);
                    setEditingId(null);
                  }}
                />
              </li>
            );
          }
          return (
            <li key={question.id} className={`question-list__row${condition ? " question-list__row--conditional" : ""}`}>
              <div className="question-list__copy">
                <span className="question-list__label">
                  {question.label}
                  {question.required && <span className="question-list__required"> *</span>}
                </span>
                <span className="question-list__meta">
                  <span className="question-list__badge">{ANSWER_TYPE_LABELS[question.answer_type]}</span>
                  {question.is_generic && <span className="question-list__badge question-list__badge--generic">Générique</span>}
                  {condition && <span className="question-list__condition">{condition}</span>}
                </span>
              </div>
              <div className="question-list__actions">
                {canReorder && (
                  <>
                    <button
                      type="button"
                      onClick={() => void guard(() => onMove(question, "up"))}
                      disabled={busy || index === 0}
                      aria-label={`Monter ${question.label}`}
                      title="Monter"
                    >
                      <ArrowUp size={14} strokeWidth={1.75} aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      onClick={() => void guard(() => onMove(question, "down"))}
                      disabled={busy || index === questions.length - 1}
                      aria-label={`Descendre ${question.label}`}
                      title="Descendre"
                    >
                      <ArrowDown size={14} strokeWidth={1.75} aria-hidden="true" />
                    </button>
                  </>
                )}
                {editable(question) && (
                  <>
                    <button
                      type="button"
                      onClick={() => setEditingId(question.id)}
                      disabled={busy}
                      aria-label={`Modifier ${question.label}`}
                      title="Modifier"
                    >
                      <Pencil size={14} strokeWidth={1.75} aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmArchive(question)}
                      disabled={busy}
                      aria-label={`Retirer ${question.label}`}
                      title="Retirer"
                    >
                      <Archive size={14} strokeWidth={1.75} aria-hidden="true" />
                    </button>
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {adding ? (
        <QuestionDefinitionForm
          section={section}
          siblings={all}
          onCancel={() => setAdding(false)}
          onSubmit={async (input) => {
            await onCreate(input);
            setAdding(false);
          }}
        />
      ) : (
        canAdd && (
          <button type="button" className="question-list__add" onClick={() => setAdding(true)}>
            <Plus size={14} strokeWidth={1.75} aria-hidden="true" />
            Ajouter une question
          </button>
        )
      )}

      {archived.length > 0 && onRestore && (
        <ul className="question-list__archived">
          {archived.map((question) => (
            <li key={question.id}>
              <span>{question.label}</span>
              <button type="button" onClick={() => void guard(() => onRestore(question))} disabled={busy}>
                <RotateCcw size={13} strokeWidth={1.75} aria-hidden="true" />
                Restaurer
              </button>
            </li>
          ))}
        </ul>
      )}

      {confirmArchive && (
        <ConfirmDialog
          title="Retirer cette question ?"
          message={`« ${confirmArchive.label} » ne sera plus proposée. Les réponses déjà reçues sont conservées.`}
          confirmLabel="Retirer"
          danger
          onCancel={() => setConfirmArchive(null)}
          onConfirm={() => {
            const question = confirmArchive;
            setConfirmArchive(null);
            void guard(() => onArchive(question));
          }}
        />
      )}
    </section>
  );
}
