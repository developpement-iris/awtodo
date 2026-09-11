import { CirclePlus, FlaskConical, TrendingUp, Wrench, type LucideIcon } from "lucide-react";
import "./TypeBadge.css";

const TASK_TYPE_ICONS: Record<string, LucideIcon> = {
  correction: Wrench,
  ajout: CirclePlus,
  evolution: TrendingUp,
  test: FlaskConical,
};

interface TypeBadgeProps {
  type: string;
  label: string;
}

export function TypeBadge({ type, label }: TypeBadgeProps) {
  const Icon = TASK_TYPE_ICONS[type];

  return (
    <span className="type-badge">
      {Icon && <Icon size={12} strokeWidth={2} aria-hidden="true" />}
      {label}
    </span>
  );
}
