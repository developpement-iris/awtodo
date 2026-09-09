import { motion } from "motion/react";
import { useState } from "react";
import "./SectionSidebar.css";

interface SectionSidebarItem<T extends string> {
  id: T;
  label: string;
}

interface SectionSidebarProps<T extends string> {
  items: SectionSidebarItem<T>[];
  activeId: T;
  onSelect: (id: T) => void;
  ariaLabel: string;
}

// Highlight de survol qui glisse d'un item à l'autre (habillage "macOS
// sidebar" adapté, transition d'élément partagé via layoutId) — pas de mode
// replié ni d'icônes (tranché : les items n'en ont pas), seule cette couche
// d'animation s'ajoute par-dessus le panneau existant.
export function SectionSidebar<T extends string>({ items, activeId, onSelect, ariaLabel }: SectionSidebarProps<T>) {
  const [hoveredId, setHoveredId] = useState<T | null>(null);

  return (
    <nav className="section-sidebar" aria-label={ariaLabel} onMouseLeave={() => setHoveredId(null)}>
      <ul className="section-sidebar__list">
        {items.map(({ id, label }) => (
          <li key={id}>
            <button
              type="button"
              role="tab"
              aria-selected={activeId === id}
              className={`section-sidebar__item${activeId === id ? " section-sidebar__item--active" : ""}`}
              onClick={() => onSelect(id)}
              onMouseEnter={() => setHoveredId(id)}
            >
              {hoveredId === id && activeId !== id && (
                <motion.span
                  layoutId="section-sidebar-hover"
                  className="section-sidebar__hover"
                  transition={{ type: "spring", stiffness: 350, damping: 30 }}
                />
              )}
              <span className="section-sidebar__label">{label}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
