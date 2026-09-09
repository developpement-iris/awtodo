import { useMemo, type CSSProperties } from "react";
import { addDays, isSameDay, startOfWeek } from "./calendarMath";
import type { CalendarItem } from "./types";

interface MonthGridProps {
  monthDate: Date;
  items: CalendarItem[];
  onDayClick: (day: Date) => void;
  onItemClick: (item: CalendarItem) => void;
}

const WEEKDAY_HEADS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

export function MonthGrid({ monthDate, items, onDayClick, onItemClick }: MonthGridProps) {
  const weeks = useMemo(() => {
    const firstOfMonth = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
    const gridStart = startOfWeek(firstOfMonth);
    return Array.from({ length: 6 }, (_, w) =>
      Array.from({ length: 7 }, (_, d) => addDays(gridStart, w * 7 + d)),
    );
  }, [monthDate]);

  const now = new Date();

  function itemsFor(day: Date): CalendarItem[] {
    return items
      .filter((item) => isSameDay(new Date(item.start), day))
      .sort((a, b) => a.start.localeCompare(b.start));
  }

  return (
    <div className="month-grid">
      <div className="month-grid__heads">
        {WEEKDAY_HEADS.map((label) => (
          <div key={label} className="month-grid__head">
            {label}
          </div>
        ))}
      </div>
      <div className="month-grid__weeks">
        {weeks.map((week, wi) => (
          <div key={wi} className="month-grid__week">
            {week.map((day) => {
              const outside = day.getMonth() !== monthDate.getMonth();
              const dayItems = itemsFor(day);
              return (
                <div
                  key={day.toISOString()}
                  className={`month-grid__cell${outside ? " month-grid__cell--outside" : ""}${
                    isSameDay(day, now) ? " month-grid__cell--today" : ""
                  }`}
                >
                  <button type="button" className="month-grid__daynum" onClick={() => onDayClick(day)}>
                    {day.getDate()}
                  </button>
                  <div className="month-grid__cell-items">
                    {dayItems.slice(0, 3).map((item) => (
                      <button
                        key={item.key}
                        type="button"
                        className={`month-grid__chip month-grid__chip--${item.kind}${
                          item.color ? " month-grid__chip--colored" : ""
                        }`}
                        style={
                          item.color ? ({ "--item-color": item.color } as CSSProperties) : undefined
                        }
                        onClick={() => onItemClick(item)}
                      >
                        {!item.allDay && (
                          <span className="month-grid__chip-time">
                            {new Date(item.start).toLocaleTimeString("fr-FR", {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        )}
                        <span className="month-grid__chip-title">{item.title}</span>
                      </button>
                    ))}
                    {dayItems.length > 3 && (
                      <button type="button" className="month-grid__more" onClick={() => onDayClick(day)}>
                        +{dayItems.length - 3}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
