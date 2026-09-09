import { DndContext, PointerSensor, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { CalendarPlus, ChevronLeft, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getProjectPlanningEntries, updateProjectPlanningEntry } from "../../api/client";
import { LoadingTransition } from "../../components/LoadingTransition";
import { SkeletonRows } from "../../components/Skeleton";
import { useToast } from "../../context/ToastContext";
import type { Project, ProjectPlanningOccurrence } from "../../types/watodo";
import { addDays, formatRangeTitle, startOfDay, startOfWeek } from "./calendarMath";
import { isoAt, resolveDrop } from "./dndDrop";
import { ProjectEntryDialog } from "./ProjectEntryDialog";
import { projectEntryToItem, type CalendarItem } from "./types";
import { WeekGrid } from "./WeekGrid";
import "./planning.css";

interface ProjectPlanningTabProps {
  project: Project;
}

const HOUR_MS = 60 * 60 * 1000;

export function ProjectPlanningTab({ project }: ProjectPlanningTabProps) {
  const { showToast } = useToast();
  const members = useMemo(() => project.members.map((m) => m.user), [project]);
  const [cursor, setCursor] = useState(() => startOfDay(new Date()));
  const [entries, setEntries] = useState<ProjectPlanningOccurrence[] | null>(null);
  const [canManage, setCanManage] = useState(project.permissions.can_manage_project_planning);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [dialog, setDialog] = useState<
    | { kind: "create"; start: string; end: string }
    | { kind: "edit"; entry: ProjectPlanningOccurrence }
    | null
  >(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  const range = useMemo(() => {
    const from = startOfWeek(cursor);
    return { from, to: addDays(from, 7) };
  }, [cursor]);

  useEffect(() => {
    let cancelled = false;
    setEntries(null);
    setError(null);
    getProjectPlanningEntries(project.id, {
      from: range.from.toISOString(),
      to: range.to.toISOString(),
    })
      .then((data) => {
        if (cancelled) return;
        setEntries(data.entries);
        setCanManage(data.can_manage);
      })
      .catch(() => {
        if (!cancelled) setError("Impossible de charger le planning du projet.");
      });
    return () => {
      cancelled = true;
    };
  }, [project.id, range.from, range.to, reloadKey]);

  const items: CalendarItem[] = useMemo(
    () => (entries ?? []).map((occ) => projectEntryToItem(occ)),
    [entries],
  );

  async function handleDragEnd(event: DragEndEvent) {
    const drop = resolveDrop(event);
    if (!drop) return;
    const data = event.active.data.current as
      | { type: "move"; item: CalendarItem }
      | { type: "resize"; item: CalendarItem }
      | undefined;
    if (!data) return;
    const { item } = data;
    try {
      if (data.type === "move") {
        const duration = new Date(item.end).getTime() - new Date(item.start).getTime();
        const start = isoAt(drop.dayIso, drop.minutes);
        const end = new Date(new Date(start).getTime() + duration).toISOString();
        await updateProjectPlanningEntry(project.id, item.id, { start, end });
      } else {
        const startMin = new Date(item.start).getHours() * 60 + new Date(item.start).getMinutes();
        if (drop.minutes <= startMin) return;
        const end = isoAt(item.start.slice(0, 10), drop.minutes);
        await updateProjectPlanningEntry(project.id, item.id, { start: item.start, end });
      }
      reload();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Action impossible.");
    }
  }

  function handleItemClick(item: CalendarItem) {
    const entry = (entries ?? []).find((e) => e.id === item.id);
    if (!entry) return;
    if (canManage) setDialog({ kind: "edit", entry });
    else showToast(`${entry.title} — ${entry.kind_display}`);
  }

  const title = formatRangeTitle(startOfWeek(cursor));

  return (
    <div className="planning-page planning-page--embedded">
      <div className="planning-page__toolbar">
        <div className="planning-page__nav">
          <button
            type="button"
            className="planning-btn"
            onClick={() => setCursor((c) => addDays(c, -7))}
            aria-label="Semaine précédente"
          >
            <ChevronLeft size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
          <button type="button" className="planning-btn" onClick={() => setCursor(startOfDay(new Date()))}>
            Aujourd'hui
          </button>
          <button
            type="button"
            className="planning-btn"
            onClick={() => setCursor((c) => addDays(c, 7))}
            aria-label="Semaine suivante"
          >
            <ChevronRight size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
          <strong className="planning-page__title">{title}</strong>
        </div>
        {canManage && (
          <button
            type="button"
            className="planning-btn planning-btn--primary"
            onClick={() => {
              const start = new Date(startOfWeek(cursor));
              start.setHours(9, 0, 0, 0);
              setDialog({
                kind: "create",
                start: start.toISOString(),
                end: new Date(start.getTime() + HOUR_MS).toISOString(),
              });
            }}
          >
            <CalendarPlus size={15} strokeWidth={1.75} aria-hidden="true" />
            Nouvelle entrée
          </button>
        )}
      </div>

      {!canManage && (
        <p className="planning-page__note">
          Le planning est défini par les chefs de projet. Vous le consultez en lecture seule.
        </p>
      )}
      {error && <p className="planning-page__error">{error}</p>}

      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <div className="planning-page__calendar">
          <LoadingTransition loading={entries === null && !error} skeleton={<SkeletonRows rows={8} />}>
            <WeekGrid
              weekStart={startOfWeek(cursor)}
              items={items}
              onItemClick={handleItemClick}
              onEmptyClick={
                canManage
                  ? (dayIso, minutes) => {
                      const start = isoAt(dayIso, minutes);
                      setDialog({
                        kind: "create",
                        start,
                        end: new Date(new Date(start).getTime() + HOUR_MS).toISOString(),
                      });
                    }
                  : undefined
              }
            />
          </LoadingTransition>
        </div>
      </DndContext>

      {dialog?.kind === "create" && (
        <ProjectEntryDialog
          projectId={project.id}
          members={members}
          initialStart={dialog.start}
          initialEnd={dialog.end}
          onClose={() => setDialog(null)}
          onSaved={reload}
        />
      )}
      {dialog?.kind === "edit" && (
        <ProjectEntryDialog
          projectId={project.id}
          members={members}
          entry={dialog.entry}
          onClose={() => setDialog(null)}
          onSaved={reload}
        />
      )}
    </div>
  );
}
