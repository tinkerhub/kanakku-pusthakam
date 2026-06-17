import type { TenantBootstrap } from "./api";

function hexToRgbParts(hex: string): string | null {
  const value = hex.trim().replace(/^#/, "");
  if (!/^[0-9a-fA-F]{6}$/.test(value)) {
    return null;
  }
  const parts = [0, 2, 4].map((index) => parseInt(value.slice(index, index + 2), 16));
  return parts.join(" ");
}

function setColorVar(name: string, value: unknown) {
  if (typeof value !== "string") return;
  const rgb = hexToRgbParts(value);
  if (rgb) {
    document.documentElement.style.setProperty(name, rgb);
  }
}

function setFavicon(url: string) {
  let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon";
    document.head.appendChild(link);
  }
  link.href = url;
}

export function applyTenantBranding(bootstrap: TenantBootstrap) {
  const name =
    bootstrap.branding.display_name ||
    bootstrap.makerspace.name ||
    "Makerspace Manager";
  document.title = name;
  setColorVar("--color-accent", bootstrap.theme.primary_color);
  setColorVar("--color-success", bootstrap.theme.accent_color);
  if (typeof bootstrap.theme.logo_url === "string" && bootstrap.theme.logo_url) {
    setFavicon(bootstrap.theme.logo_url);
  }
}
