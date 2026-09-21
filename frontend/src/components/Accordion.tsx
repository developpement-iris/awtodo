import { ChevronDown } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { createContext, useContext, useState, type ReactNode } from "react";
import "./Accordion.css";

// Idée reprise d'un snippet Base UI fourni (Accordion), réécrite aux
// conventions du repo : pas de Tailwind, pas de `@/components/base-ui/*`,
// pas de Radix — même composition (Accordion / AccordionItem /
// AccordionTrigger / AccordionContent), rendu et anim maison (`motion`,
// déjà une dépendance, même patron que `TaskAccordion`).

interface AccordionContextValue {
  openValues: Set<string>;
  toggle: (value: string) => void;
}

const AccordionContext = createContext<AccordionContextValue | null>(null);

interface AccordionProps {
  /** "multiple" (défaut) : plusieurs sections ouvertes à la fois — "single" : une seule. */
  type?: "single" | "multiple";
  defaultValue?: string[];
  /** Mode contrôlé (ex. `SpecTab` : ouvrir/fermer EST l'action d'inclure/
   * exclure une section du cahier des charges, l'état vit côté serveur) —
   * fournir `value`+`onValueChange` ensemble, sinon l'accordéon gère son
   * propre état (mode non contrôlé, ex. le panneau "À planifier" du
   * planning). */
  value?: string[];
  onValueChange?: (next: string[]) => void;
  className?: string;
  children: ReactNode;
}

export function Accordion({
  type = "multiple",
  defaultValue = [],
  value,
  onValueChange,
  className,
  children,
}: AccordionProps) {
  const [internalValues, setInternalValues] = useState<Set<string>>(new Set(defaultValue));
  const controlled = value !== undefined;
  const openValues = controlled ? new Set(value) : internalValues;

  function toggle(item: string) {
    const next = new Set(openValues);
    if (next.has(item)) {
      next.delete(item);
    } else {
      if (type === "single") next.clear();
      next.add(item);
    }
    if (controlled) {
      onValueChange?.(Array.from(next));
    } else {
      setInternalValues(next);
    }
  }

  return (
    <AccordionContext.Provider value={{ openValues, toggle }}>
      <div className={`accordion${className ? ` ${className}` : ""}`}>{children}</div>
    </AccordionContext.Provider>
  );
}

interface AccordionItemContextValue {
  value: string;
  open: boolean;
}

const AccordionItemContext = createContext<AccordionItemContextValue | null>(null);

interface AccordionItemProps {
  value: string;
  className?: string;
  children: ReactNode;
}

export function AccordionItem({ value, className, children }: AccordionItemProps) {
  const ctx = useContext(AccordionContext);
  if (!ctx) throw new Error("AccordionItem doit être utilisé à l'intérieur de <Accordion>.");
  const open = ctx.openValues.has(value);

  return (
    <AccordionItemContext.Provider value={{ value, open }}>
      <div className={`accordion-item${open ? " accordion-item--open" : ""}${className ? ` ${className}` : ""}`}>
        {children}
      </div>
    </AccordionItemContext.Provider>
  );
}

function useAccordionItem(name: string) {
  const accordionCtx = useContext(AccordionContext);
  const itemCtx = useContext(AccordionItemContext);
  if (!accordionCtx || !itemCtx) {
    throw new Error(`${name} doit être utilisé à l'intérieur de <AccordionItem>.`);
  }
  return { accordionCtx, itemCtx };
}

export function AccordionTrigger({ children, className }: { children: ReactNode; className?: string }) {
  const { accordionCtx, itemCtx } = useAccordionItem("AccordionTrigger");
  return (
    <button
      type="button"
      className={`accordion-trigger${className ? ` ${className}` : ""}`}
      onClick={() => accordionCtx.toggle(itemCtx.value)}
      aria-expanded={itemCtx.open}
    >
      <span className="accordion-trigger__label">{children}</span>
      <ChevronDown
        size={15}
        strokeWidth={1.75}
        className={`accordion-trigger__chevron${itemCtx.open ? " accordion-trigger__chevron--open" : ""}`}
        aria-hidden="true"
      />
    </button>
  );
}

export function AccordionContent({ children, className }: { children: ReactNode; className?: string }) {
  const { itemCtx } = useAccordionItem("AccordionContent");
  return (
    <AnimatePresence initial={false}>
      {itemCtx.open && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="accordion-content-wrapper"
        >
          <div className={`accordion-content${className ? ` ${className}` : ""}`}>{children}</div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
