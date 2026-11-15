import { CheckCircle2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { EvaluationApiError, getPublicEvaluation, submitPublicEvaluation } from "../../api/client";
import type { EvaluationAnswerValue, PublicEvaluation } from "../../types/watodo";
import { AnswerField } from "./AnswerField";
import { isEmptyAnswer } from "./answerFormat";
import { visibleQuestionIds } from "./visibility";
import "./PublicEvaluationPage.css";

type State =
  | { kind: "loading" }
  | { kind: "invalid" }
  | { kind: "closed"; title?: string }
  | { kind: "error"; message: string }
  | { kind: "form"; evaluation: PublicEvaluation }
  | { kind: "done"; message: string };

const CLOSED_MESSAGE = "Ce questionnaire est clos. Merci de votre intérêt.";
const NAME_ERROR_KEY = "__name__";

interface PublicEvaluationPageProps {
  token: string;
}

/** Formulaire client d'une fiche d'évaluation, sans compte (2ᵉ exception au
 * garde-fou « connexion obligatoire », voir CLAUDE.md). Aucun appel authentifié. */
export function PublicEvaluationPage({ token }: PublicEvaluationPageProps) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [name, setName] = useState("");
  const [answers, setAnswers] = useState<Record<string, EvaluationAnswerValue>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    let cancelled = false;
    getPublicEvaluation(token)
      .then((evaluation) => {
        if (cancelled) return;
        document.title = evaluation.title;
        setState(evaluation.closed ? { kind: "closed", title: evaluation.title } : { kind: "form", evaluation });
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof EvaluationApiError && err.status === 404) setState({ kind: "invalid" });
        else setState({ kind: "error", message: "Le questionnaire ne peut pas être chargé pour le moment. Réessayez plus tard." });
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const questions = useMemo(() => (state.kind === "form" ? state.evaluation.questions ?? [] : []), [state]);
  const visible = visibleQuestionIds(questions, answers);

  function focusFirstError(keys: string[]) {
    requestAnimationFrame(() => {
      const first = keys[0];
      const target =
        first === NAME_ERROR_KEY
          ? formRef.current?.querySelector<HTMLElement>("#evaluation-name")
          : formRef.current?.querySelector<HTMLElement>(`[data-question-id="${first}"]`);
      target?.scrollIntoView({ behavior: "smooth", block: "center" });
      (target?.matches("input") ? target : target?.querySelector<HTMLElement>("input, textarea, button"))?.focus();
    });
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (state.kind !== "form") return;
    const nextErrors: Record<string, string> = {};
    if (!name.trim()) nextErrors[NAME_ERROR_KEY] = "Indiquez votre nom.";
    for (const question of questions) {
      if (question.required && visible.has(question.id) && isEmptyAnswer(answers[question.id])) {
        nextErrors[question.id] = "Cette question est obligatoire.";
      }
    }
    setErrors(nextErrors);
    setSubmitError(null);
    if (Object.keys(nextErrors).length > 0) {
      focusFirstError(Object.keys(nextErrors));
      return;
    }
    // Une question masquée garde sa saisie à l'écran, mais n'est pas envoyée.
    const payload = Object.fromEntries(
      Object.entries(answers).filter(([id, value]) => visible.has(id) && !isEmptyAnswer(value)),
    );
    setSubmitting(true);
    try {
      const result = await submitPublicEvaluation(token, name.trim(), payload);
      setState({ kind: "done", message: result.detail });
      window.scrollTo({ top: 0 });
    } catch (err) {
      if (err instanceof EvaluationApiError) {
        if (err.status === 410) setState({ kind: "closed", title: state.evaluation.title });
        else if (err.status === 404) setState({ kind: "invalid" });
        else if (err.status === 429) setSubmitError("Trop d'envois depuis cette connexion, réessayez dans une heure.");
        else if (err.questionId) {
          setErrors({ [err.questionId]: err.message });
          focusFirstError([err.questionId]);
        } else setSubmitError(err.message);
      } else {
        setSubmitError("L'envoi a échoué. Vérifiez votre connexion et réessayez.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="public-evaluation">
      <main className="public-evaluation__column">
        {state.kind === "loading" && <p className="public-evaluation__muted">Chargement du questionnaire…</p>}
        {state.kind === "invalid" && (
          <div className="public-evaluation__notice">
            <h1>Lien invalide</h1>
            <p>Ce lien n'est pas ou plus valide. Demandez un nouveau lien à votre interlocuteur.</p>
          </div>
        )}
        {state.kind === "error" && (
          <div className="public-evaluation__notice">
            <h1>Questionnaire indisponible</h1>
            <p>{state.message}</p>
          </div>
        )}
        {state.kind === "closed" && (
          <div className="public-evaluation__notice">
            {state.title && <h1>{state.title}</h1>}
            <p>{CLOSED_MESSAGE}</p>
          </div>
        )}
        {state.kind === "done" && (
          <div className="public-evaluation__notice public-evaluation__notice--done">
            <CheckCircle2 size={32} strokeWidth={1.75} aria-hidden="true" />
            <h1>Merci</h1>
            <p>{state.message}</p>
          </div>
        )}
        {state.kind === "form" && (
          <>
            <header className="public-evaluation__header">
              <p className="public-evaluation__project">{state.evaluation.project_name}</p>
              <h1>{state.evaluation.title}</h1>
              {state.evaluation.client_intro && <p className="public-evaluation__intro">{state.evaluation.client_intro}</p>}
            </header>
            <form ref={formRef} className="public-evaluation__form" onSubmit={handleSubmit} noValidate>
              <div className={`public-evaluation__name${errors[NAME_ERROR_KEY] ? " has-error" : ""}`}>
                <label htmlFor="evaluation-name">
                  Votre nom <span aria-label="obligatoire">*</span>
                </label>
                <input
                  id="evaluation-name"
                  type="text"
                  value={name}
                  maxLength={150}
                  autoComplete="name"
                  aria-invalid={Boolean(errors[NAME_ERROR_KEY])}
                  aria-describedby={errors[NAME_ERROR_KEY] ? "evaluation-name-error" : undefined}
                  onChange={(event) => setName(event.target.value)}
                />
                {errors[NAME_ERROR_KEY] && (
                  <span id="evaluation-name-error" role="alert">
                    {errors[NAME_ERROR_KEY]}
                  </span>
                )}
              </div>

              {questions
                .filter((question) => visible.has(question.id))
                .map((question) => (
                  <AnswerField
                    key={question.id}
                    question={question}
                    value={answers[question.id]}
                    error={errors[question.id]}
                    onChange={(value) => {
                      setAnswers((current) => ({ ...current, [question.id]: value }));
                      if (errors[question.id]) {
                        setErrors((current) => {
                          const next = { ...current };
                          delete next[question.id];
                          return next;
                        });
                      }
                    }}
                  />
                ))}

              {submitError && (
                <p className="public-evaluation__submit-error" role="alert">
                  {submitError}
                </p>
              )}
              <button type="submit" className="public-evaluation__submit" disabled={submitting}>
                {submitting ? "Envoi en cours…" : "Envoyer mes réponses"}
              </button>
            </form>
          </>
        )}
      </main>
      <footer className="public-evaluation__footer">Propulsé par Awtodo</footer>
    </div>
  );
}
