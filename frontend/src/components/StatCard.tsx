import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import "./StatCard.css";

interface StatCardProps {
  icon: LucideIcon;
  tone: "neutral" | "positive";
  value: ReactNode;
  suffix?: ReactNode;
  label: string;
}

export function StatCard({ icon: Icon, tone, value, suffix, label }: StatCardProps) {
  return (
    <div className="stat-card">
      <div className="stat-card__top">
        <span className="stat-card__label">{label}</span>
        <span className={`stat-card__icon stat-card__icon--${tone}`}>
          <Icon size={14} strokeWidth={1.75} aria-hidden="true" />
        </span>
      </div>
      <span className="stat-card__value">
        {value}
        {suffix && <span className="stat-card__suffix">{suffix}</span>}
      </span>
    </div>
  );
}
