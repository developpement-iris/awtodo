import { Check } from "lucide-react";
import "./Checkbox.css";

export type CheckboxSize = "sm" | "md" | "lg";

const ICON_SIZE: Record<CheckboxSize, number> = { sm: 11, md: 14, lg: 16 };

interface CheckboxProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  /** sm ≈ 16px (défaut), md ≈ 20px, lg ≈ 24px. */
  size?: CheckboxSize;
  id?: string;
  className?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
}

/**
 * Checkbox unique du site (voir docs/charte-graphique.md > "Checkbox").
 * Enveloppe un `<input type="checkbox">` réel (masqué visuellement mais garde
 * clavier/focus/sémantique de formulaire) et une case stylée aux jetons du
 * thème — état coché = `--color-accent` (brique), pas de couleur hors palette.
 */
export function Checkbox({
  checked,
  onCheckedChange,
  disabled = false,
  size = "sm",
  id,
  className,
  "aria-label": ariaLabel,
  "aria-labelledby": ariaLabelledBy,
}: CheckboxProps) {
  return (
    <span className={`checkbox checkbox--${size}${className ? ` ${className}` : ""}`}>
      <input
        type="checkbox"
        className="checkbox__input"
        id={id}
        checked={checked}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledBy}
        onChange={(event) => onCheckedChange(event.target.checked)}
      />
      <span className="checkbox__box" aria-hidden="true">
        <Check size={ICON_SIZE[size]} strokeWidth={3} />
      </span>
    </span>
  );
}
