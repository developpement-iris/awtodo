import {
  DndContext,
  PointerSensor,
  useDraggable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragMoveEvent,
} from "@dnd-kit/core";
import { CalendarPlus, ChevronLeft, ChevronRight, Share2, SlidersHorizontal } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createBlock,
  getCalendar,
  getIncidents,
  getMe,
  getTasks,
  getWorkingHours,
  listCalendarShares,
  updateBlock,
  updateEvent,
  updateProjectPlanningEntry,
} from "../../api/client";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "../../components/Accordion";
import { Checkbox } from "../../components/Checkbox";
import { LoadingTransition } from "../../components/LoadingTransition";
import { SkeletonRows } from "../../components/Skeleton";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { useToast } from "../../context/ToastContext";
import type { ViewName } from "../../types/navigation";
import type { CalendarBundle, Incident, Me, ScheduledBlock, Task, WorkingHoursDay } from "../../types/watodo";
import { TaskCardDialog } from "../tasks/TaskCardDialog";
import { BlockDialog } from "./BlockDialog";
import {
  addDays,
  addMonths,
  formatMonthTitle,
  formatRangeTitle,
  startOfDay,
  startOfWeek,
  toIsoDate,
} from "./calendarMath";
import { isoAt, resolveDrop, resolveMove } from "./dndDrop";
import { EventDialog } from "./EventDialog";
import { MonthGrid } from "./MonthGrid";
import { PlanningPreferencesDialog } from "./PlanningPreferencesDialog";
import { SharePanel } from "./SharePanel";
import {
  blockToItem,
  calendarUserLabel,
  eventToItem,
  PLANNING_PALETTE,
  projectEntryToItem,
  type CalendarItem,
} from "./types";
import { WeekGrid } from "./WeekGrid";
import "./planning.css";

const SCHEDULABLE_TASK_STATUSES = new Set(["assignee", "en_cours"]);
const SCHEDULABLE_INCIDENT_STATUSES = new Set(["signale", "en_cours"]);
const HOUR_MS = 60 * 60 * 1000;

type ViewMode = "week" | "month";

type UnscheduledItemProps =
  | { kind: "task"; task: Task; blockCount: number }
  | { kind: "incident"; incident: Incident; blockCount: number };

// Généralisé de "UnscheduledTask" (tâches uniquement) pour couvrir aussi les
// incidents — retour direct : "il y a un onglet avec des tâches à choisir,
// j'aimerais qu'il y ait tâches ET incidents". Le glisser-déposer distingue
// les deux via `data.kind` (voir `handleDragEnd`).
function UnscheduledItem(props: UnscheduledItemProps) {
  const item = props.kind === "task" ? props.task : props.incident;
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `unsched:${props.kind}:${item.id}`,
    data:
      props.kind === "task"
        ? { type: "external", kind: "task", task: props.task }
        : { type: "external", kind: "incident", incident: props.incident },
  });
  return (
    <li
      ref={setNodeRef}
      className={`planning-unsched__item${isDragging ? " planning-unsched__item--dragging" : ""}`}
      style={transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined}
      {...listeners}
      {...attributes}
    >
      <span className={`planning-unsched__prio planning-unsched__prio--${item.priority}`} />
      <span className="planning-unsched__title">{item.title}</span>
      {props.blockCount > 0 && (
        <span className="planning-unsched__count" title="Créneaux déjà posés">
          {props.blockCount}
        </span>
      )}
    </li>
  );
}

interface PlanningPageProps {
  onNavigate?: (view: ViewName, options?: { taskId?: string; incidentId?: string }) => void;
}

export function PlanningPage({ onNavigate }: PlanningPageProps) {
  const { currentUser, users } = useCurrentUser();
  const { showToast } = useToast();
  const [view, setView] = useState<ViewMode>("week");
  const [cursor, setCursor] = useState(() => startOfDay(new Date()));
  const [bundle, setBundle] = useState<CalendarBundle | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [hiddenCalendars, setHiddenCalendars] = useState<Set<string>>(new Set());
  // Cran de 30 min visé par le glissé en cours (aperçu dans la grille).
  const [dropPreview, setDropPreview] = useState<{ dayIso: string; minutes: number } | null>(null);
  const [dialog, setDialog] = useState<
    | { kind: "create"; start: string; end: string }
    | { kind: "edit"; eventId: string }
    | { kind: "block"; block: ScheduledBlock }
    | { kind: "share" }
    | { kind: "preferences" }
    | { kind: "task"; taskId: string }
    | null
  >(null);
  // Réglages personnels du planning (couleur, horaires de travail) —
  // chargés à part de `currentUser` (contexte global) : les horaires ne sont
  // exposés que par `MeSerializer`/`getMe()`, jamais par `getUsers()` (voir
  // docs/organisation-et-comptes.md > "Personnalisation du planning").
  const [me, setMe] = useState<Me | null>(null);
  // Personnes qui m'ont accordé le droit de gérer leurs horaires (partage
  // avec `can_manage_work_hours=True`) — alimente le sélecteur de personne
  // du panneau "Mon planning".
  const [delegatedUsers, setDelegatedUsers] = useState<{ id: string; label: string }[]>([]);

  useEffect(() => {
    getMe()
      .then(setMe)
      .catch(() => undefined);
    listCalendarShares()
      .then((data) =>
        setDelegatedUsers(
          data.received
            .filter((share) => share.can_manage_work_hours)
            .map((share) => ({ id: share.owner.id, label: calendarUserLabel(share.owner) })),
        ),
      )
      .catch(() => undefined);
  }, []);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const range = useMemo(() => {
    if (view === "week") {
      const from = startOfWeek(cursor);
      return { from, to: addDays(from, 7) };
    }
    const firstOfMonth = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const from = startOfWeek(firstOfMonth);
    return { from, to: addDays(from, 42) };
  }, [view, cursor]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    let cancelled = false;
    setBundle(null);
    setError(null);
    getCalendar({ from: range.from.toISOString(), to: range.to.toISOString() })
      .then((data) => {
        if (!cancelled) setBundle(data);
      })
      .catch(() => {
        if (!cancelled) setError("Impossible de charger le calendrier.");
      });
    return () => {
      cancelled = true;
    };
  }, [range.from, range.to, reloadKey]);

  useEffect(() => {
    if (!currentUser) return;
    getTasks({ assignee: currentUser.id })
      .then((data) => setTasks(data.filter((t) => SCHEDULABLE_TASK_STATUSES.has(t.status))))
      .catch(() => setTasks([]));
  }, [currentUser, reloadKey]);

  useEffect(() => {
    if (!currentUser) return;
    getIncidents({ assigned_to: currentUser.id, status: Array.from(SCHEDULABLE_INCIDENT_STATUSES) })
      .then(setIncidents)
      .catch(() => setIncidents([]));
  }, [currentUser, reloadKey]);

  // Liste des calendriers : le mien + un par personne qui partage avec moi.
  const sharedCalendars = useMemo(
    () =>
      (bundle?.shared ?? []).map((group, index) => ({
        id: group.owner.id,
        label: calendarUserLabel(group.owner),
        color: PLANNING_PALETTE[index % PLANNING_PALETTE.length],
      })),
    [bundle],
  );

  const colorByCalendar = useMemo(() => {
    const map = new Map<string, string>();
    sharedCalendars.forEach((c) => map.set(c.id, c.color));
    return map;
  }, [sharedCalendars]);

  const myColor = me?.planning_color || undefined;

  const allItems: CalendarItem[] = useMemo(() => {
    if (!bundle) return [];
    return [
      ...bundle.events.map((occ) => eventToItem(occ, { color: myColor })),
      ...bundle.blocks.map((block) => blockToItem(block, { color: myColor })),
      ...bundle.project_entries.map((occ) => projectEntryToItem(occ)),
      ...bundle.shared.flatMap((group) => {
        const color = colorByCalendar.get(group.owner.id);
        return [
          ...group.occurrences.map((occ) => eventToItem(occ, { shared: true, color })),
          ...group.blocks.map((block) =>
            blockToItem(block, {
              shared: true,
              color,
              calendarId: group.owner.id,
              ownerLabel: calendarUserLabel(group.owner),
            }),
          ),
        ];
      }),
    ];
  }, [bundle, colorByCalendar, myColor]);

  const visibleItems = useMemo(
    () => allItems.filter((item) => !hiddenCalendars.has(item.calendarId)),
    [allItems, hiddenCalendars],
  );

  // Horaires de travail de la semaine affichée (base ou exception) — voir
  // docs/organisation-et-comptes.md > "Personnalisation du planning".
  // Refetch à chaque changement de semaine : une exception peut ne concerner
  // que la semaine consultée, pas le modèle de base.
  const currentWeekStart = useMemo(() => toIsoDate(startOfWeek(cursor)), [cursor]);
  const [workHours, setWorkHours] = useState<WorkingHoursDay[] | null>(null);

  useEffect(() => {
    if (view !== "week") return;
    let cancelled = false;
    getWorkingHours({ week: currentWeekStart })
      .then((data) => {
        if (!cancelled) setWorkHours(data.days);
      })
      .catch(() => {
        if (!cancelled) setWorkHours(null);
      });
    return () => {
      cancelled = true;
    };
  }, [currentWeekStart, view, reloadKey]);

  const blockCountByTask = useMemo(() => {
    const map = new Map<string, number>();
    for (const b of bundle?.blocks ?? []) {
      if (b.task) map.set(b.task.id, (map.get(b.task.id) ?? 0) + 1);
    }
    return map;
  }, [bundle]);

  const blockCountByIncident = useMemo(() => {
    const map = new Map<string, number>();
    for (const b of bundle?.blocks ?? []) {
      if (b.incident) map.set(b.incident.id, (map.get(b.incident.id) ?? 0) + 1);
    }
    return map;
  }, [bundle]);

  function toggleCalendar(id: string) {
    setHiddenCalendars((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  type DragData =
    | { type: "external"; kind: "task"; task: Task }
    | { type: "external"; kind: "incident"; incident: Incident }
    | { type: "move"; item: CalendarItem }
    | { type: "resize"; item: CalendarItem };

  // Le déplacement d'un item déjà positionné se résout à partir du décalage
  // du glissé appliqué à sa position de départ (`resolveMove`) — pas de la
  // position absolue du pointeur (`resolveDrop`), qui dépend de l'endroit où
  // l'item a été saisi. Dépôt externe / redimensionnement restent pointeur.
  function resolveForEvent(event: DragEndEvent | DragMoveEvent) {
    const data = event.active.data.current as DragData | undefined;
    if (data?.type === "move") return resolveMove(event, data.item.start);
    return resolveDrop(event);
  }

  function handleDragMove(event: DragMoveEvent) {
    const next = resolveForEvent(event);
    setDropPreview((prev) => {
      if (prev === next) return prev;
      if (prev && next && prev.dayIso === next.dayIso && prev.minutes === next.minutes) return prev;
      return next;
    });
  }

  async function handleDragEnd(event: DragEndEvent) {
    setDropPreview(null);
    const drop = resolveForEvent(event);
    if (!drop) return;
    const data = event.active.data.current as DragData | undefined;
    if (!data) return;

    try {
      if (data.type === "external") {
        const start = isoAt(drop.dayIso, drop.minutes);
        const end = new Date(new Date(start).getTime() + HOUR_MS).toISOString();
        if (data.kind === "task") {
          await createBlock({ task: data.task.id, start, end });
        } else {
          await createBlock({ incident: data.incident.id, start, end });
        }
        showToast("Créneau ajouté.");
      } else if (data.type === "move") {
        const { item } = data;
        if (!item.editable) return;
        const duration = new Date(item.end).getTime() - new Date(item.start).getTime();
        const start = isoAt(drop.dayIso, drop.minutes);
        const end = new Date(new Date(start).getTime() + duration).toISOString();
        await applyItemTimes(item, start, end);
      } else {
        const { item } = data;
        if (!item.editable) return;
        const startMin = new Date(item.start).getHours() * 60 + new Date(item.start).getMinutes();
        if (drop.minutes <= startMin) return;
        const end = isoAt(item.start.slice(0, 10), drop.minutes);
        await applyItemTimes(item, item.start, end);
      }
      reload();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Action impossible.");
    }
  }

  async function applyItemTimes(item: CalendarItem, start: string, end: string) {
    if (item.kind === "event") {
      await updateEvent(item.id, { start, end });
    } else if (item.kind === "block") {
      await updateBlock(item.id, { start, end });
    } else if (item.kind === "project_entry") {
      const occ = item.raw as { project_id: string };
      await updateProjectPlanningEntry(occ.project_id, item.id, { start, end });
    }
  }

  function handleItemClick(item: CalendarItem) {
    if (item.kind === "event") {
      setDialog({ kind: "edit", eventId: item.id });
    } else if (item.kind === "shared") {
      // Événement d'un calendrier partagé : lecture seule. Pas d'appel à
      // `getEvent` — le propriétaire n'est ni moi (owner) ni un participant,
      // le endpoint est scopé à ces deux cas et renverrait 404 ("Impossible
      // de charger l'événement"). Le détail utile (titre, propriétaire) est
      // déjà sur l'item, chargé avec le calendrier — même traitement que les
      // créneaux partagés ci-dessous.
      showToast(`${item.title} — ${item.subtitle ?? "calendrier partagé"}`);
    } else if (item.kind === "block") {
      // Créneau d'un calendrier partagé : lecture seule, pas d'édition.
      if (!item.editable) {
        showToast(`${item.title} — ${item.subtitle ?? "créneau partagé"}`);
        return;
      }
      setDialog({ kind: "block", block: item.raw as ScheduledBlock });
    } else {
      showToast(`${item.title} — planning de projet`);
    }
  }

  function shiftCursor(dir: number) {
    setCursor((c) => (view === "week" ? addDays(c, dir * 7) : addMonths(c, dir)));
  }

  const title = view === "week" ? formatRangeTitle(startOfWeek(cursor)) : formatMonthTitle(cursor);

  return (
    <div className="planning-page">
      <div className="planning-page__toolbar">
        <div className="planning-page__nav">
          <button type="button" className="planning-btn" onClick={() => shiftCursor(-1)} aria-label="Précédent">
            <ChevronLeft size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
          <button type="button" className="planning-btn" onClick={() => setCursor(startOfDay(new Date()))}>
            Aujourd'hui
          </button>
          <button type="button" className="planning-btn" onClick={() => shiftCursor(1)} aria-label="Suivant">
            <ChevronRight size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
          <strong className="planning-page__title">{title}</strong>
        </div>

        <div className="planning-page__actions">
          <div className="planning-page__view-toggle" role="tablist" aria-label="Vue">
            <button
              type="button"
              role="tab"
              aria-selected={view === "week"}
              className={view === "week" ? "planning-toggle planning-toggle--on" : "planning-toggle"}
              onClick={() => setView("week")}
            >
              Semaine
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === "month"}
              className={view === "month" ? "planning-toggle planning-toggle--on" : "planning-toggle"}
              onClick={() => setView("month")}
            >
              Mois
            </button>
          </div>
          <button type="button" className="planning-btn" onClick={() => setDialog({ kind: "preferences" })}>
            <SlidersHorizontal size={15} strokeWidth={1.75} aria-hidden="true" />
            Mon planning
          </button>
          <button type="button" className="planning-btn" onClick={() => setDialog({ kind: "share" })}>
            <Share2 size={15} strokeWidth={1.75} aria-hidden="true" />
            Partage
          </button>
          <button
            type="button"
            className="planning-btn planning-btn--primary"
            onClick={() => {
              const start = new Date();
              start.setMinutes(0, 0, 0);
              start.setHours(9);
              const end = new Date(start.getTime() + HOUR_MS);
              setDialog({ kind: "create", start: start.toISOString(), end: end.toISOString() });
            }}
          >
            <CalendarPlus size={15} strokeWidth={1.75} aria-hidden="true" />
            Nouvel événement
          </button>
        </div>
      </div>

      {error && <p className="planning-page__error">{error}</p>}

      <DndContext
        sensors={sensors}
        onDragMove={handleDragMove}
        onDragEnd={handleDragEnd}
        onDragCancel={() => setDropPreview(null)}
      >
        <div className="planning-page__layout">
          <aside className="planning-side">
            <section className="planning-calendars">
              <h2 className="planning-side__heading">Calendriers</h2>
              <ul className="planning-calendars__list">
                <li>
                  <label className="planning-calendars__item">
                    <Checkbox
                      checked={!hiddenCalendars.has("mine")}
                      onCheckedChange={() => toggleCalendar("mine")}
                      aria-label="Afficher mon calendrier"
                    />
                    <span
                      className="planning-calendars__swatch planning-calendars__swatch--mine"
                      style={myColor ? { backgroundColor: myColor } : undefined}
                    />
                    Mon calendrier
                  </label>
                </li>
                {sharedCalendars.map((cal) => (
                  <li key={cal.id}>
                    <label className="planning-calendars__item">
                      <Checkbox
                        checked={!hiddenCalendars.has(cal.id)}
                        onCheckedChange={() => toggleCalendar(cal.id)}
                        aria-label={`Afficher le calendrier de ${cal.label}`}
                      />
                      <span
                        className="planning-calendars__swatch"
                        style={{ backgroundColor: cal.color }}
                      />
                      {cal.label}
                    </label>
                  </li>
                ))}
                {sharedCalendars.length === 0 && (
                  <li className="planning-side__empty">Aucun calendrier partagé avec vous.</li>
                )}
              </ul>
            </section>

            <section className="planning-unsched">
              <h2 className="planning-side__heading">À planifier</h2>
              <p className="planning-side__hint">
                Glissez un élément sur le calendrier. Un même élément peut recevoir plusieurs créneaux.
              </p>
              <Accordion type="multiple" defaultValue={["tasks", "incidents"]}>
                <AccordionItem value="tasks">
                  <AccordionTrigger>
                    Tâches
                    {tasks.length > 0 && <span className="planning-unsched__accordion-count">{tasks.length}</span>}
                  </AccordionTrigger>
                  <AccordionContent>
                    <ul className="planning-unsched__list">
                      {tasks.map((task) => (
                        <UnscheduledItem
                          key={task.id}
                          kind="task"
                          task={task}
                          blockCount={blockCountByTask.get(task.id) ?? 0}
                        />
                      ))}
                      {tasks.length === 0 && <li className="planning-side__empty">Aucune tâche à planifier.</li>}
                    </ul>
                  </AccordionContent>
                </AccordionItem>
                <AccordionItem value="incidents">
                  <AccordionTrigger>
                    Incidents
                    {incidents.length > 0 && (
                      <span className="planning-unsched__accordion-count">{incidents.length}</span>
                    )}
                  </AccordionTrigger>
                  <AccordionContent>
                    <ul className="planning-unsched__list">
                      {incidents.map((incident) => (
                        <UnscheduledItem
                          key={incident.id}
                          kind="incident"
                          incident={incident}
                          blockCount={blockCountByIncident.get(incident.id) ?? 0}
                        />
                      ))}
                      {incidents.length === 0 && (
                        <li className="planning-side__empty">Aucun incident à planifier.</li>
                      )}
                    </ul>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </section>
          </aside>

          <div className="planning-page__calendar">
            <LoadingTransition loading={bundle === null && !error} skeleton={<SkeletonRows rows={8} />}>
              {view === "week" ? (
                <WeekGrid
                  weekStart={startOfWeek(cursor)}
                  items={visibleItems}
                  dropPreview={dropPreview}
                  workHours={workHours}
                  onItemClick={handleItemClick}
                  onEmptyClick={(dayIso, minutes) => {
                    const start = isoAt(dayIso, minutes);
                    const end = new Date(new Date(start).getTime() + HOUR_MS).toISOString();
                    setDialog({ kind: "create", start, end });
                  }}
                />
              ) : (
                <MonthGrid
                  monthDate={cursor}
                  items={visibleItems}
                  onDayClick={(day) => {
                    setCursor(startOfDay(day));
                    setView("week");
                  }}
                  onItemClick={handleItemClick}
                />
              )}
            </LoadingTransition>
          </div>
        </div>
      </DndContext>

      {dialog?.kind === "create" && (
        <EventDialog
          mode="create"
          initialStart={dialog.start}
          initialEnd={dialog.end}
          assignableUsers={users}
          onClose={() => setDialog(null)}
          onSaved={reload}
        />
      )}
      {dialog?.kind === "edit" && (
        <EventDialog
          mode="edit"
          eventId={dialog.eventId}
          assignableUsers={users}
          onClose={() => setDialog(null)}
          onSaved={reload}
        />
      )}
      {dialog?.kind === "block" && (
        <BlockDialog
          block={dialog.block}
          onClose={() => setDialog(null)}
          onSaved={reload}
          onOpenTarget={
            dialog.block.task
              ? () => setDialog({ kind: "task", taskId: dialog.block.task!.id })
              : dialog.block.incident && onNavigate
                ? () => {
                    setDialog(null);
                    onNavigate("incidents", { incidentId: dialog.block.incident!.id });
                  }
                : undefined
          }
        />
      )}
      {dialog?.kind === "task" && (
        <TaskCardDialog taskId={dialog.taskId} onClose={() => setDialog(null)} onChanged={reload} />
      )}
      {dialog?.kind === "share" && <SharePanel onClose={() => setDialog(null)} onChanged={reload} />}
      {dialog?.kind === "preferences" && me && (
        <PlanningPreferencesDialog
          me={me}
          currentWeekStart={currentWeekStart}
          delegatedUsers={delegatedUsers}
          onClose={() => setDialog(null)}
          onSaved={(updated) => {
            setMe(updated);
            reload();
          }}
        />
      )}
    </div>
  );
}
