import { ChevronDown, Download, FileText, MessageSquareText, Printer } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  downloadEvaluationExport,
  getEvaluationResponses,
  getEvaluationResults,
  setEvaluationResponseStatus,
} from "../../api/client";
import { BarChart } from "../../components/BarChart";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DonutChart } from "../../components/DonutChart";
import { StatCard } from "../../components/StatCard";
import { useToast } from "../../context/ToastContext";
import type {
  EvaluationClientResponse,
  EvaluationQuestion,
  EvaluationResults,
  EvaluationSheetDetail,
  EvaluationSummary,
} from "../../types/watodo";
import { formatAnswer } from "./answerFormat";
import { SheetPrintView } from "./SheetPrintView";
import { visibleQuestionIds } from "./visibility";
import "./SheetResults.css";

const DATE_TIME = new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" });
const ACCENT = "var(--color-accent)";
const ACCENT_SOFT = "color-mix(in srgb, var(--color-accent) 45%, var(--color-surface))";
const NEUTRAL = "var(--color-text-faint)";
const TEXT_PREVIEW = 5;

function decimal(value: number, digits = 1): string {
  return value.toFixed(digits).replace(".", ",");
}

function SummaryCard({ question, summary }: { question: EvaluationQuestion; summary: EvaluationSummary }) {
  const [allTexts, setAllTexts] = useState(false);
  let content: React.ReactNode;
  if (summary.count === 0) {
    content = <p className="sheet-results__none">Aucune réponse.</p>;
  } else if (summary.kind === "note") {
    content = (
      <>
        <p className="sheet-results__figure">
          {decimal(summary.average ?? 0)} <small>/ 5</small>
        </p>
        <BarChart data={["1", "2", "3", "4", "5"].map((key) => ({ label: key, value: summary.distribution[key] ?? 0 }))} height={110} />
      </>
    );
  } else if (summary.kind === "nps") {
    content = (
      <div className="sheet-results__donut">
        <DonutChart
          slices={[
            { label: "Promoteurs (9-10)", value: summary.promoters, color: ACCENT },
            { label: "Passifs (7-8)", value: summary.passives, color: ACCENT_SOFT },
            { label: "Détracteurs (0-6)", value: summary.detractors, color: NEUTRAL },
          ]}
          centerLabel="NPS"
          centerValue={`${(summary.score ?? 0) > 0 ? "+" : ""}${summary.score ?? 0}`}
          size={130}
        />
      </div>
    );
  } else if (summary.kind === "yes_no") {
    content = (
      <div className="sheet-results__donut">
        <DonutChart
          slices={[
            { label: "Oui", value: summary.yes, color: ACCENT },
            { label: "Non", value: summary.no, color: NEUTRAL },
          ]}
          centerLabel="Oui"
          centerValue={`${Math.round((summary.yes_rate ?? 0) * 100)} %`}
          size={130}
        />
      </div>
    );
  } else if (summary.kind === "choices") {
    content = <BarChart data={Object.entries(summary.counts).map(([label, value]) => ({ label, value }))} height={120} />;
  } else {
    const shown = allTexts ? summary.values : summary.values.slice(0, TEXT_PREVIEW);
    content = (
      <>
        <ul className="sheet-results__texts">
          {shown.map((value, index) => (
            <li key={index}>{value}</li>
          ))}
        </ul>
        {summary.values.length > TEXT_PREVIEW && (
          <button type="button" className="sheet-results__link" onClick={() => setAllTexts((value) => !value)}>
            {allTexts ? "Voir moins" : `Voir les ${summary.values.length} réponses`}
          </button>
        )}
      </>
    );
  }
  return (
    <article className="sheet-results__card">
      <header>
        <h5>{question.label}</h5>
        <span>
          {summary.count} réponse{summary.count > 1 ? "s" : ""}
        </span>
      </header>
      {content}
    </article>
  );
}

interface SheetResultsProps {
  sheet: EvaluationSheetDetail;
  projectName: string;
  onChanged: () => void;
  onGoToInternal: () => void;
}

export function SheetResults({ sheet, projectName, onChanged, onGoToInternal }: SheetResultsProps) {
  const { showToast } = useToast();
  const [results, setResults] = useState<EvaluationResults | null>(null);
  const [responses, setResponses] = useState<EvaluationClientResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ response: EvaluationClientResponse; action: "discard" | "restore" } | null>(null);
  const [printing, setPrinting] = useState<EvaluationClientResponse[] | null>(null);
  const canManage = sheet.permissions.can_manage;

  const load = useCallback(() => {
    Promise.all([getEvaluationResults(sheet.id), getEvaluationResponses(sheet.id)])
      .then(([nextResults, nextResponses]) => {
        setResults(nextResults);
        setResponses(nextResponses);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Impossible de charger les résultats."));
  }, [sheet.id]);

  useEffect(() => {
    load();
  }, [load]);

  const questionsById = new Map(sheet.questions.map((question) => [question.id, question]));
  const clientQuestions = sheet.questions.filter((question) => question.section === "client" && question.status === "active");
  const internalQuestions = sheet.questions.filter((question) => question.section === "interne" && question.status === "active");
  const internalVisible = visibleQuestionIds(internalQuestions, sheet.internal.answers);
  const internalFilled = internalQuestions.some((question) => {
    const value = sheet.internal.answers[question.id];
    return value !== null && value !== undefined && value !== "";
  });
  const kept = responses.filter((response) => response.status === "retenue");

  async function handleExport() {
    try {
      await downloadEvaluationExport(sheet.id, sheet.title);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Export impossible.");
    }
  }

  async function applyStatus() {
    if (!confirm) return;
    const { response, action } = confirm;
    setConfirm(null);
    try {
      setResponses(await setEvaluationResponseStatus(sheet.id, response.id, action));
      setResults(await getEvaluationResults(sheet.id));
      showToast(action === "discard" ? "Réponse écartée." : "Réponse rétablie.");
      onChanged();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Action impossible.");
    }
  }

  if (error) return <p className="evaluations-tab__muted">{error}</p>;
  if (!results) return <p className="evaluations-tab__muted">Chargement des résultats…</p>;

  return (
    <div className="sheet-results">
      <div className="sheet-results__head">
        <div className="sheet-results__stat">
          <StatCard icon={MessageSquareText} tone="neutral" value={results.response_count} label="Réponses reçues" />
        </div>
        <div className="sheet-results__exports">
          <button type="button" onClick={() => void handleExport()}>
            <Download size={14} strokeWidth={1.75} aria-hidden="true" />
            Exporter en CSV
          </button>
          <button type="button" onClick={() => setPrinting(kept)} disabled={kept.length === 0 && !internalFilled}>
            <Printer size={14} strokeWidth={1.75} aria-hidden="true" />
            Exporter en PDF
          </button>
        </div>
      </div>
      <p className="evaluations-tab__muted">
        Le PDF contient un document par client, avec ses réponses puis l'évaluation chef de projet. Dans la fenêtre
        d'impression, choisissez « Enregistrer au format PDF ».
      </p>

      <section className="sheet-results__section">
        <h4>Satisfaction client</h4>
        {results.response_count === 0 && sheet.status === "brouillon" ? (
          <p className="evaluations-tab__muted">Ouvrez la fiche et envoyez le lien au client pour recevoir des réponses.</p>
        ) : (
          <div className="sheet-results__grid">
            {results.client.map((item) => {
              const question = questionsById.get(item.question_id);
              return question ? <SummaryCard key={item.question_id} question={question} summary={item.summary} /> : null;
            })}
          </div>
        )}
      </section>

      <section className="sheet-results__section">
        <h4>Évaluation chef de projet</h4>
        {internalFilled ? (
          <dl className="sheet-results__internal">
            {internalQuestions
              .filter((question) => internalVisible.has(question.id))
              .map((question) => (
                <div key={question.id}>
                  <dt>{question.label}</dt>
                  <dd>{formatAnswer(sheet.internal.answers[question.id], question)}</dd>
                </div>
              ))}
          </dl>
        ) : (
          <p className="evaluations-tab__muted">
            Pas encore remplie.{" "}
            <button type="button" className="sheet-results__link" onClick={onGoToInternal}>
              Remplir l'évaluation chef de projet
            </button>
          </p>
        )}
      </section>

      <section className="sheet-results__section">
        <h4>Réponses individuelles</h4>
        {responses.length === 0 ? (
          <p className="evaluations-tab__muted">Aucune réponse pour l'instant.</p>
        ) : (
          <ul className="sheet-results__responses">
            {responses.map((response) => {
              const open = expanded === response.id;
              const visible = visibleQuestionIds(clientQuestions, response.answers);
              return (
                <li key={response.id} className={response.status === "ecartee" ? "is-discarded" : undefined}>
                  <div className="sheet-results__response-row">
                    <button
                      type="button"
                      className="sheet-results__response-toggle"
                      onClick={() => setExpanded(open ? null : response.id)}
                      aria-expanded={open}
                    >
                      <ChevronDown size={14} strokeWidth={1.75} className={open ? "is-open" : undefined} aria-hidden="true" />
                      <strong>{response.respondent_name}</strong>
                      <span>{DATE_TIME.format(new Date(response.created_at))}</span>
                      {response.status === "ecartee" && <em>écartée</em>}
                    </button>
                    <div className="sheet-results__response-actions">
                      {response.status === "retenue" && (
                        <button type="button" onClick={() => setPrinting([response])} title="Imprimer seulement cette réponse">
                          <FileText size={14} strokeWidth={1.75} aria-hidden="true" />
                          PDF
                        </button>
                      )}
                      {canManage && (
                        <button
                          type="button"
                          onClick={() =>
                            setConfirm({ response, action: response.status === "retenue" ? "discard" : "restore" })
                          }
                        >
                          {response.status === "retenue" ? "Écarter" : "Rétablir"}
                        </button>
                      )}
                    </div>
                  </div>
                  {open && (
                    <dl className="sheet-results__answers">
                      {clientQuestions
                        .filter((question) => visible.has(question.id))
                        .map((question) => (
                          <div key={question.id}>
                            <dt>{question.label}</dt>
                            <dd>{formatAnswer(response.answers[question.id], question)}</dd>
                          </div>
                        ))}
                    </dl>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {confirm && (
        <ConfirmDialog
          title={confirm.action === "discard" ? "Écarter cette réponse ?" : "Rétablir cette réponse ?"}
          message={
            confirm.action === "discard"
              ? `La réponse de ${confirm.response.respondent_name} sortira des résultats, de l'export et des statistiques. Elle reste rétablissable.`
              : `La réponse de ${confirm.response.respondent_name} comptera de nouveau dans les résultats.`
          }
          confirmLabel={confirm.action === "discard" ? "Écarter" : "Rétablir"}
          danger={confirm.action === "discard"}
          onCancel={() => setConfirm(null)}
          onConfirm={() => void applyStatus()}
        />
      )}

      {printing && (
        <SheetPrintView sheet={sheet} projectName={projectName} responses={printing} onDone={() => setPrinting(null)} />
      )}
    </div>
  );
}
