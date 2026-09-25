import { useDraggable, useDroppable } from "@dnd-kit/core";
import { useMemo } from "react";
import type { WorkingHoursDay } from "../../types/watodo";
import {
  GRID_END_HOUR,
  GRID_START_HOUR,
  HOUR_HEIGHT,
  PX_PER_MINUTE,
  clampMinutes,
  formatHour,
  formatTimeRange,
  gridHours,
  gridSlots,
  isoWeekday,
  isSameDay,
  minutesToOffset,
  snapMinutes,
  snapOffset,
  toIsoDate,
  weekDays,
} from "./calendarMath";
import type { CalendarItem } from "./types";

function minutesFromMidnight(iso: string): number {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

function hmToMinutes(hm: string): number {
  const [h, m] = hm.split(":").map(Number);
  return h * 60 + m;
}

interface DayColumnProps {
  day: Date;
  items: CalendarItem[];
  now: Date;
  /** Minutes depuis minuit du cran survolé pendant un glissé (aperçu). */
  previewMinutes: number | null;
  /** Horaires de travail des 7 jours (index 0 = lundi), ou `null` tant que
   * non chargées — pas de grisage plutôt qu'un défaut arbitraire. */
  workHours: WorkingHoursDay[] | null;
  onItemClick: (item: CalendarItem) => void;
  onEmptyClick?: (dayIso: string, minutes: number) => void;
}

function ItemBlock({
  item,
  onItemClick,
}: {
  item: CalendarItem;
  onItemClick: (item: CalendarItem) => void;
}) {
  const startMin = minutesFromMidnight(item.start);
  const endMin = Math.max(startMin + 15, minutesFromMidnight(item.end));
  const top = minutesToOffset(startMin);
  const height = (endMin - startMin) * (HOUR_HEIGHT / 60);

  const move = useDraggable({
    id: `move:${item.key}`,
    data: { type: "move", item },
    disabled: !item.editable,
  });
  const resize = useDraggable({
    id: `resize:${item.key}`,
    data: { type: "resize", item },
    disabled: !item.editable,
  });

  // Deux activateurs frères (jamais imbriqués) : le bouton interne pour
  // « déplacer », la poignée du bas pour « redimensionner ». Le déplacement
  // translate tout le bloc ; le redimensionnement n'agit que sur la hauteur.
  // Le décalage vertical est aligné en direct sur les crans de 30 min (le
  // drop l'était déjà via `snapMinutes` — ici c'est le retour visuel pendant
  // le glissé qui « accroche » cran par cran).
  const resizeDelta = resize.isDragging ? snapOffset(resize.transform?.y ?? 0) : 0;
  const style: React.CSSProperties = {
    top: `${Math.max(0, top)}px`,
    height: `${Math.max(18, height + resizeDelta)}px`,
    transform: move.transform
      ? `translate3d(${move.transform.x}px, ${snapOffset(move.transform.y)}px, 0)`
      : undefined,
  };
  if (item.color) {
    (style as Record<string, string>)["--item-color"] = item.color;
  }

  return (
    <div
      ref={move.setNodeRef}
      className={`week-grid__item week-grid__item--${item.kind}${item.color ? " week-grid__item--colored" : ""}${
        item.editable ? "" : " week-grid__item--readonly"
      }${move.isDragging || resize.isDragging ? " week-grid__item--dragging" : ""}`}
      style={style}
    >
      <button
        type="button"
        className="week-grid__item-hit"
        onClick={() => onItemClick(item)}
        title={`${item.title}${item.subtitle ? ` — ${item.subtitle}` : ""} (${formatTimeRange(item.start, item.end)})`}
        {...(item.editable ? move.listeners : {})}
        {...(item.editable ? move.attributes : {})}
      >
        <span className="week-grid__item-time">{formatTimeRange(item.start, item.end)}</span>
        <span className="week-grid__item-title">{item.title}</span>
        {item.subtitle && <span className="week-grid__item-subtitle">{item.subtitle}</span>}
      </button>
      {item.editable && (
        <span
          ref={resize.setNodeRef}
          className="week-grid__item-resize"
          {...resize.listeners}
          {...resize.attributes}
          aria-hidden="true"
        />
      )}
    </div>
  );
}

function DayColumn({ day, items, now, previewMinutes, workHours, onItemClick, onEmptyClick }: DayColumnProps) {
  const iso = toIsoDate(day);
  const { setNodeRef, isOver } = useDroppable({ id: `day:${iso}` });
  const isToday = isSameDay(day, now);
  const nowOffset = isToday ? minutesToOffset(now.getHours() * 60 + now.getMinutes()) : null;
  const gridHeight = (GRID_END_HOUR - GRID_START_HOUR) * HOUR_HEIGHT;
  const gridStartMin = GRID_START_HOUR * 60;
  const gridEndMin = GRID_END_HOUR * 60;
  const dayWorkHours = workHours ? workHours[isoWeekday(day)] : null;

  const dayItems = items.filter((item) => isSameDay(new Date(item.start), day) && !item.allDay);

  function handleBackgroundClick(e: React.MouseEvent<HTMLDivElement>) {
    if (!onEmptyClick || e.target !== e.currentTarget) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const minutes = clampMinutes(
      snapMinutes((e.clientY - rect.top) / PX_PER_MINUTE + GRID_START_HOUR * 60),
    );
    onEmptyClick(iso, minutes);
  }

  return (
    <div
      ref={setNodeRef}
      data-planning-day={iso}
      className={`week-grid__col${isOver ? " week-grid__col--over" : ""}`}
      style={{ height: `${gridHeight}px` }}
      onClick={handleBackgroundClick}
    >
      {dayWorkHours && !dayWorkHours.enabled && (
        <div className="week-grid__offhours" style={{ top: 0, height: `${gridHeight}px` }} aria-hidden="true" />
      )}
      {dayWorkHours && dayWorkHours.enabled && (
        <>
          {hmToMinutes(dayWorkHours.start) > gridStartMin && (
            <div
              className="week-grid__offhours"
              style={{
                top: 0,
                height: `${minutesToOffset(Math.min(hmToMinutes(dayWorkHours.start), gridEndMin))}px`,
              }}
              aria-hidden="true"
            />
          )}
          {hmToMinutes(dayWorkHours.end) < gridEndMin && (
            <div
              className="week-grid__offhours"
              style={{
                top: `${minutesToOffset(Math.max(hmToMinutes(dayWorkHours.end), gridStartMin))}px`,
                height: `${gridHeight - minutesToOffset(Math.max(hmToMinutes(dayWorkHours.end), gridStartMin))}px`,
              }}
              aria-hidden="true"
            />
          )}
        </>
      )}
      {gridSlots().map((minutes) => (
        <div
          key={minutes}
          className={`week-grid__slot-line${minutes % 60 === 0 ? " week-grid__slot-line--hour" : ""}`}
          style={{ top: `${minutesToOffset(minutes)}px` }}
        />
      ))}
      {previewMinutes !== null && (
        <div
          className="week-grid__drop-preview"
          style={{ top: `${minutesToOffset(previewMinutes)}px` }}
          aria-hidden="true"
        />
      )}
      {nowOffset !== null && nowOffset >= 0 && nowOffset <= gridHeight && (
        <div className="week-grid__now" style={{ top: `${nowOffset}px` }} />
      )}
      {dayItems.map((item) => (
        <ItemBlock key={item.key} item={item} onItemClick={onItemClick} />
      ))}
    </div>
  );
}

interface WeekGridProps {
  weekStart: Date;
  items: CalendarItem[];
  /** Cible du glissé en cours : jour + cran de 30 min survolé. */
  dropPreview?: { dayIso: string; minutes: number } | null;
  /** Horaires de travail de la semaine affichée (7 jours, base ou exception
   * — voir docs/organisation-et-comptes.md > "Personnalisation du
   * planning"). `null` tant que non chargées : pas de grisé plutôt qu'un
   * défaut arbitraire pendant le chargement. */
  workHours?: WorkingHoursDay[] | null;
  onItemClick: (item: CalendarItem) => void;
  onEmptyClick?: (dayIso: string, minutes: number) => void;
}

export function WeekGrid({
  weekStart,
  items,
  dropPreview,
  workHours = null,
  onItemClick,
  onEmptyClick,
}: WeekGridProps) {
  const days = useMemo(() => weekDays(weekStart), [weekStart]);
  const now = new Date();

  const allDayByDay = days.map((day) => items.filter((i) => i.allDay && isSameDay(new Date(i.start), day)));
  const hasAllDay = allDayByDay.some((list) => list.length > 0);

  return (
    <div className="week-grid">
      <div className="week-grid__header">
        <div className="week-grid__gutter" />
        {days.map((day) => (
          <div
            key={day.toISOString()}
            className={`week-grid__day-head${isSameDay(day, now) ? " week-grid__day-head--today" : ""}`}
          >
            {day.toLocaleDateString("fr-FR", { weekday: "short" })}
            <strong>{day.getDate()}</strong>
          </div>
        ))}
      </div>

      {hasAllDay && (
        <div className="week-grid__allday">
          <div className="week-grid__gutter week-grid__gutter--allday">journée</div>
          {allDayByDay.map((list, index) => (
            <div key={index} className="week-grid__allday-cell">
              {list.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`week-grid__chip week-grid__chip--${item.kind}`}
                  onClick={() => onItemClick(item)}
                >
                  {item.title}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}

      <div className="week-grid__body">
        <div className="week-grid__gutter week-grid__gutter--hours">
          {gridHours().map((hour) => (
            <div key={hour} className="week-grid__hour-label" style={{ top: `${minutesToOffset(hour * 60)}px` }}>
              {formatHour(hour)}
            </div>
          ))}
        </div>
        {days.map((day) => (
          <DayColumn
            key={day.toISOString()}
            day={day}
            items={items}
            now={now}
            previewMinutes={dropPreview && dropPreview.dayIso === toIsoDate(day) ? dropPreview.minutes : null}
            workHours={workHours}
            onItemClick={onItemClick}
            onEmptyClick={onEmptyClick}
          />
        ))}
      </div>
    </div>
  );
}
