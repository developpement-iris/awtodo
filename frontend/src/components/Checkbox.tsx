import "./Checkbox.css";

export type CheckboxSize = "sm" | "md" | "lg";

interface CheckboxProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  /** sm (défaut), md, lg. */
  size?: CheckboxSize;
  id?: string;
  className?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
}

/**
 * Interrupteur oui/non unique du site (voir docs/charte-graphique.md >
 * "Interrupteur"). Rendu en **switch carré** — remplace l'ancienne case à
 * cocher (session du 2026-09-10, retour direct). Enveloppe un
 * `<input type="checkbox">` réel (masqué mais garde clavier/focus/sémantique
 * de formulaire) ; l'état activé glisse le curseur et passe la piste sur
 * `--color-accent` (jamais une couleur hors palette).
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
    <span className={`switch switch--${size}${className ? ` ${className}` : ""}`}>
      <input
        type="checkbox"
        role="switch"
        className="switch__input"
        id={id}
        checked={checked}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledBy}
        onChange={(event) => onCheckedChange(event.target.checked)}
      />
      <span className="switch__track" aria-hidden="true">
        <span className="switch__thumb" />
      </span>
    </span>
  );
}
