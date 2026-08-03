export type Theme = "light" | "dark";

const STORAGE_KEY = "vapilu-theme";

export function getStoredTheme(): Theme | null {
  const v = localStorage.getItem(STORAGE_KEY);
  return v === "light" || v === "dark" ? v : null;
}

export function applyTheme(theme: Theme | null): void {
  if (theme) {
    document.documentElement.setAttribute("data-theme", theme);
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

export function setTheme(theme: Theme): void {
  localStorage.setItem(STORAGE_KEY, theme);
  applyTheme(theme);
}

// Resolves what's actually rendered right now (stored override, or the OS
// preference) - used so a toggle button can show the right icon/label
// even before the user has ever clicked it.
export function resolveActiveTheme(): Theme {
  const stored = getStoredTheme();
  if (stored) return stored;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}
