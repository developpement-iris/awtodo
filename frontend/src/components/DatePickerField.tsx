import { Calendar as CalendarIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { DayPicker } from "react-day-picker";
import { DAY_PICKER_CLASS_NAMES } from "./dayPickerClassNames";
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

function toDisplay(value: string): string {
  const date = parseIsoDate(value);
  if (!date) return "";
  return `${String(date.getDate()).padStart(2, "0")}/${String(date.getMonth() + 1).padStart(2, "0")}/${date.getFullYear()}`;
}

// Masque de saisie jj/mm/aaaa : on ne garde que les chiffres (8 max) et on
// insère les barres — taper "03112026" donne "03/11/2026".
function maskDigits(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

/** `jj/mm/aaaa` → ISO, ou `null` si incomplet / date inexistante (31/02…). */
function parseTyped(text: string): string | null {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(text);
  if (!match) return null;
  const [day, month, year] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
  return toIsoDate(date);
}

// Champ date : saisie clavier jj/mm/aaaa (session du 2026-11-03) OU choix
// au calendrier (bouton icône). La valeur n'est transmise que lorsqu'une date
// complète et valide est tapée ; une saisie invalide est annulée en quittant
// le champ, un champ vidé efface la date.
export function DatePickerField({ value, onChange, placeholder = "jj/mm/aaaa", disabled = false }: DatePickerFieldProps) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(() => toDisplay(value));
  const containerRef = useRef<HTMLDivElement>(null);
  const selectedDate = parseIsoDate(value);
  const invalid = text.length === 10 && parseTyped(text) === null;

  useEffect(() => {
    setText(toDisplay(value));
  }, [value]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleType(raw: string) {
    const masked = maskDigits(raw);
    setText(masked);
    if (masked === "") {
      if (value) onChange("");
      return;
    }
    const iso = parseTyped(masked);
    if (iso && iso !== value) onChange(iso);
  }

  function handleBlur() {
    // Saisie incomplète ou invalide : retour à la dernière date valide.
    if (text && parseTyped(text) === null) setText(toDisplay(value));
  }

  return (
    <div className={`date-picker-field${invalid ? " date-picker-field--invalid" : ""}`} ref={containerRef}>
      <div className="date-picker-field__control">
        <input
          type="text"
          inputMode="numeric"
          className="date-picker-field__input"
          value={text}
          placeholder={placeholder}
          onChange={(event) => handleType(event.target.value)}
          onBlur={handleBlur}
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false);
          }}
          disabled={disabled}
          aria-invalid={invalid || undefined}
          aria-label="Date (jj/mm/aaaa)"
        />
        <button
          type="button"
          className="date-picker-field__toggle"
          onClick={() => setOpen((current) => !current)}
          disabled={disabled}
          aria-expanded={open}
          aria-label="Ouvrir le calendrier"
        >
          <CalendarIcon size={15} strokeWidth={1.75} aria-hidden="true" />
        </button>
      </div>

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
            classNames={DAY_PICKER_CLASS_NAMES}
            showOutsideDays
          />
        </div>
      )}
    </div>
  );
}
