import { Check, ListFilter } from "lucide-react";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import { useEffect, useRef, useState } from "react";
import type { StatusFilterOption } from "../lib/statusFilterOptions";
import "./StatusFilterDropdown.css";

interface StatusFilterDropdownProps {
  options: StatusFilterOption[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
}

// Habillage "filter disclosure" (Watermelon UI, adapté) : bouton rond qui se
// déplie en panneau via une transition d'élément partagé (layoutId), plutôt
// qu'un simple dropdown. Le vrai composant est à sélection unique et se
// referme au choix — ici les filtres restent multi-sélection (le
// comportement de filtrage ne change pas), seul le panneau ne se ferme donc
// pas automatiquement, uniquement au clic extérieur.
export function StatusFilterDropdown({ options, selected, onChange }: StatusFilterDropdownProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function toggle(value: string) {
    const next = new Set(selected);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    onChange(next);
  }

  const activeCount = options.filter((option) => selected.has(option.value)).length;

  return (
    <div className="status-filter-dropdown" ref={containerRef}>
      <MotionConfig transition={{ type: "spring", bounce: 0.25, duration: 0.5 }}>
        <AnimatePresence initial={false}>
          {open ? (
            <motion.div
              key="open"
              layoutId="status-filter-disclosure"
              style={{ borderRadius: 10 }}
              className="status-filter-dropdown__panel"
              role="group"
              aria-label="Filtrer par statut"
            >
              {options.map((option) => {
                const isSelected = selected.has(option.value);
                return (
                  <button
                    key={option.value}
                    type="button"
                    className="status-filter-dropdown__option"
                    role="checkbox"
                    aria-checked={isSelected}
                    onClick={() => toggle(option.value)}
                  >
                    <span>{option.label}</span>
                    <span
                      className={`status-filter-dropdown__check${isSelected ? " status-filter-dropdown__check--active" : ""}`}
                      aria-hidden="true"
                    >
                      <Check size={11} strokeWidth={3} />
                    </span>
                  </button>
                );
              })}
            </motion.div>
          ) : (
            <motion.button
              key="closed"
              type="button"
              layoutId="status-filter-disclosure"
              style={{ borderRadius: 20 }}
              className="status-filter-dropdown__trigger"
              onClick={() => setOpen(true)}
              aria-expanded={open}
              aria-label="Filtrer par statut"
            >
              <ListFilter size={16} strokeWidth={1.75} aria-hidden="true" />
              {activeCount > 0 && <span className="status-filter-dropdown__count">{activeCount}</span>}
            </motion.button>
          )}
        </AnimatePresence>
      </MotionConfig>
    </div>
  );
}
