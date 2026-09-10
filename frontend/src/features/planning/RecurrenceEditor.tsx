import { Combobox } from "../../components/Combobox";
import {
  WEEKDAY_LABELS,
  type RecurrenceForm,
  type RecurrenceFreq,
} from "./recurrence";

interface RecurrenceEditorProps {
  value: RecurrenceForm;
  onChange: (value: RecurrenceForm) => void;
}

const FREQ_OPTIONS: { value: RecurrenceFreq; label: string }[] = [
  { value: "none", label: "Ne se répète pas" },
  { value: "daily", label: "Tous les jours" },
  { value: "weekly", label: "Toutes les semaines" },
  { value: "monthly", label: "Tous les mois" },
  { value: "yearly", label: "Tous les ans" },
];

export function RecurrenceEditor({ value, onChange }: RecurrenceEditorProps) {
  function patch(next: Partial<RecurrenceForm>) {
    onChange({ ...value, ...next });
  }

  function toggleWeekday(index: number) {
    const set = new Set(value.weekdays);
    if (set.has(index)) set.delete(index);
    else set.add(index);
    patch({ weekdays: [...set].sort((a, b) => a - b) });
  }

  return (
    <div className="recurrence-editor">
      <label className="planning-field">
        <span>Récurrence</span>
        <Combobox
          options={FREQ_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
          value={value.freq}
          onChange={(v) => patch({ freq: v as RecurrenceFreq })}
          clearable={false}
        />
      </label>

      {value.freq !== "none" && (
        <>
          <label className="planning-field">
            <span>Tous les</span>
            <input
              type="number"
              min={1}
              max={99}
              value={value.interval}
              onChange={(e) => patch({ interval: Math.max(1, Number(e.target.value) || 1) })}
            />
          </label>

          {value.freq === "weekly" && (
            <div className="recurrence-editor__weekdays">
              {WEEKDAY_LABELS.map((label, index) => (
                <button
                  key={label}
                  type="button"
                  className={`recurrence-editor__weekday${
                    value.weekdays.includes(index) ? " recurrence-editor__weekday--on" : ""
                  }`}
                  onClick={() => toggleWeekday(index)}
                >
                  {label}
                </button>
              ))}
            </div>
          )}

          <fieldset className="recurrence-editor__end">
            <legend>Fin</legend>
            <label>
              <input
                type="radio"
                name="recurrence-end"
                checked={value.endMode === "never"}
                onChange={() => patch({ endMode: "never" })}
              />
              Jamais
            </label>
            <label>
              <input
                type="radio"
                name="recurrence-end"
                checked={value.endMode === "on"}
                onChange={() => patch({ endMode: "on" })}
              />
              Le
              <input
                type="date"
                value={value.until}
                disabled={value.endMode !== "on"}
                onChange={(e) => patch({ until: e.target.value })}
              />
            </label>
            <label>
              <input
                type="radio"
                name="recurrence-end"
                checked={value.endMode === "after"}
                onChange={() => patch({ endMode: "after" })}
              />
              Après
              <input
                type="number"
                min={1}
                max={365}
                value={value.count}
                disabled={value.endMode !== "after"}
                onChange={(e) => patch({ count: Math.max(1, Number(e.target.value) || 1) })}
              />
              occurrences
            </label>
          </fieldset>
        </>
      )}
    </div>
  );
}
