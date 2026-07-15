/**
 * index.tsx — Widget entry point.
 *
 * This file does three things:
 *
 * 1. Defines a custom element <career-assistant-widget> that hosts the React
 *    app inside a Shadow DOM root. Shadow DOM keeps all CSS scoped — no
 *    conflicts with the host page's styles in either direction.
 *
 * 2. Reads configuration from the <script> tag's data-* attributes:
 *      data-api-key          (required)
 *      data-base-url         (optional, defaults to script's own origin)
 *      data-theme-primary    (optional, default #2563eb)
 *      data-greeting         (optional)
 *      data-suggested-qs     (optional, comma-separated)
 *      data-owner-name       (optional, default "the owner")
 *
 * 3. Auto-instantiates — as soon as the browser parses the <script> tag it
 *    creates and registers the custom element, then appends it to <body>.
 *    Portfolio owners only need one <script> tag.
 *
 * Usage on any page:
 *   <script
 *     src="https://your-domain.com/widget/widget.iife.js"
 *     data-api-key="pk_live_..."
 *     data-theme-primary="#2563eb"
 *     async
 *   ></script>
 */

import React from "react";
import { createRoot } from "react-dom/client";
import { Dashboard, type DashboardConfig } from "./Dashboard";
import { ChatWidget, type WidgetConfig } from "./ChatWidget";
import dashboardCSS from "./styles/dashboard.css?inline";
import widgetCSS from "./styles/widget.css?inline";

/** Resolve base URL from the script tag that loaded us */
function resolveBaseUrl(): string {
  // currentScript is set while the script is executing (sync scripts).
  // For async scripts we fall back to searching for the tag.
  const script =
    (document.currentScript as HTMLScriptElement | null) ??
    document.querySelector<HTMLScriptElement>(
      'script[src*="widget"]'
    );

  if (script?.src) {
    try {
      const u = new URL(script.src);
      return `${u.protocol}//${u.host}`;
    } catch {
      // ignore
    }
  }
  return window.location.origin;
}

/** Read data-* attributes from the loader <script> tag */
function readConfig(): WidgetConfig & { themeColor: string } {
  const script =
    (document.currentScript as HTMLScriptElement | null) ??
    document.querySelector<HTMLScriptElement>('script[src*="widget"]');

  const get = (attr: string, fallback = "") =>
    script?.dataset[attr] ?? fallback;

  const rawQs = get("suggestedQs", "");
  const suggestedQuestions = rawQs
    ? rawQs.split(",").map((q) => q.trim()).filter(Boolean)
    : [];

  return {
    apiKey: get("apiKey", ""),
    baseUrl: get("baseUrl", resolveBaseUrl()),
    greeting: get(
      "greeting",
      `Hi! I'm ${get("ownerName", "the owner")}'s career assistant. Ask me anything about their experience, skills, or projects.`
    ),
    suggestedQuestions,
    themeColor: get("themePrimary", "#2563eb"),
    ownerName: get("ownerName", "the owner"),
  };
}

function readDashboardConfig(el?: HTMLElement | null): DashboardConfig {
  const script =
    (document.currentScript as HTMLScriptElement | null) ??
    document.querySelector<HTMLScriptElement>('script[src*="widget"]');
  const source = el ?? script;
  const get = (attr: string, fallback = "") => source?.dataset[attr] ?? fallback;
  return {
    apiKey: get("apiKey", ""),
    baseUrl: get("baseUrl", resolveBaseUrl()),
  };
}

/** The custom element class — wraps React inside Shadow DOM */
class CareerAssistantWidget extends HTMLElement {
  private _root: ReturnType<typeof createRoot> | null = null;

  connectedCallback() {
    // Create shadow root (closed = no external JS can reach inside)
    const shadow = this.attachShadow({ mode: "closed" });

    // Inject scoped CSS into the shadow root
    const style = document.createElement("style");
    style.textContent = widgetCSS;
    shadow.appendChild(style);

    // Mount point for React
    const container = document.createElement("div");
    container.id = "widget-root";
    shadow.appendChild(container);

    // Read config and apply theme colour as CSS variable
    const config = readConfig();
    style.textContent += `\n:host { --primary: ${config.themeColor}; --primary-dark: ${darken(config.themeColor)}; --primary-light: ${lighten(config.themeColor)}; }`;

    // Mount React
    this._root = createRoot(container);
    this._root.render(<ChatWidget config={config} />);
  }

  disconnectedCallback() {
    this._root?.unmount();
    this._root = null;
  }
}

class TaarsDashboard extends HTMLElement {
  private _root: ReturnType<typeof createRoot> | null = null;

  connectedCallback() {
    const shadow = this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = dashboardCSS;
    shadow.appendChild(style);
    const container = document.createElement("div");
    container.id = "dashboard-root";
    shadow.appendChild(container);
    this._root = createRoot(container);
    this._root.render(<Dashboard config={readDashboardConfig(this)} />);
  }

  disconnectedCallback() {
    this._root?.unmount();
    this._root = null;
  }
}

/** Slightly darken a hex colour for hover states */
function darken(hex: string): string {
  return adjustHex(hex, -30);
}

/** Slightly lighten a hex colour for backgrounds */
function lighten(hex: string): string {
  return adjustHex(hex, 200, 0.08); // very light tint
}

function adjustHex(hex: string, amount: number, alpha?: number): string {
  try {
    const clean = hex.replace("#", "");
    const r = parseInt(clean.slice(0, 2), 16);
    const g = parseInt(clean.slice(2, 4), 16);
    const b = parseInt(clean.slice(4, 6), 16);
    if (alpha !== undefined) {
      return `rgba(${r},${g},${b},${alpha})`;
    }
    const clamp = (v: number) => Math.max(0, Math.min(255, v));
    return `#${[r, g, b]
      .map((c) => clamp(c + amount).toString(16).padStart(2, "0"))
      .join("")}`;
  } catch {
    return hex;
  }
}

// ---------------------------------------------------------------
// Register and auto-mount
// ---------------------------------------------------------------

const TAG = "career-assistant-widget";
const DASHBOARD_TAG = "taars-dashboard";

if (!customElements.get(TAG)) {
  customElements.define(TAG, CareerAssistantWidget);
}

if (!customElements.get(DASHBOARD_TAG)) {
  customElements.define(DASHBOARD_TAG, TaarsDashboard);
}

// Auto-append the element to <body> so owners don't need an extra HTML tag.
// Only do this once even if the script is somehow loaded twice.
const loaderScript =
  (document.currentScript as HTMLScriptElement | null) ??
  document.querySelector<HTMLScriptElement>('script[src*="widget"]');
const shouldAutoMountDashboard = loaderScript?.dataset.mode === "dashboard";

if (shouldAutoMountDashboard && !document.querySelector(DASHBOARD_TAG)) {
  const el = document.createElement(DASHBOARD_TAG);
  if (loaderScript?.dataset.apiKey) el.dataset.apiKey = loaderScript.dataset.apiKey;
  if (loaderScript?.dataset.baseUrl) el.dataset.baseUrl = loaderScript.dataset.baseUrl;
  if (document.body) {
    document.body.appendChild(el);
  } else {
    document.addEventListener("DOMContentLoaded", () => {
      document.body.appendChild(el);
    });
  }
} else if (!shouldAutoMountDashboard && !document.querySelector(TAG)) {
  const el = document.createElement(TAG);
  // Run after DOM is ready
  if (document.body) {
    document.body.appendChild(el);
  } else {
    document.addEventListener("DOMContentLoaded", () => {
      document.body.appendChild(el);
    });
  }
}
