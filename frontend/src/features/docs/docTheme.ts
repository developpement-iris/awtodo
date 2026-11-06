import type { CSSProperties } from "react";
import { contrastTextFor, hexToRgb, relativeLuminance } from "../../theme/brandColors";
import type { DocThemeColors } from "../../types/watodo";

// Couleurs par zone de la page publique (session du 2026-11-05). Chaque zone
// redéfinit les jetons en cascade : bordures, code et survols en découlent, et
// une zone sans couleur suit celle qui l'englobe ou le thème du visiteur.
// Partagé avec l'aperçu de l'écran Personnalisation.

type ThemeStyle = CSSProperties & Record<`--${string}`, string>;

// Seuil WCAG pour les éléments d'interface et le texte en gras.
const MIN_ACCENT_CONTRAST = 3;

function inkFor(text: string): string {
  const rgb = hexToRgb(text);
  return rgb ? rgb.join(", ") : "26, 26, 26";
}

function contrastRatio(a: [number, number, number], b: [number, number, number]): number {
  const [light, dark] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

// L'accent est un choix libre : sur une zone où il ne se lirait pas (lien,
// page active), il cède la place à la couleur de texte de cette zone.
function readableAccent(accent: string, zone: [number, number, number], text: string): string | null {
  const accentRgb = hexToRgb(accent);
  return accentRgb && contrastRatio(accentRgb, zone) < MIN_ACCENT_CONTRAST ? text : null;
}

// La couleur de texte choisie prime ; sans elle, calculée selon le fond.
export function resolveZoneText(background: string | undefined, text: string | undefined): string | null {
  if (text && hexToRgb(text)) return text;
  const rgb = background ? hexToRgb(background) : null;
  return rgb ? contrastTextFor(rgb) : null;
}

function textTokens(text: string): ThemeStyle {
  const ink = inkFor(text);
  return {
    color: text,
    "--color-text": text,
    "--color-text-muted": `rgba(${ink}, 0.72)`,
    "--color-text-faint": `rgba(${ink}, 0.55)`,
    "--color-border": `rgba(${ink}, 0.2)`,
    "--tone-neutral-bg": `rgba(${ink}, 0.1)`,
    "--tone-neutral-text": text,
  };
}

function zoneStyle(hex: string | undefined, textColor: string | undefined, accent: string): ThemeStyle {
  const rgb = hex ? hexToRgb(hex) : null;
  const text = resolveZoneText(hex, textColor);
  if (!text) return {};
  const style: ThemeStyle = textTokens(text);
  if (hex && rgb) {
    style.background = hex;
    style["--color-bg"] = hex;
    style["--color-surface"] = `rgba(${inkFor(text)}, 0.06)`;
    const accentOverride = readableAccent(accent, rgb, text);
    if (accentOverride) style["--color-accent"] = accentOverride;
  }
  return style;
}

function tabsStyle(colors: DocThemeColors, accent: string): ThemeStyle {
  const style: ThemeStyle = {};
  // L'onglet actif prend `--color-bg` pour se fondre dans la page en dessous.
  const backgroundRgb = colors.background ? hexToRgb(colors.background) : null;
  if (colors.background && backgroundRgb) {
    style["--color-bg"] = colors.background;
    const pageText = resolveZoneText(colors.background, colors.background_text);
    const accentOverride = pageText ? readableAccent(accent, backgroundRgb, pageText) : null;
    if (accentOverride) style["--color-accent"] = accentOverride;
  }
  if (colors.tabs && hexToRgb(colors.tabs)) style["--sidebar-bg"] = colors.tabs;
  const text = resolveZoneText(colors.tabs, colors.tabs_text);
  if (text) {
    const ink = inkFor(text);
    style["--sidebar-muted"] = `rgba(${ink}, 0.72)`;
    style["--sidebar-active"] = text;
    style["--sidebar-active-bg"] = `rgba(${ink}, 0.14)`;
  }
  return style;
}

export function buildDocTheme(accentColor: string, colors: DocThemeColors) {
  const accentRgb = accentColor ? hexToRgb(accentColor) : null;
  const shell: ThemeStyle =
    accentColor && accentRgb
      ? { "--color-accent": accentColor, "--color-accent-contrast": contrastTextFor(accentRgb) }
      : {};
  const accent = accentColor || getComputedStyle(document.documentElement).getPropertyValue("--color-accent").trim();
  return {
    shell,
    tabs: tabsStyle(colors, accent),
    main: zoneStyle(colors.background, colors.background_text, accent),
    sidebar: zoneStyle(colors.sidebar, colors.sidebar_text, accent),
    content: zoneStyle(colors.content, colors.content_text, accent),
    header: zoneStyle(colors.header, colors.header_text, accent),
    footer: zoneStyle(colors.footer, colors.footer_text, accent),
  };
}
