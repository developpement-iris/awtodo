import { Plus, X } from "lucide-react";
import { useState } from "react";
import { Checkbox } from "../../components/Checkbox";
import { Combobox } from "../../components/Combobox";
import type {
  EvaluationAnswerType,
  EvaluationQuestion,
  EvaluationQuestionInput,
  EvaluationSection,
} from "../../types/watodo";
import { ANSWER_TYPE_LABELS, CHOICE_TYPES, CONDITIONABLE_TYPES, conditionChoices } from "./answerFormat";
import "./QuestionDefinitionForm.css";

interface QuestionDefinitionFormProps {
  section: EvaluationSection;
  /** Questions actives de la même portée (catalogue ou fiche), pour les conditions. */
  siblings: EvaluationQuestion[];
  initial?: EvaluationQuestion;
  /** Type figé (question du catalogue déjà créée). */
  lockType?: boolean;
  onSubmit: (input: EvaluationQuestionInput) => Promise<void>;
  onCancel: () => void;
}

const TYPE_OPTIONS = (Object.keys(ANSWER_TYPE_LABELS) as EvaluationAnswerType[]).map((value) => ({
  value,
  label: ANSWER_TYPE_LABELS[value],
}));

/** Création ou modification d'une question (catalogue d'un groupe ou fiche). */
export function QuestionDefinitionForm({
  section,
  siblings,
  initial,
  lockType = false,
  onSubmit,
  onCancel,
}: QuestionDefinitionFormProps) {
  const [label, setLabel] = useState(initial?.label ?? "");
  const [helpText, setHelpText] = useState(initial?.help_text ?? "");
  const [answerType, setAnswerType] = useState<EvaluationAnswerType>(initial?.answer_type ?? "note_5");
  const [options, setOptions] = useState<string[]>(initial?.options.length ? initial.options : ["", ""]);
  const [required, setRequired] = useState(initial?.required ?? false);
  const [conditionOn, setConditionOn] = useState(initial?.condition_on ?? "");
  const [conditionValues, setConditionValues] = useState<string[]>(initial?.condition_values ?? []);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isChoice = CHOICE_TYPES.includes(answerType);
  const targets = siblings.filter(
    (candidate) =>
      candidate.section === section &&
      candidate.id !== initial?.id &&
      candidate.status === "active" &&
      CONDITIONABLE_TYPES.includes(candidate.answer_type),
  );
  const target = targets.find((candidate) => candidate.id === conditionOn);

  function validate(): string | null {
    if (!label.trim()) return "Le libellé est obligatoire.";
    if (isChoice) {
      const cleaned = options.map((option) => option.trim()).filter(Boolean);
      if (cleaned.length < 2) return "Indiquez au moins deux options.";
      if (new Set(cleaned.map((option) => option.toLowerCase())).size !== cleaned.length) {
        return "Deux options sont identiques.";
      }
    }
    if (conditionOn && conditionValues.length === 0) return "Cochez au moins une réponse pour la condition.";
    return null;
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const problem = validate();
    if (problem) {
      setError(problem);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        section,
        label: label.trim(),
        help_text: helpText.trim(),
        answer_type: answerType,
        options: isChoice ? options.map((option) => option.trim()).filter(Boolean) : [],
        required,
        condition_on: conditionOn || null,
        condition_values: conditionOn ? conditionValues : [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enregistrement impossible.");
      setSubmitting(false);
    }
  }

  return (
    <form className="question-form" onSubmit={handleSubmit}>
      <label className="question-form__field">
        <span>Libellé</span>
        <input type="text" value={label} maxLength={300} onChange={(event) => setLabel(event.target.value)} autoFocus />
      </label>

      <label className="question-form__field">
        <span>Aide (facultative)</span>
        <input type="text" value={helpText} maxLength={500} onChange={(event) => setHelpText(event.target.value)} />
      </label>

      <div className="question-form__row">
        <label className="question-form__field">
          <span>Type de réponse</span>
          <Combobox
            options={TYPE_OPTIONS}
            value={answerType}
            onChange={(value) => setAnswerType(value as EvaluationAnswerType)}
            clearable={false}
            disabled={lockType}
          />
        </label>
        <label className="question-form__inline">
          <Checkbox checked={required} onCheckedChange={setRequired} aria-label="Réponse obligatoire" />
          <span>Réponse obligatoire</span>
        </label>
      </div>
      {lockType && (
        <p className="question-form__hint">Le type de réponse ne change plus après la création, pour garder des statistiques comparables.</p>
      )}

      {isChoice && (
        <fieldset className="question-form__options">
          <legend>Options</legend>
          {options.map((option, index) => (
            <div key={index} className="question-form__option">
              <input
                type="text"
                value={option}
                maxLength={150}
                aria-label={`Option ${index + 1}`}
                onChange={(event) =>
                  setOptions((current) => current.map((value, i) => (i === index ? event.target.value : value)))
                }
              />
              <button
                type="button"
                onClick={() => setOptions((current) => current.filter((_, i) => i !== index))}
                disabled={options.length <= 2}
                aria-label={`Retirer l'option ${index + 1}`}
              >
                <X size={14} strokeWidth={1.75} aria-hidden="true" />
              </button>
            </div>
          ))}
          <button type="button" className="question-form__add" onClick={() => setOptions((current) => [...current, ""])}>
            <Plus size={14} strokeWidth={1.75} aria-hidden="true" />
            Ajouter une option
          </button>
        </fieldset>
      )}

      <fieldset className="question-form__condition">
        <legend>Afficher seulement si…</legend>
        {targets.length === 0 ? (
          <p className="question-form__hint">
            Aucune question Oui / Non ou à choix unique dans cette partie : la question est toujours affichée.
          </p>
        ) : (
          <>
            <Combobox
              options={[
                { value: "", label: "Aucune condition (toujours affichée)" },
                ...targets.map((candidate) => ({ value: candidate.id, label: candidate.label })),
              ]}
              value={conditionOn}
              onChange={(value) => {
                setConditionOn(value);
                setConditionValues([]);
              }}
              placeholder="Aucune condition (toujours affichée)"
            />
            {target && (
              <div className="question-form__values">
                <span>La réponse à « {target.label} » est :</span>
                {conditionChoices(target).map((choice) => (
                  <label key={choice.value} className="question-form__inline">
                    <Checkbox
                      checked={conditionValues.includes(choice.value)}
                      aria-label={choice.label}
                      onCheckedChange={(checked) =>
                        setConditionValues((current) =>
                          checked ? [...current, choice.value] : current.filter((value) => value !== choice.value),
                        )
                      }
                    />
                    <span>{choice.label}</span>
                  </label>
                ))}
              </div>
            )}
          </>
        )}
      </fieldset>

      {error && (
        <p className="question-form__error" role="alert">
          {error}
        </p>
      )}

      <div className="question-form__actions">
        <button type="button" className="question-form__cancel" onClick={onCancel} disabled={submitting}>
          Annuler
        </button>
        <button type="submit" className="question-form__save" disabled={submitting}>
          {submitting ? "Enregistrement…" : initial ? "Enregistrer" : "Ajouter la question"}
        </button>
      </div>
    </form>
  );
}
