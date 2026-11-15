"""Calcul de la charge par personne (session du 2026-11-14) — fonctions pures,
sans accès à la base, testées à part (`tests/test_workload.py`).

Une occurrence planifiée (entrée du planning projet, créneau sur une tâche ou
un incident) est découpée en demi-journées, en heure de Paris : le matin va de
minuit à 13 h, l'après-midi de 13 h à minuit. Une demi-journée compte dès que
l'occurrence la chevauche, même brièvement, et une seule fois par personne et
par projet quel que soit le nombre d'occurrences qui la touchent.
"""

from datetime import date, datetime, time, timedelta

from django.utils import timezone

AFTERNOON_START = time(13, 0)
MORNING = "am"
AFTERNOON = "pm"


def half_days(start, end):
    """Demi-journées `(date, "am"|"pm")` chevauchées par [start, end[, en heure
    locale. Une occurrence vide ou inversée n'en donne aucune."""
    if end <= start:
        return set()
    local_start = timezone.localtime(start)
    local_end = timezone.localtime(end)
    tz = local_start.tzinfo
    result = set()
    day = local_start.date()
    while day <= local_end.date():
        midnight = datetime.combine(day, time.min, tzinfo=tz)
        noon = datetime.combine(day, AFTERNOON_START, tzinfo=tz)
        next_midnight = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
        if local_start < noon and local_end > midnight:
            result.add((day, MORNING))
        if local_start < next_midnight and local_end > noon:
            result.add((day, AFTERNOON))
        day += timedelta(days=1)
    return result


def period_key(day, granularity):
    """Clé de la période contenant `day` : `2027-01` (mois) ou `2027-W03`
    (semaine ISO, du lundi au dimanche)."""
    if granularity == "week":
        iso_year, iso_week, _ = day.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return f"{day.year}-{day.month:02d}"


def build_periods(first_day, last_day, granularity):
    """Périodes successives couvrant [first_day, last_day] (dates incluses),
    rognées aux bornes. Chaque période : `{key, start, end}` (dates incluses)."""
    periods = []
    cursor = first_day
    while cursor <= last_day:
        if granularity == "week":
            natural_end = cursor + timedelta(days=6 - cursor.weekday())
        else:
            next_month = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
            natural_end = next_month - timedelta(days=1)
        end = min(natural_end, last_day)
        periods.append({"key": period_key(cursor, granularity), "start": cursor, "end": end})
        cursor = end + timedelta(days=1)
    return periods


def working_days(start, end):
    """Jours ouvrés (lundi-vendredi) entre deux dates incluses — sert de repère
    de capacité (2 demi-journées par jour ouvré), jours fériés non déduits."""
    count = 0
    day = start
    while day <= end:
        if day.weekday() < 5:
            count += 1
        day += timedelta(days=1)
    return count


def project_active_between(*, created, end, start_day, end_day):
    """Vrai si un projet né le `created` et fini le `end` (`None` = sans fin)
    chevauche la période [start_day, end_day]."""
    if created > end_day:
        return False
    return end is None or end >= start_day
