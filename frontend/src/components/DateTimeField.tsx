import { CalendarClock } from "lucide-react";
import { useRef, useState } from "react";
import { DayPicker } from "react-day-picker";
import { AnchoredPanel } from "./AnchoredPanel";
import { DAY_PICKER_CLASS_NAMES } from "./dayPickerClassNames";
import "./DatePickerField.css";
import "./DateTimeField.css";

interface DateTimeFieldProps {
  /** Date-heure locale au format `YYYY-MM-DDTHH:mm` (celui de
   * `<input type="datetime-local">` — inchangé pour les appelants), vide si
   * rien de choisi. */
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  /** Pas des minutes proposé par le champ heure (défaut 5). */
  minuteStep?: number;
}

const DEFAULT_TIME = "09:00";

function splitValue(value: string): { date: string; time: string } {
  const [date = "", time = ""] = value.split("T");
  return { date, time: time.slice(0, 5) };
}

function parseDate(date: string): Date | undefined {
  if (!date) return undefined;
  const [y, m, d] = date.split("-").map(Number);
  if (!y || !m || !d) return undefined;
  return new Date(y, m - 1, d);
}

function toIsoDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/**
 * Remplaçant unifié de `<input type="datetime-local">` : un déclencheur qui
 * ouvre (dans un portail `AnchoredPanel`) un champ heure + un calendrier
 * (react-day-picker, mêmes classes que `DatePickerField`). Émet toujours
 * `YYYY-MM-DDTHH:mm`.
 */
export function DateTimeField({ value, onChange, disabled = false, minuteStep = 5 }: DateTimeFieldProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const { date, time } = splitValue(value);
  const selectedDate = parseDate(date);

  function emit(nextDate: string, nextTime: string) {
    if (!nextDate) return;
    onChange(`${nextDate}T${nextTime || DEFAULT_TIME}`);
  }

  const display = selectedDate
    ? `${selectedDate.toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" })} · ${
        time || DEFAULT_TIME
      }`
    : "";

  return (
    <div className="date-time-field">
      <button
        type="button"
        ref={triggerRef}
        className="date-picker-field__trigger"
        onClick={() => setOpen((current) => !current)}
        disabled={disabled}
        aria-expanded={open}
      >
        <span className={display ? "date-picker-field__value" : "date-picker-field__placeholder"}>
          {display || "Choisir une date et une heure"}
        </span>
        <CalendarClock size={15} strokeWidth={1.75} aria-hidden="true" />
      </button>

      {open && (
        <AnchoredPanel
          anchorRef={triggerRef}
          onClose={() => setOpen(false)}
          width="auto"
          className="date-time-field__panel"
        >
          <label className="date-time-field__time">
            Heure
            <input
              type="time"
              step={minuteStep * 60}
              value={time}
              onChange={(event) => emit(date || toIsoDate(new Date()), event.target.value)}
            />
          </label>
          <DayPicker
            mode="single"
            selected={selectedDate}
            defaultMonth={selectedDate}
            onSelect={(picked) => {
              if (picked) emit(toIsoDate(picked), time);
            }}
            classNames={DAY_PICKER_CLASS_NAMES}
            showOutsideDays
          />
        </AnchoredPanel>
      )}
    </div>
  );
}
