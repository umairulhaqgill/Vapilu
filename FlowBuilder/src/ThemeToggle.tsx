import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { resolveActiveTheme, setTheme, type Theme } from "./theme";

export default function ThemeToggle() {
  const [theme, setThemeState] = useState<Theme>("dark");

  useEffect(() => {
    setThemeState(resolveActiveTheme());
  }, []);

  const toggle = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    setThemeState(next);
  };

  return (
    <button type="button" className="theme-toggle" onClick={toggle} title="Toggle light / dark theme">
      <span className={`theme-toggle-track${theme === "light" ? " theme-toggle-track-light" : ""}`}>
        <span className="theme-toggle-thumb">
          {theme === "dark" ? <Moon size={9} /> : <Sun size={9} />}
        </span>
      </span>
      <span>{theme === "dark" ? "Dark" : "Light"}</span>
    </button>
  );
}
