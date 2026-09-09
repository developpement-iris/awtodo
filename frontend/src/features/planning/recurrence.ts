// Construction et description (en français) de règles RRULE iCal, sous-ensemble
// courant. Le backend accepte des RRULE plus riches ; l'éditeur ne produit que
// ce qui est utile pour un agenda interne. Voir docs/modeles-et-api.md >
// "Module Planning".

export type RecurrenceFreq = "none" | "daily" | "weekly" | "monthly" | "yearly";
export type RecurrenceEndMode = "never" | "on" | "after";

export interface RecurrenceForm {
  freq: RecurrenceFreq;
  interval: number;
  weekdays: number[]; // 0 = lundi … 6 = dimanche
  endMode: RecurrenceEndMode;
  until: string; // yyyy-mm-dd
  count: number;
}

export const EMPTY_RECURRENCE: RecurrenceForm = {
  freq: "none",
  interval: 1,
  weekdays: [],
  endMode: "never",
  until: "",
  count: 10,
};

const RRULE_FREQ: Record<Exclude<RecurrenceFreq, "none">, string> = {
  daily: "DAILY",
  weekly: "WEEKLY",
  monthly: "MONTHLY",
  yearly: "YEARLY",
};

const BYDAY = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"];
export const WEEKDAY_LABELS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function untilStamp(dateStr: string): string {
  // Fin de journée locale -> horodatage UTC compact exigé par dateutil quand
  // le DTSTART est timezone-aware.
  const d = new Date(`${dateStr}T23:59:59`);
  return (
    `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}` +
    `T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}${pad(d.getUTCSeconds())}Z`
  );
}

export function buildRrule(form: RecurrenceForm): string {
  if (form.freq === "none") return "";
  const parts = [`FREQ=${RRULE_FREQ[form.freq]}`];
  if (form.interval > 1) parts.push(`INTERVAL=${form.interval}`);
  if (form.freq === "weekly" && form.weekdays.length > 0) {
    parts.push(`BYDAY=${form.weekdays.map((d) => BYDAY[d]).join(",")}`);
  }
  if (form.endMode === "on" && form.until) parts.push(`UNTIL=${untilStamp(form.until)}`);
  if (form.endMode === "after" && form.count > 0) parts.push(`COUNT=${form.count}`);
  return parts.join(";");
}

function parseParam(rule: string, key: string): string | null {
  const match = rule.split(";").find((p) => p.startsWith(`${key}=`));
  return match ? match.slice(key.length + 1) : null;
}

export function parseRrule(rule: string): RecurrenceForm {
  if (!rule) return { ...EMPTY_RECURRENCE };
  const freqRaw = parseParam(rule, "FREQ");
  const freq =
    (Object.entries(RRULE_FREQ).find(([, v]) => v === freqRaw)?.[0] as RecurrenceFreq | undefined) ?? "none";
  const byday = parseParam(rule, "BYDAY");
  const until = parseParam(rule, "UNTIL");
  const count = parseParam(rule, "COUNT");
  return {
    freq,
    interval: Number(parseParam(rule, "INTERVAL") ?? 1) || 1,
    weekdays: byday
      ? byday.split(",").map((d) => BYDAY.indexOf(d)).filter((i) => i >= 0)
      : [],
    endMode: until ? "on" : count ? "after" : "never",
    until: until ? `${until.slice(0, 4)}-${until.slice(4, 6)}-${until.slice(6, 8)}` : "",
    count: Number(count ?? 10) || 10,
  };
}

const FREQ_NOUN: Record<Exclude<RecurrenceFreq, "none">, [string, string]> = {
  daily: ["jour", "jours"],
  weekly: ["semaine", "semaines"],
  monthly: ["mois", "mois"],
  yearly: ["an", "ans"],
};

export function describeRrule(rule: string): string {
  const form = parseRrule(rule);
  if (form.freq === "none") return "Ne se répète pas";
  const [singular, plural] = FREQ_NOUN[form.freq];
  let base =
    form.interval > 1 ? `Tous les ${form.interval} ${plural}` : `Toutes les ${singular}`;
  if (form.freq === "daily") base = form.interval > 1 ? `Tous les ${form.interval} jours` : "Tous les jours";
  if (form.freq === "monthly") base = form.interval > 1 ? `Tous les ${form.interval} mois` : "Tous les mois";
  if (form.freq === "yearly") base = form.interval > 1 ? `Tous les ${form.interval} ans` : "Tous les ans";
  if (form.freq === "weekly" && form.weekdays.length > 0) {
    base += `, le ${form.weekdays.map((d) => WEEKDAY_LABELS[d].toLowerCase()).join(", ")}`;
  }
  if (form.endMode === "on" && form.until) base += ` jusqu'au ${form.until.split("-").reverse().join("/")}`;
  if (form.endMode === "after" && form.count > 0) base += ` (${form.count} occurrences)`;
  return base;
}
