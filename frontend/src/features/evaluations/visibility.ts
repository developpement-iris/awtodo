import type { EvaluationAnswerValue, EvaluationQuestion } from "../../types/watodo";

/** Miroir de apps/evaluations/answers.py::visible_question_ids — garder les deux alignés.
 * Une question conditionnelle est visible si sa cible l'est et que la réponse
 * à la cible figure dans `condition_values`. */
export function visibleQuestionIds(
  questions: Pick<EvaluationQuestion, "id" | "condition_on" | "condition_values">[],
  answers: Record<string, EvaluationAnswerValue>,
): Set<string> {
  const byId = new Map(questions.map((question) => [question.id, question]));
  const memo = new Map<string, boolean>();
  const isVisible = (id: string, depth = 0): boolean => {
    const cached = memo.get(id);
    if (cached !== undefined) return cached;
    const question = byId.get(id)!;
    const target = question.condition_on;
    let visible = true;
    if (target && byId.has(target) && depth < questions.length) {
      const value = answers[target];
      visible = isVisible(target, depth + 1) && typeof value === "string" && question.condition_values.includes(value);
    }
    memo.set(id, visible);
    return visible;
  };
  return new Set(questions.filter((question) => isVisible(question.id)).map((question) => question.id));
}
