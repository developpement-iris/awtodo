import type { CSSProperties } from "react";
import { contrastTextFor, hexToRgb, relativeLuminance } from "../../theme/brandColors";
import type { DocThemeColors } from "../../types/watodo";

// Couleurs par zone de la page publique (session du 2026-11-05). Chaque zone
// redéfinit les jetons en cascade : le texte, les bordures et le code s'y
// adaptent seuls, et une zone sans couleur suit celle qui l'englobe ou le
// thème du visiteur. Partagé avec l'aperçu de l'écran Personnalisation.

type ThemeStyle = CSSProperties & Record<`--${string}`, string>;

// Seuil WCAG pour les éléments d'interface et le texte en gras.
const MIN_ACCENT_CONTRAST = 3;

function inkFor(text: string): string {
  return text === "#FFFFFF" ? "255, 255, 255" : "26, 26, 26";
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

function zoneStyle(hex: string | undefined, accent: string): ThemeStyle {
  const rgb = hex ? hexToRgb(hex) : null;
  if (!hex || !rgb) return {};
  const text = contrastTextFor(rgb);
  const ink = inkFor(text);
  const accentOverride = readableAccent(accent, rgb, text);
  return {
    background: hex,
    color: text,
    "--color-bg": hex,
    "--color-surface": `rgba(${ink}, 0.06)`,
    "--color-text": text,
    "--color-text-muted": `rgba(${ink}, 0.72)`,
    "--color-text-faint": `rgba(${ink}, 0.55)`,
    "--color-border": `rgba(${ink}, 0.2)`,
    "--tone-neutral-bg": `rgba(${ink}, 0.1)`,
    "--tone-neutral-text": text,
    ...(accentOverride ? { "--color-accent": accentOverride } : {}),
  };
}

function tabsStyle(tabs: string | undefined, background: string | undefined, accent: string): ThemeStyle {
  const style: ThemeStyle = {};
  // L'onglet actif prend `--color-bg` pour se fondre dans la page en dessous.
  const backgroundRgb = background ? hexToRgb(background) : null;
  if (background && backgroundRgb) {
    style["--color-bg"] = background;
    const accentOverride = readableAccent(accent, backgroundRgb, contrastTextFor(backgroundRgb));
    if (accentOverride) style["--color-accent"] = accentOverride;
  }
  const rgb = tabs ? hexToRgb(tabs) : null;
  if (tabs && rgb) {
    const text = contrastTextFor(rgb);
    const ink = inkFor(text);
    style["--sidebar-bg"] = tabs;
    style["--sidebar-muted"] = `rgba(${ink}, 0.7)`;
    style["--sidebar-active"] = text;
    style["--sidebar-active-bg"] = `rgba(${ink}, 0.12)`;
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
    tabs: tabsStyle(colors.tabs, colors.background, accent),
    main: zoneStyle(colors.background, accent),
    sidebar: zoneStyle(colors.sidebar, accent),
    content: zoneStyle(colors.content, accent),
    header: zoneStyle(colors.header, accent),
    footer: zoneStyle(colors.footer, accent),
  };
}
