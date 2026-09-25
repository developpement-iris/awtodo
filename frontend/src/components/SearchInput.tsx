import { Search, X } from "lucide-react";
import "./SearchInput.css";

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  "aria-label"?: string;
}

// Barre de recherche texte partagée (session du 2026-09-25) — filtre par
// titre sur les écrans Tâches/Incidents, purement côté front sur les données
// déjà chargées (même principe que le tri par colonne, pas de nouveau
// paramètre d'API pour l'instant).
export function SearchInput({ value, onChange, placeholder = "Rechercher…", ...rest }: SearchInputProps) {
  return (
    <label className="search-input">
      <Search size={15} strokeWidth={1.75} aria-hidden="true" className="search-input__icon" />
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={rest["aria-label"] ?? placeholder}
        className="search-input__field"
      />
      {value && (
        <button
          type="button"
          className="search-input__clear"
          onClick={() => onChange("")}
          aria-label="Effacer la recherche"
        >
          <X size={13} strokeWidth={1.75} aria-hidden="true" />
        </button>
      )}
    </label>
  );
}
