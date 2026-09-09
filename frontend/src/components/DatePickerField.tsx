import { Calendar as CalendarIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { DayPicker, type ClassNames } from "react-day-picker";
import "./DatePickerField.css";

interface DatePickerFieldProps {
  /** Date ISO `yyyy-mm-dd` (format déjà utilisé par les payloads API), chaîne
   * vide si aucune date choisie. */
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

function parseIsoDate(value: string): Date | undefined {
  if (!value) return undefined;
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return undefined;
  return new Date(year, month - 1, day);
}

// Construit à partir des parties locales de la date (pas `toISOString()`,
// qui convertit en UTC et peut décaler d'un jour selon le fuseau).
function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

// Pas d'import du CSS par défaut de react-day-picker : classNames custom
// pointant vers nos propres classes (voir DatePickerField.css, écrit avec
// les tokens du projet) plutôt que de neutraliser leur feuille de style.
const CLASS_NAMES: Partial<ClassNames> = {
  root: "date-picker-field__calendar",
  months: "date-picker-field__months",
  month: "date-picker-field__month",
  month_caption: "date-picker-field__caption",
  caption_label: "date-picker-field__caption-label",
  nav: "date-picker-field__nav",
  button_previous: "date-picker-field__nav-button",
  button_next: "date-picker-field__nav-button",
  month_grid: "date-picker-field__grid",
  weekdays: "date-picker-field__weekdays",
  weekday: "date-picker-field__weekday",
  week: "date-picker-field__week",
  day: "date-picker-field__day",
  day_button: "date-picker-field__day-button",
  selected: "date-picker-field__day-button--selected",
  today: "date-picker-field__day-button--today",
  outside: "date-picker-field__day-button--outside",
  disabled: "date-picker-field__day-button--disabled",
};

// Habillage "date-picker-4" (Watermelon UI) adapté : champ + icône qui ouvre
// un calendrier en popover. Contrairement au composant source, la saisie
// manuelle de texte libre n'est pas reprise (fragile à parser) — le champ
// est un simple déclencheur, toute la saisie passe par le calendrier.
export function DatePickerField({ value, onChange, placeholder = "Choisir une date", disabled = false }: DatePickerFieldProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const selectedDate = parseIsoDate(value);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const displayValue = selectedDate
    ? selectedDate.toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" })
    : "";

  return (
    <div className="date-picker-field" ref={containerRef}>
      <button
        type="button"
        className="date-picker-field__trigger"
        onClick={() => setOpen((current) => !current)}
        disabled={disabled}
        aria-expanded={open}
      >
        <span className={displayValue ? "date-picker-field__value" : "date-picker-field__placeholder"}>
          {displayValue || placeholder}
        </span>
        <CalendarIcon size={15} strokeWidth={1.75} aria-hidden="true" />
      </button>

      {open && (
        <div className="date-picker-field__panel">
          <DayPicker
            mode="single"
            selected={selectedDate}
            defaultMonth={selectedDate}
            onSelect={(date) => {
              if (date) {
                onChange(toIsoDate(date));
                setOpen(false);
              }
            }}
            classNames={CLASS_NAMES}
            showOutsideDays
          />
        </div>
      )}
    </div>
  );
}
