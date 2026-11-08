"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  Wind,
  LayoutDashboard,
  ChartNoAxesCombined,
  Layers,
  Activity,
  Sun,
  Moon,
  ArrowUpRight,
} from "lucide-react";
const links = [
  { href: "/", label: "Overview", Icon: LayoutDashboard },
  { href: "/forecast", label: "Forecast", Icon: ChartNoAxesCombined },
  { href: "/models", label: "Models", Icon: Layers },
  { href: "/monitoring", label: "Monitoring", Icon: Activity },
];
export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const value = localStorage.getItem("vayuops-theme");
    const enabled = value
      ? value === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    setDark(enabled);
    document.documentElement.classList.toggle("dark", enabled);
  }, []);
  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("vayuops-theme", next ? "dark" : "light");
  }
  return (
    <>
      <a href="#content" className="skip">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link className="brand" href="/">
          <Wind size={28} />
          <span>
            VayuOps<span className="brand-sub">AIR QUALITY INTELLIGENCE</span>
          </span>
        </Link>
        <p className="nav-label">WORKSPACE</p>
        <nav>
          {links.map(({ href, label, Icon }) => (
            <Link
              key={href}
              href={href}
              className={path === href ? "active" : ""}
              aria-current={path === href ? "page" : undefined}
            >
              <Icon size={19} />
              {label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="status-dot" /> Static data snapshot
          <p>India · PM2.5 forecasting</p>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span>
            VAYUOPS{" "}
            <span className="muted">
              / &nbsp; {links.find((x) => x.href === path)?.label}
            </span>
          </span>
          <button
            className="theme"
            onClick={toggle}
            aria-label={dark ? "Use light mode" : "Use dark mode"}
          >
            {dark ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </header>
        <main id="content">{children}</main>
        <footer>
          <p>
            Data sources · Indian Cities AQI 2020–2024 · OpenAQ 2025 · CPCB
            city_day · air_pollution_data
          </p>
          <a
            href="https://github.com/Ayan1702-D/Vayuops/blob/main/docs/limitations.md"
            target="_blank"
            rel="noreferrer"
          >
            Data & model limitations <ArrowUpRight size={14} />
          </a>
        </footer>
      </div>
    </>
  );
}
