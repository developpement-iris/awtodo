"""Normalisation des réponses et visibilité conditionnelle. Aucune dépendance
ORM : utilisé par les services, et miroir exact de
`frontend/src/features/evaluations/visibility.ts` — garder les deux alignés.

Une « question » est tout objet portant `id`, `label`, `answer_type`,
`options`, `required`, `condition_on_id` et `condition_values`."""

TEXT_LIMITS = {"texte_court": 200, "texte_long": 5000}


class AnswerError(ValueError):
    def __init__(self, question_id, message):
        super().__init__(message)
        self.question_id = question_id
        self.message = message


def _is_empty(raw):
    return raw is None or raw == "" or raw == []


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def normalize_answer(question, raw):
    """Valeur normalisée (`int`, `"oui"`/`"non"`, chaîne, liste) ou `None` si vide."""
    if _is_empty(raw):
        return None
    qid = str(question.id)
    kind = question.answer_type
    if kind in ("note_5", "nps_10"):
        low, high = (1, 5) if kind == "note_5" else (0, 10)
        if not _is_int(raw) or not low <= raw <= high:
            raise AnswerError(qid, f"Réponse attendue entre {low} et {high} : {question.label}")
        return raw
    if kind == "oui_non":
        if raw is True or raw == "oui":
            return "oui"
        if raw is False or raw == "non":
            return "non"
        raise AnswerError(qid, f"Réponse oui/non attendue : {question.label}")
    if kind == "choix_unique":
        if not isinstance(raw, str) or raw not in question.options:
            raise AnswerError(qid, f"Choix inconnu : {question.label}")
        return raw
    if kind == "choix_multiple":
        if (
            not isinstance(raw, list)
            or len(set(map(str, raw))) != len(raw)
            or any(not isinstance(value, str) or value not in question.options for value in raw)
        ):
            raise AnswerError(qid, f"Choix inconnu : {question.label}")
        return raw
    if not isinstance(raw, str):
        raise AnswerError(qid, f"Texte attendu : {question.label}")
    text = raw.strip()
    if len(text) > TEXT_LIMITS[kind]:
        raise AnswerError(qid, f"Texte trop long ({TEXT_LIMITS[kind]} caractères maximum) : {question.label}")
    return text or None


def visible_question_ids(questions, answers):
    """Une question est visible si elle n'a pas de condition, ou si sa
    question cible est visible et que la réponse à la cible figure dans
    `condition_values`. Une cible absente (archivée) laisse la question
    visible. Les cycles sont interdits à l'écriture
    (`definitions.clean_definition`), l'ordre des questions est indifférent."""
    by_id = {str(question.id): question for question in questions}
    memo = {}

    def is_visible(qid):
        if qid not in memo:
            question = by_id[qid]
            target = str(question.condition_on_id) if question.condition_on_id else None
            if target is None or target not in by_id:
                memo[qid] = True
            else:
                memo[qid] = is_visible(target) and answers.get(target) in question.condition_values
        return memo[qid]

    return {qid for qid in by_id if is_visible(qid)}


def clean_answers(questions, raw_answers, *, enforce_required):
    """Une valeur normalisée par question (`None` si vide ou masquée). Les
    réponses à des questions masquées sont ignorées, pas refusées."""
    by_id = {str(question.id): question for question in questions}
    raw_answers = {str(key): value for key, value in (raw_answers or {}).items()}
    if set(raw_answers) - set(by_id):
        raise AnswerError(None, "Réponse à une question inconnue.")
    normalized = {qid: normalize_answer(question, raw_answers.get(qid)) for qid, question in by_id.items()}
    visible = visible_question_ids(questions, normalized)
    cleaned = {qid: (value if qid in visible else None) for qid, value in normalized.items()}
    if enforce_required:
        for question in questions:
            qid = str(question.id)
            if qid in visible and question.required and cleaned[qid] is None:
                raise AnswerError(qid, f"Réponse obligatoire : {question.label}")
    return cleaned
