const UNITS: Array<{ limit: number; divisor: number; unit: Intl.RelativeTimeFormatUnit }> = [
  { limit: 60, divisor: 1, unit: "second" },
  { limit: 3600, divisor: 60, unit: "minute" },
  { limit: 86400, divisor: 3600, unit: "hour" },
  { limit: 2592000, divisor: 86400, unit: "day" },
  { limit: 31536000, divisor: 2592000, unit: "month" },
  { limit: Infinity, divisor: 31536000, unit: "year" },
];

const formatter = new Intl.RelativeTimeFormat("fr-FR", { numeric: "auto" });

/** "il y a 4h", "il y a 2 jours" — calculé côté front à partir de created_at, pas de champ backend dédié. */
export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const elapsedSeconds = Math.max(0, (now.getTime() - new Date(iso).getTime()) / 1000);
  const bucket = UNITS.find((entry) => elapsedSeconds < entry.limit) ?? UNITS[UNITS.length - 1];
  const value = Math.max(1, Math.floor(elapsedSeconds / bucket.divisor));
  return formatter.format(-value, bucket.unit);
}
