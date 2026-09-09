import { Home } from "lucide-react";
import "./Breadcrumb.css";

export interface BreadcrumbItem {
  label: string;
  onClick?: () => void;
}

interface BreadcrumbProps {
  items: BreadcrumbItem[];
}

export function Breadcrumb({ items }: BreadcrumbProps) {
  if (items.length === 0) return null;

  return (
    <nav className="breadcrumb" aria-label="Fil d'Ariane">
      {items.map((item, index) => {
        const isFirst = index === 0;
        const isLast = index === items.length - 1;
        return (
          <span key={item.label} className="breadcrumb__segment">
            {!isFirst && (
              <span className="breadcrumb__sep" aria-hidden="true">
                /
              </span>
            )}
            {item.onClick && !isLast ? (
              <button type="button" className="breadcrumb__item" onClick={item.onClick}>
                {isFirst && <Home size={13} strokeWidth={1.75} aria-hidden="true" />}
                {item.label}
              </button>
            ) : (
              <span className="breadcrumb__item breadcrumb__item--active" aria-current="page">
                {isFirst && <Home size={13} strokeWidth={1.75} aria-hidden="true" />}
                {item.label}
              </span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
