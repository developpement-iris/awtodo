import { Check, ImagePlus, Loader2 } from "lucide-react";
import { useRef, useState } from "react";
import { compressImage } from "../../lib/imageCompress";
import { PROJECT_COVER_IMAGES } from "../../lib/projectCovers";
import type { Project } from "../../types/watodo";
import { ProjectCover } from "./ProjectCover";
import "./CoverPicker.css";

interface CoverPickerProps {
  /** Sert à prévisualiser les options (teinte des initiales, image déjà importée). */
  project: Pick<Project, "id" | "name" | "cover_updated_at">;
  value: string;
  onChange: (value: string) => void;
  /** Reçoit l'image déjà compressée. Absent = pas d'import proposé. */
  onImport?: (image: Blob) => Promise<void> | void;
  /** Aperçu local d'une image importée pas encore envoyée (création). */
  pendingPreviewSrc?: string;
}

// Choix de l'image d'illustration : initiales, bibliothèque, ou import.
export function CoverPicker({ project, value, onChange, onImport, pendingPreviewSrc }: CoverPickerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasUpload = Boolean(pendingPreviewSrc || project.cover_updated_at);

  const options = [
    { key: "", label: "Initiales" },
    ...(hasUpload ? [{ key: "upload", label: "Image importée" }] : []),
    ...PROJECT_COVER_IMAGES,
  ];

  async function handleFile(file: File | undefined) {
    if (!file || !onImport) return;
    setImporting(true);
    setError(null);
    try {
      await onImport(await compressImage(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'import a échoué.");
    } finally {
      setImporting(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="cover-picker-wrapper">
      <div className="cover-picker" role="radiogroup" aria-label="Image d'illustration">
        {options.map((option) => {
          const selected = value === option.key;
          return (
            <button
              key={option.key || "monogram"}
              type="button"
              role="radio"
              aria-checked={selected}
              className={`cover-picker__option${selected ? " cover-picker__option--selected" : ""}`}
              onClick={() => onChange(option.key)}
              title={option.label}
            >
              <ProjectCover
                project={{ ...project, name: project.name || "?", phase: null, cover_image: option.key }}
                previewSrc={option.key === "upload" ? pendingPreviewSrc : undefined}
                size="row"
              />
              <span className="cover-picker__label">{option.label}</span>
              {selected && (
                <span className="cover-picker__check">
                  <Check size={11} strokeWidth={2.5} aria-hidden="true" />
                </span>
              )}
            </button>
          );
        })}

        {onImport && (
          <button
            type="button"
            className="cover-picker__option cover-picker__import"
            onClick={() => inputRef.current?.click()}
            disabled={importing}
          >
            <span className="cover-picker__import-icon">
              {importing ? (
                <Loader2 size={18} strokeWidth={1.75} aria-hidden="true" className="cover-picker__spinner" />
              ) : (
                <ImagePlus size={18} strokeWidth={1.75} aria-hidden="true" />
              )}
            </span>
            <span className="cover-picker__label">{importing ? "Import…" : "Importer"}</span>
          </button>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        onChange={(event) => handleFile(event.target.files?.[0])}
      />
      {error && <p className="cover-picker__error">{error}</p>}
    </div>
  );
}
