import { useEffect, useState } from "react";
import { EvaluationApiError, saveInternalEvaluation } from "../../api/client";
import { useToast } from "../../context/ToastContext";
import type { EvaluationAnswerValue, EvaluationSheetDetail } from "../../types/watodo";
import { AnswerField } from "./AnswerField";
import { formatAnswer } from "./answerFormat";
import { visibleQuestionIds } from "./visibility";

const DATE_TIME = new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeStyle: "short" });

interface InternalEvaluationFormProps {
  sheet: EvaluationSheetDetail;
  onChange: (sheet: EvaluationSheetDetail) => void;
}

/** Partie chef de projet : une seule par fiche, partagée par les chefs de projet. */
export function InternalEvaluationForm({ sheet, onChange }: InternalEvaluationFormProps) {
  const { showToast } = useToast();
  const [answers, setAnswers] = useState<Record<string, EvaluationAnswerValue>>(sheet.internal.answers);
  const [saving, setSaving] = useState(false);
  const [errorQuestion, setErrorQuestion] = useState<{ id: string | null; message: string } | null>(null);

  useEffect(() => {
    setAnswers(sheet.internal.answers);
  }, [sheet.id, sheet.internal.answers]);

  const questions = sheet.questions.filter((question) => question.section === "interne" && question.status === "active");
  const visible = visibleQuestionIds(questions, answers);
  const canEdit = sheet.permissions.can_manage && sheet.status !== "archivee";
  const dirty = JSON.stringify(answers) !== JSON.stringify(sheet.internal.answers);

  if (sheet.status === "brouillon") {
    return (
      <p className="evaluations-tab__muted">
        Ouvrez la fiche (onglet Questions) pour remplir l'évaluation : les questions doivent d'abord être figées.
      </p>
    );
  }

  if (questions.length === 0) {
    return <p className="evaluations-tab__muted">Cette fiche n'a pas de question chef de projet.</p>;
  }

  async function handleSave() {
    setSaving(true);
    setErrorQuestion(null);
    try {
      onChange(await saveInternalEvaluation(sheet.id, answers));
      showToast("Évaluation enregistrée.");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Enregistrement impossible.";
      setErrorQuestion({ id: err instanceof EvaluationApiError ? err.questionId : null, message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="internal-form">
      {sheet.internal.updated_at && (
        <p className="evaluations-tab__muted">
          Dernière mise à jour par {sheet.internal.updated_by ?? "un chef de projet"} le{" "}
          {DATE_TIME.format(new Date(sheet.internal.updated_at))}.
        </p>
      )}
      {!canEdit && !sheet.internal.updated_at && (
        <p className="evaluations-tab__muted">Les chefs de projet n'ont pas encore rempli cette partie.</p>
      )}

      {questions
        .filter((question) => visible.has(question.id))
        .map((question) =>
          canEdit ? (
            <AnswerField
              key={question.id}
              question={{ ...question, required: false }}
              value={answers[question.id]}
              onChange={(value) => setAnswers((current) => ({ ...current, [question.id]: value }))}
              error={errorQuestion?.id === question.id ? errorQuestion.message : undefined}
            />
          ) : (
            <div key={question.id} className="internal-form__read">
              <span>{question.label}</span>
              <p>{formatAnswer(sheet.internal.answers[question.id], question)}</p>
            </div>
          ),
        )}

      {errorQuestion && !errorQuestion.id && <p className="internal-form__error">{errorQuestion.message}</p>}

      {canEdit && (
        <div className="internal-form__actions">
          <span className="evaluations-tab__muted">Rien n'est imposé : enregistrez au fil de l'eau.</span>
          <button type="button" className="sheet-editor__primary" onClick={() => void handleSave()} disabled={saving || !dirty}>
            {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      )}
    </div>
  );
}
