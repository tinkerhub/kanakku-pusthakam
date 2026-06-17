import { createContext, useContext, useEffect, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  bootstrapTenant,
  setRuntimePublishableKey,
  type TenantBootstrap,
} from "./api";
import { applyTenantBranding } from "./branding";
import { configuredTenantToken } from "./runtimeConfig";

type TenantContextValue =
  | {
      mode: "central";
      loading: false;
      error: null;
      bootstrap: null;
      slug: "";
      makerspaceId: null;
      modules: Set<string>;
    }
  | {
      mode: "single";
      loading: boolean;
      error: Error | null;
      bootstrap: TenantBootstrap | null;
      slug: string;
      makerspaceId: number | null;
      modules: Set<string>;
    };

const TenantContext = createContext<TenantContextValue | null>(null);

export function TenantProvider({ children }: { children: ReactNode }) {
  const tenantToken = configuredTenantToken();
  const singleTenant = Boolean(tenantToken);
  const tenantQuery = useQuery({
    queryKey: ["runtime-tenant", tenantToken],
    queryFn: () => bootstrapTenant({ tenant: tenantToken }),
    enabled: singleTenant,
    staleTime: Infinity,
  });

  useEffect(() => {
    if (tenantQuery.data) {
      setRuntimePublishableKey(tenantQuery.data.public_api.publishable_key);
      applyTenantBranding(tenantQuery.data);
    }
  }, [tenantQuery.data]);

  if (!singleTenant) {
    return (
      <TenantContext.Provider
        value={{
          mode: "central",
          loading: false,
          error: null,
          bootstrap: null,
          slug: "",
          makerspaceId: null,
          modules: new Set(),
        }}
      >
        {children}
      </TenantContext.Provider>
    );
  }

  const error = tenantQuery.error instanceof Error ? tenantQuery.error : null;
  const value: TenantContextValue = {
    mode: "single",
    loading: tenantQuery.isLoading,
    error,
    bootstrap: tenantQuery.data ?? null,
    slug: tenantQuery.data?.makerspace.slug ?? "",
    makerspaceId: tenantQuery.data?.makerspace.id ?? null,
    modules: new Set(tenantQuery.data?.modules ?? []),
  };

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>;
}

export function useTenant() {
  const value = useContext(TenantContext);
  if (!value) {
    throw new Error("useTenant must be used inside TenantProvider");
  }
  return value;
}

export function tenantPath(mode: "central" | "single", slug: string, subpath = "") {
  const cleanSubpath = subpath.replace(/^\/+/, "");
  if (mode === "single") {
    return cleanSubpath ? `/${cleanSubpath}` : "/";
  }
  return cleanSubpath ? `/m/${slug}/${cleanSubpath}` : `/m/${slug}`;
}

export function useTenantPath(slug: string) {
  const tenant = useTenant();
  return (subpath = "") => tenantPath(tenant.mode, slug, subpath);
}
