import { type ReactNode, type RefObject, useLayoutEffect, useState } from "react";
import { createPortal } from "react-dom";

interface AnchoredPanelProps {
  /** Élément sous lequel ancrer le panneau. */
  anchorRef: RefObject<HTMLElement | null>;
  onClose: () => void;
  children: ReactNode;
  /** Largeur du panneau : `anchor` = celle du déclencheur (défaut), `auto` = contenu. */
  width?: "anchor" | "auto";
  className?: string;
}

const MARGIN = 4;

/**
 * Panneau flottant rendu dans un portail (`position: fixed`) et positionné
 * sous son ancre — s'affranchit de tout `overflow` d'un dialogue parent
 * (contrairement à un simple `position: absolute`). Bascule au-dessus si la
 * place manque en bas. Ferme au clic extérieur et à Échap.
 */
export function AnchoredPanel({ anchorRef, onClose, children, width = "anchor", className }: AnchoredPanelProps) {
  const [style, setStyle] = useState<React.CSSProperties | null>(null);

  useLayoutEffect(() => {
    const anchor = anchorRef.current;
    if (!anchor) return;

    function place() {
      const rect = anchor!.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      const openUp = spaceBelow < 260 && rect.top > spaceBelow;
      const next: React.CSSProperties = {
        position: "fixed",
        left: Math.max(MARGIN, Math.min(rect.left, window.innerWidth - rect.width - MARGIN)),
        maxHeight: `${Math.max(160, (openUp ? rect.top : spaceBelow) - MARGIN * 2)}px`,
      };
      if (width === "anchor") next.width = rect.width;
      else next.maxWidth = `${window.innerWidth - 2 * MARGIN}px`;
      if (openUp) next.bottom = window.innerHeight - rect.top + MARGIN;
      else next.top = rect.bottom + MARGIN;
      setStyle(next);
    }

    place();
    const handler = () => place();
    window.addEventListener("resize", handler);
    window.addEventListener("scroll", handler, true);
    return () => {
      window.removeEventListener("resize", handler);
      window.removeEventListener("scroll", handler, true);
    };
  }, [anchorRef, width]);

  useLayoutEffect(() => {
    function onPointerDown(event: PointerEvent) {
      const target = event.target as Node;
      if (anchorRef.current?.contains(target)) return;
      if ((target as HTMLElement).closest?.("[data-anchored-panel]")) return;
      onClose();
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown, true);
      document.removeEventListener("keydown", onKeyDown, true);
    };
  }, [anchorRef, onClose]);

  if (!style) return null;

  return createPortal(
    <div data-anchored-panel className={className} style={style}>
      {children}
    </div>,
    document.body,
  );
}
