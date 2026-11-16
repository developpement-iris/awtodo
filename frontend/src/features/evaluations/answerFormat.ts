import type { EvaluationAnswerType, EvaluationAnswerValue, EvaluationQuestion } from "../../types/watodo";

export const ANSWER_TYPE_LABELS: Record<EvaluationAnswerType, string> = {
  note_5: "Note de 1 à 5",
  nps_10: "Recommandation de 0 à 10",
  oui_non: "Oui / Non",
  choix_unique: "Choix unique",
  choix_multiple: "Choix multiple",
  texte_court: "Texte court",
  texte_long: "Texte long",
};

export const CONDITIONABLE_TYPES: EvaluationAnswerType[] = ["oui_non", "choix_unique"];
export const CHOICE_TYPES: EvaluationAnswerType[] = ["choix_unique", "choix_multiple"];

export const SECTION_LABELS = { client: "Satisfaction client", interne: "Évaluation chef de projet" } as const;

export function isEmptyAnswer(value: EvaluationAnswerValue | undefined): boolean {
  return value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0);
}

export function formatAnswer(value: EvaluationAnswerValue | undefined, question?: Pick<EvaluationQuestion, "answer_type">): string {
  if (isEmptyAnswer(value)) return "—";
  if (Array.isArray(value)) return value.join(", ");
  if (value === "oui") return "Oui";
  if (value === "non") return "Non";
  if (question?.answer_type === "note_5") return `${value} / 5`;
  if (question?.answer_type === "nps_10") return `${value} / 10`;
  return String(value);
}

/** Valeurs proposées pour une condition : Oui/Non ou les options de la cible. */
export function conditionChoices(target: Pick<EvaluationQuestion, "answer_type" | "options">): { value: string; label: string }[] {
  if (target.answer_type === "oui_non") {
    return [
      { value: "oui", label: "Oui" },
      { value: "non", label: "Non" },
    ];
  }
  return target.options.map((option) => ({ value: option, label: option }));
}

export function describeCondition(question: EvaluationQuestion, all: EvaluationQuestion[]): string | null {
  if (!question.condition_on) return null;
  const target = all.find((candidate) => candidate.id === question.condition_on);
  if (!target) return null;
  const values = question.condition_values.map((value) => (value === "oui" ? "Oui" : value === "non" ? "Non" : value));
  return `Affichée si « ${target.label} » = ${values.join(" ou ")}`;
}
