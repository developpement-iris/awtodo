import { TASK_TYPE_ICONS } from "../lib/taskTypeIcons";
import type { TaskTypeIcon } from "../types/watodo";
import "./TypeBadge.css";

interface TypeBadgeProps {
  icon: TaskTypeIcon;
  label: string;
}

export function TypeBadge({ icon, label }: TypeBadgeProps) {
  const Icon = TASK_TYPE_ICONS[icon];

  return (
    <span className="type-badge">
      {Icon && <Icon size={12} strokeWidth={2} aria-hidden="true" />}
      {label}
    </span>
  );
}
