export type RuntimeTenantConfig = {
  apiUrl?: string;
  tenantToken?: string;
};

declare global {
  interface Window {
    __TENANT__?: RuntimeTenantConfig;
  }
}

function clean(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function runtimeTenantConfig(): RuntimeTenantConfig {
  const config = typeof window === "undefined" ? undefined : window.__TENANT__;
  return {
    apiUrl: clean(config?.apiUrl) || undefined,
    tenantToken: clean(config?.tenantToken) || undefined,
  };
}

export function configuredTenantToken(): string {
  return (
    runtimeTenantConfig().tenantToken ||
    clean(import.meta.env.VITE_TENANT_TOKEN) ||
    ""
  );
}

export function configuredApiUrl(): string {
  return (
    runtimeTenantConfig().apiUrl ||
    clean(import.meta.env.VITE_API_URL) ||
    "http://localhost:8000/api"
  ).replace(/\/+$/, "");
}
