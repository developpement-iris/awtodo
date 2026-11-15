"""Résultats d'une fiche d'évaluation : synthèse par question, export CSV et
agrégats pour les statistiques. Lecture seule, aucun contrôle de droits ici :
les appelants (vues, dashboard) vérifient l'accès avant."""

from collections import Counter
from types import SimpleNamespace

from .models import Answer, ClientResponse, InternalEvaluation, SheetQuestion

SECTION_LABELS = {"client": "Client", "interne": "Chef de projet"}


def summarize(question, values):
    """Synthèse des réponses à une question, selon son type (voir le plan :
    note, nps, yes_no, choices, text). Les valeurs `None` sont ignorées."""
    values = [v for v in values if v is not None]
    count = len(values)
    kind = question.answer_type
    if kind == "note_5":
        return {
            "kind": "note",
            "count": count,
            "average": round(sum(values) / count, 2) if count else None,
            "distribution": {str(n): values.count(n) for n in range(1, 6)},
        }
    if kind == "nps_10":
        promoters = sum(1 for v in values if v >= 9)
        detractors = sum(1 for v in values if v <= 6)
        return {
            "kind": "nps",
            "count": count,
            "score": round(100 * (promoters - detractors) / count) if count else None,
            "promoters": promoters,
            "passives": count - promoters - detractors,
            "detractors": detractors,
            "distribution": {str(n): values.count(n) for n in range(0, 11)},
        }
    if kind == "oui_non":
        yes = values.count("oui")
        return {"kind": "yes_no", "count": count, "yes": yes, "no": count - yes, "yes_rate": yes / count if count else None}
    if kind in ("choix_unique", "choix_multiple"):
        counter = Counter()
        for value in values:
            counter.update(value if isinstance(value, list) else [value])
        return {"kind": "choices", "count": count, "counts": {o: counter.get(o, 0) for o in question.options}}
    return {"kind": "text", "count": count, "values": values}


def format_value(question, value):
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    return str(value)


def _active_questions(sheet, section):
    return list(
        SheetQuestion.all_objects.filter(sheet=sheet, section=section, status="active").order_by("position", "created_at")
    )


def _kept_responses(sheet):
    return list(
        ClientResponse.all_objects.filter(sheet=sheet, status="retenue").prefetch_related("answers").order_by("created_at")
    )


def _internal_values(sheet):
    internal = InternalEvaluation.objects.filter(sheet=sheet).first()
    return {a.question_id: a.value for a in internal.answers.all()} if internal else {}


def sheet_results(sheet):
    responses = _kept_responses(sheet)
    by_question = {}
    for response in responses:
        for answer in response.answers.all():
            by_question.setdefault(answer.question_id, []).append(answer.value)
    internal_values = _internal_values(sheet)
    return {
        "response_count": len(responses),
        "client": [
            {"question_id": str(q.id), "summary": summarize(q, by_question.get(q.id, []))}
            for q in _active_questions(sheet, "client")
        ],
        "interne": [
            {"question_id": str(q.id), "value": internal_values.get(q.id)} for q in _active_questions(sheet, "interne")
        ],
    }


def export_csv_rows(sheet):
    """Une ligne par réponse client retenue, suivie de la partie chef de projet
    (identique sur chaque ligne). Sans réponse client, une ligne porte quand
    même la partie chef de projet si elle est remplie."""
    client_questions = _active_questions(sheet, "client")
    internal_questions = _active_questions(sheet, "interne")
    internal_values = _internal_values(sheet)
    internal_cells = [format_value(q, internal_values.get(q.id)) for q in internal_questions]
    header = (
        ["Date", "Répondant"]
        + [q.label for q in client_questions]
        + [f"Chef de projet — {q.label}" for q in internal_questions]
    )
    rows = []
    for response in _kept_responses(sheet):
        values = {a.question_id: a.value for a in response.answers.all()}
        rows.append(
            [response.created_at.strftime("%Y-%m-%d %H:%M"), response.respondent_name]
            + [format_value(q, values.get(q.id)) for q in client_questions]
            + internal_cells
        )
    if not rows and any(internal_cells):
        rows.append(["", "(aucune réponse client)"] + [""] * len(client_questions) + internal_cells)
    return header, rows


# --- Statistiques (tâche 7) ------------------------------------------------


def _format_result(answer_type, values):
    summary = summarize(SimpleNamespace(answer_type=answer_type, options=[]), values)
    if summary["count"] == 0:
        return "—"
    if answer_type == "note_5":
        return f"{summary['average']:.1f} / 5".replace(".", ",")
    if answer_type == "nps_10":
        return f"NPS {summary['score']:+d}"
    return f"{round(summary['yes_rate'] * 100)} % oui"


def evaluation_insights(project_ids):
    """Agrégats par question générique du catalogue. Un catalogue appartient à
    un seul groupe (ou projet sans groupe) : une ligne ne mélange jamais deux
    groupes. Seules les notes, NPS et oui/non s'agrègent."""
    answers = (
        Answer.objects.filter(
            question__sheet__project_id__in=list(project_ids),
            question__catalog_question__isnull=False,
            question__answer_type__in=("note_5", "nps_10", "oui_non"),
        )
        .exclude(value=None)
        .exclude(client_response__status="ecartee")
        .select_related("question__catalog_question__team", "question__catalog_question__project")
    )
    grouped = {}
    for answer in answers:
        if answer.value is None:  # JSON null sous Postgres
            continue
        source = answer.question.catalog_question
        grouped.setdefault(source, []).append(answer.value)
    rows = [
        {
            "groupe": source.team.name if source.team_id else source.project.name,
            "partie": SECTION_LABELS[source.section],
            "question": source.label,
            "resultat": _format_result(source.answer_type, values),
            "reponses": len(values),
        }
        for source, values in grouped.items()
    ]
    rows.sort(key=lambda r: (r["groupe"], r["partie"], r["question"]))
    response_count = ClientResponse.all_objects.filter(sheet__project_id__in=list(project_ids), status="retenue").count()
    return {"generic_rows": rows, "response_count": response_count}
