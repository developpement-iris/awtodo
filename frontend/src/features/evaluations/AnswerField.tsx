import { useId } from "react";
import { Checkbox } from "../../components/Checkbox";
import { Combobox } from "../../components/Combobox";
import type { EvaluationAnswerValue, EvaluationQuestion } from "../../types/watodo";
import "./AnswerField.css";

const LONG_TEXT_LIMIT = 5000;
const SHORT_TEXT_LIMIT = 200;
const COUNTER_FROM = 4500;
const COMBOBOX_FROM = 8;

interface AnswerFieldProps {
  question: Pick<EvaluationQuestion, "id" | "label" | "help_text" | "answer_type" | "options" | "required">;
  value: EvaluationAnswerValue | undefined;
  onChange: (value: EvaluationAnswerValue) => void;
  error?: string;
  disabled?: boolean;
}

function Scale({
  from,
  to,
  value,
  onChange,
  required,
  disabled,
  lowLabel,
  highLabel,
  labelledBy,
}: {
  from: number;
  to: number;
  value: EvaluationAnswerValue | undefined;
  onChange: (value: EvaluationAnswerValue) => void;
  required: boolean;
  disabled?: boolean;
  lowLabel: string;
  highLabel: string;
  labelledBy: string;
}) {
  const steps = Array.from({ length: to - from + 1 }, (_, index) => from + index);
  return (
    <div className="answer-field__scale">
      <div className="answer-field__pills" role="radiogroup" aria-labelledby={labelledBy}>
        {steps.map((step) => {
          const selected = value === step;
          return (
            <button
              key={step}
              type="button"
              role="radio"
              aria-checked={selected}
              className={`answer-field__pill${selected ? " is-selected" : ""}`}
              disabled={disabled}
              // Recliquer efface la réponse, sauf pour une question obligatoire.
              onClick={() => onChange(selected && !required ? null : step)}
            >
              {step}
            </button>
          );
        })}
      </div>
      <div className="answer-field__scale-labels" aria-hidden="true">
        <span>{lowLabel}</span>
        <span>{highLabel}</span>
      </div>
    </div>
  );
}

/** Saisie d'une réponse selon le type de la question (page publique, partie
 * chef de projet, aperçu). Aucun `<select>` natif. */
export function AnswerField({ question, value, onChange, error, disabled }: AnswerFieldProps) {
  const baseId = useId();
  const labelId = `${baseId}-label`;
  const helpId = `${baseId}-help`;
  const errorId = `${baseId}-error`;
  const describedBy = [question.help_text ? helpId : "", error ? errorId : ""].filter(Boolean).join(" ") || undefined;
  const text = typeof value === "string" ? value : "";

  function renderInput() {
    switch (question.answer_type) {
      case "note_5":
        return (
          <Scale
            from={1}
            to={5}
            value={value}
            onChange={onChange}
            required={question.required}
            disabled={disabled}
            lowLabel="Pas du tout"
            highLabel="Tout à fait"
            labelledBy={labelId}
          />
        );
      case "nps_10":
        return (
          <Scale
            from={0}
            to={10}
            value={value}
            onChange={onChange}
            required={question.required}
            disabled={disabled}
            lowLabel="Peu probable"
            highLabel="Très probable"
            labelledBy={labelId}
          />
        );
      case "oui_non":
        return (
          <div className="answer-field__segmented" role="radiogroup" aria-labelledby={labelId}>
            {[
              { value: "oui", label: "Oui" },
              { value: "non", label: "Non" },
            ].map((option) => {
              const selected = value === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  className={selected ? "is-selected" : undefined}
                  disabled={disabled}
                  onClick={() => onChange(selected && !question.required ? null : option.value)}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        );
      case "choix_unique":
        if (question.options.length >= COMBOBOX_FROM) {
          return (
            <Combobox
              options={question.options.map((option) => ({ value: option, label: option }))}
              value={text}
              onChange={(next) => onChange(next || null)}
              placeholder="Choisir une réponse"
              disabled={disabled}
              clearable={!question.required}
              searchable
            />
          );
        }
        return (
          <div className="answer-field__options" role="radiogroup" aria-labelledby={labelId}>
            {question.options.map((option) => {
              const selected = value === option;
              return (
                <button
                  key={option}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  className={`answer-field__option${selected ? " is-selected" : ""}`}
                  disabled={disabled}
                  onClick={() => onChange(selected && !question.required ? null : option)}
                >
                  <span className="answer-field__radio" aria-hidden="true" />
                  {option}
                </button>
              );
            })}
          </div>
        );
      case "choix_multiple": {
        const chosen = Array.isArray(value) ? value : [];
        return (
          <div className="answer-field__options" role="group" aria-labelledby={labelId}>
            {question.options.map((option) => (
              <label key={option} className="answer-field__check">
                <Checkbox
                  checked={chosen.includes(option)}
                  disabled={disabled}
                  aria-label={option}
                  onCheckedChange={(checked) => {
                    const next = checked
                      ? question.options.filter((candidate) => candidate === option || chosen.includes(candidate))
                      : chosen.filter((candidate) => candidate !== option);
                    onChange(next.length ? next : null);
                  }}
                />
                <span>{option}</span>
              </label>
            ))}
          </div>
        );
      }
      case "texte_court":
        return (
          <input
            type="text"
            className="answer-field__text"
            value={text}
            maxLength={SHORT_TEXT_LIMIT}
            disabled={disabled}
            aria-labelledby={labelId}
            aria-describedby={describedBy}
            aria-invalid={Boolean(error)}
            onChange={(event) => onChange(event.target.value)}
          />
        );
      case "texte_long":
        return (
          <>
            <textarea
              className="answer-field__text"
              rows={4}
              value={text}
              maxLength={LONG_TEXT_LIMIT}
              disabled={disabled}
              aria-labelledby={labelId}
              aria-describedby={describedBy}
              aria-invalid={Boolean(error)}
              onChange={(event) => onChange(event.target.value)}
            />
            {text.length > COUNTER_FROM && (
              <span className="answer-field__counter">
                {text.length} / {LONG_TEXT_LIMIT}
              </span>
            )}
          </>
        );
    }
  }

  return (
    <div className={`answer-field${error ? " answer-field--error" : ""}`} data-question-id={question.id}>
      <span id={labelId} className="answer-field__label">
        {question.label}
        {question.required && (
          <span className="answer-field__required" aria-label="obligatoire">
            {" "}
            *
          </span>
        )}
      </span>
      {question.help_text && (
        <span id={helpId} className="answer-field__help">
          {question.help_text}
        </span>
      )}
      {renderInput()}
      {error && (
        <span id={errorId} className="answer-field__error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
