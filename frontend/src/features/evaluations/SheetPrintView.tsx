import { useEffect } from "react";
import { createPortal } from "react-dom";
import type { EvaluationClientResponse, EvaluationQuestion, EvaluationSheetDetail } from "../../types/watodo";
import { formatAnswer } from "./answerFormat";
import { visibleQuestionIds } from "./visibility";
import "./SheetPrintView.css";

const DATE_TIME = new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeStyle: "short" });

interface SheetPrintViewProps {
  sheet: EvaluationSheetDetail;
  projectName: string;
  /** Réponses à imprimer : un document chacune. Vide = l'évaluation chef de projet seule. */
  responses: EvaluationClientResponse[];
  onDone: () => void;
}

function AnswerList({ questions, answers }: { questions: EvaluationQuestion[]; answers: Record<string, unknown> }) {
  const typed = answers as EvaluationClientResponse["answers"];
  const visible = visibleQuestionIds(questions, typed);
  return (
    <dl>
      {questions
        .filter((question) => visible.has(question.id))
        .map((question) => (
          <div key={question.id}>
            <dt>{question.label}</dt>
            <dd>{formatAnswer(typed[question.id], question)}</dd>
          </div>
        ))}
    </dl>
  );
}

/** Export PDF par l'impression du navigateur : un document par réponse
 * client, suivi de la partie chef de projet. Monté le temps d'imprimer. */
export function SheetPrintView({ sheet, projectName, responses, onDone }: SheetPrintViewProps) {
  const clientQuestions = sheet.questions.filter((question) => question.section === "client" && question.status === "active");
  const internalQuestions = sheet.questions.filter((question) => question.section === "interne" && question.status === "active");

  useEffect(() => {
    const previousTitle = document.title;
    // Le nom de fichier proposé par le navigateur vient du titre de la page.
    document.title = `Évaluation – ${projectName} – ${sheet.title}`;
    document.body.classList.add("is-printing-evaluation");
    const finish = () => {
      document.title = previousTitle;
      document.body.classList.remove("is-printing-evaluation");
      onDone();
    };
    window.addEventListener("afterprint", finish, { once: true });
    const frame = requestAnimationFrame(() => window.print());
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("afterprint", finish);
      document.title = previousTitle;
      document.body.classList.remove("is-printing-evaluation");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const internal = (
    <section>
      <h3>Évaluation chef de projet</h3>
      {sheet.internal.updated_at ? (
        <>
          <p className="evaluation-print__meta">
            Renseignée par {sheet.internal.updated_by ?? "un chef de projet"} le {DATE_TIME.format(new Date(sheet.internal.updated_at))}
          </p>
          <AnswerList questions={internalQuestions} answers={sheet.internal.answers} />
        </>
      ) : (
        <p className="evaluation-print__meta">Non renseignée.</p>
      )}
    </section>
  );

  const header = (subtitle: string) => (
    <header>
      <p className="evaluation-print__project">{projectName}</p>
      <h2>{sheet.title}</h2>
      <p className="evaluation-print__meta">{subtitle}</p>
    </header>
  );

  return createPortal(
    <div className="evaluation-print" aria-hidden="true">
      {responses.length === 0 ? (
        <article className="evaluation-print__page">
          {header("Évaluation chef de projet")}
          {internal}
        </article>
      ) : (
        responses.map((response) => (
          <article key={response.id} className="evaluation-print__page">
            {header(`Répondant : ${response.respondent_name} · ${DATE_TIME.format(new Date(response.created_at))}`)}
            <section>
              <h3>Satisfaction client</h3>
              <AnswerList questions={clientQuestions} answers={response.answers} />
            </section>
            {internal}
          </article>
        ))
      )}
    </div>,
    document.body,
  );
}
