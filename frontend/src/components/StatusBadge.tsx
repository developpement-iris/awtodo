import type { LucideIcon } from "lucide-react";
import type { Tone } from "../lib/badges";
import "./StatusBadge.css";

interface StatusBadgeProps {
  label: string;
  tone: Tone;
  icon?: LucideIcon;
}

export function StatusBadge({ label, tone, icon: Icon }: StatusBadgeProps) {
  return (
    <span className={`status-badge status-badge--${tone}`}>
      {Icon && <Icon size={12} strokeWidth={2} aria-hidden="true" />}
      {label}
    </span>
  );
}
