import { DndContext, PointerSensor, useDraggable, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { CalendarPlus, ChevronLeft, ChevronRight, Share2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createBlock,
  getCalendar,
  getTasks,
  updateBlock,
  updateEvent,
  updateProjectPlanningEntry,
} from "../../api/client";
import { Checkbox } from "../../components/Checkbox";
import { LoadingTransition } from "../../components/LoadingTransition";
import { SkeletonRows } from "../../components/Skeleton";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { useToast } from "../../context/ToastContext";
import type { CalendarBundle, ScheduledBlock, Task } from "../../types/watodo";
import { BlockDialog } from "./BlockDialog";
import {
  addDays,
  addMonths,
  formatMonthTitle,
  formatRangeTitle,
  startOfDay,
  startOfWeek,
} from "./calendarMath";
import { isoAt, resolveDrop } from "./dndDrop";
import { EventDialog } from "./EventDialog";
import { MonthGrid } from "./MonthGrid";
import { SharePanel } from "./SharePanel";
import { blockToItem, calendarUserLabel, eventToItem, projectEntryToItem, type CalendarItem } from "./types";
import { WeekGrid } from "./WeekGrid";
import "./planning.css";

const SCHEDULABLE_TASK_STATUSES = new Set(["assignee", "en_cours"]);
const HOUR_MS = 60 * 60 * 1000;

// Couleurs d'identité des calendriers partagés (façon Outlook). Teintes
// "text" sobres, toujours accompagnées du nom du propriétaire — jamais la
// couleur seule (règle d'accessibilité de la charte). "Mon calendrier"
// garde le traitement accent par défaut, pas de couleur ici.
const CALENDAR_COLORS = ["#2E6363", "#96790F", "#7A4F9E", "#2E6B45", "#B0466A", "#3A6EA5"];

type ViewMode = "week" | "month";

function UnscheduledTask({ task, blockCount }: { task: Task; blockCount: number }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `unsched:task:${task.id}`,
    data: { type: "external", task },
  });
  return (
    <li
      ref={setNodeRef}
      className={`planning-unsched__item${isDragging ? " planning-unsched__item--dragging" : ""}`}
      style={transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined}
      {...listeners}
      {...attributes}
    >
      <span className={`planning-unsched__prio planning-unsched__prio--${task.priority}`} />
      <span className="planning-unsched__title">{task.title}</span>
      {blockCount > 0 && (
        <span className="planning-unsched__count" title="Créneaux déjà posés">
          {blockCount}
        </span>
      )}
    </li>
  );
}

export function PlanningPage() {
  const { currentUser, users } = useCurrentUser();
  const { showToast } = useToast();
  const [view, setView] = useState<ViewMode>("week");
  const [cursor, setCursor] = useState(() => startOfDay(new Date()));
  const [bundle, setBundle] = useState<CalendarBundle | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [hiddenCalendars, setHiddenCalendars] = useState<Set<string>>(new Set());
  const [dialog, setDialog] = useState<
    | { kind: "create"; start: string; end: string }
    | { kind: "edit"; eventId: string }
    | { kind: "block"; block: ScheduledBlock }
    | { kind: "share" }
    | null
  >(null);

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

  // Liste des calendriers : le mien + un par personne qui partage avec moi.
  const sharedCalendars = useMemo(
    () =>
      (bundle?.shared ?? []).map((group, index) => ({
        id: group.owner.id,
        label: calendarUserLabel(group.owner),
        color: CALENDAR_COLORS[index % CALENDAR_COLORS.length],
      })),
    [bundle],
  );

  const colorByCalendar = useMemo(() => {
    const map = new Map<string, string>();
    sharedCalendars.forEach((c) => map.set(c.id, c.color));
    return map;
  }, [sharedCalendars]);

  const allItems: CalendarItem[] = useMemo(() => {
    if (!bundle) return [];
    return [
      ...bundle.events.map((occ) => eventToItem(occ)),
      ...bundle.blocks.map((block) => blockToItem(block)),
      ...bundle.project_entries.map((occ) => projectEntryToItem(occ)),
      ...bundle.shared.flatMap((group) =>
        group.occurrences.map((occ) =>
          eventToItem(occ, { shared: true, color: colorByCalendar.get(group.owner.id) }),
        ),
      ),
    ];
  }, [bundle, colorByCalendar]);

  const visibleItems = useMemo(
    () => allItems.filter((item) => !hiddenCalendars.has(item.calendarId)),
    [allItems, hiddenCalendars],
  );

  const blockCountByTask = useMemo(() => {
    const map = new Map<string, number>();
    for (const b of bundle?.blocks ?? []) {
      if (b.task) map.set(b.task.id, (map.get(b.task.id) ?? 0) + 1);
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

  async function handleDragEnd(event: DragEndEvent) {
    const drop = resolveDrop(event);
    if (!drop) return;
    const data = event.active.data.current as
      | { type: "external"; task: Task }
      | { type: "move"; item: CalendarItem }
      | { type: "resize"; item: CalendarItem }
      | undefined;
    if (!data) return;

    try {
      if (data.type === "external") {
        const start = isoAt(drop.dayIso, drop.minutes);
        const end = new Date(new Date(start).getTime() + HOUR_MS).toISOString();
        await createBlock({ task: data.task.id, start, end });
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
    if (item.kind === "event" || item.kind === "shared") {
      setDialog({ kind: "edit", eventId: item.id });
    } else if (item.kind === "block") {
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

      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
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
                    <span className="planning-calendars__swatch planning-calendars__swatch--mine" />
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
                Glissez une tâche sur le calendrier. Une même tâche peut recevoir plusieurs créneaux.
              </p>
              <ul className="planning-unsched__list">
                {tasks.map((task) => (
                  <UnscheduledTask key={task.id} task={task} blockCount={blockCountByTask.get(task.id) ?? 0} />
                ))}
                {tasks.length === 0 && <li className="planning-side__empty">Aucune tâche à planifier.</li>}
              </ul>
            </section>
          </aside>

          <div className="planning-page__calendar">
            <LoadingTransition loading={bundle === null && !error} skeleton={<SkeletonRows rows={8} />}>
              {view === "week" ? (
                <WeekGrid
                  weekStart={startOfWeek(cursor)}
                  items={visibleItems}
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
        <BlockDialog block={dialog.block} onClose={() => setDialog(null)} onSaved={reload} />
      )}
      {dialog?.kind === "share" && <SharePanel onClose={() => setDialog(null)} onChanged={reload} />}
    </div>
  );
}
