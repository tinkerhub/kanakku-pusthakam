# Common Makerspace Manager Platform PRD

## Problem Statement

This product is a common makerspace manager platform, not a single-organization inventory tool. It should provide a shared backend for makerspace operations such as public inventory, staff workflows, guest-admin handover, QR scans, evidence, notifications, printing, maintenance, procurement, member-facing workflows, and audit logs. The next scaling problem is that different makerspaces and different workflows need different user interfaces without duplicating backend logic.

The platform should support many frontends from one backend:

- A public inventory portal for each makerspace.
- A staff/admin dashboard for space managers and inventory managers.
- A guest handover app for physical issue workflows.
- A QR-first scanner PWA for mobile use.
- A kiosk/check-in UI for public spaces.
- A superadmin console for managing makerspaces, domains, modules, API clients, and integrations.
- Third-party makerspace websites or internal tools built by external teams.

The current backend has many of the right pieces: makerspace tenancy, RBAC, versioned API routes, public keys, API clients, CORS origins, OpenAPI docs, and scoped workflows. However, frontend selection, tenant discovery, domain mapping, feature/module discovery, theming, and third-party client onboarding are not yet formalized as a platform contract.

Without a clear platform layer, each new frontend risks hardcoding makerspace slugs, API paths, branding, permissions, and feature assumptions. That would slow down growth and make it harder to onboard independent makerspaces in the style of InvenTree or other extensible operations platforms.

## Solution

Create a tenant-aware platform layer that lets multiple independent frontends safely consume the same backend.

The backend remains the single source of truth for makerspaces, inventory, requests, QR, evidence, users, roles, modules, integrations, and audit logs. Frontends become replaceable clients that bootstrap themselves from backend-provided configuration.

The solution has five main parts:

1. Tenant and frontend discovery

   Add a backend-owned way to resolve a frontend request into a makerspace and frontend context using hostname, configured domain, public code, or slug.

2. Frontend bootstrap API

   Add a public bootstrap endpoint that returns makerspace identity, frontend type, enabled modules, branding/theme settings, public API configuration, and supported workflows.

3. Domain and client registry

   Model frontend domains and API clients separately so each makerspace can safely attach multiple public portals, scanner apps, kiosk UIs, or third-party websites.

4. Module and feature flags

   Add per-makerspace module configuration so frontends can render only the workflows enabled for that makerspace, such as borrowing, self-checkout, 3D printing, maintenance, procurement, Telegram, or public inventory.

5. Typed external API contract

   Strengthen the OpenAPI contract and generate a reusable TypeScript client SDK so first-party and third-party frontends use the same API definitions.

The backend must never assume a single frontend. Every request must be evaluated through client identity, tenant identity, user identity where applicable, RBAC, feature/module availability, and makerspace scoping.

## User Stories

1. As a public visitor, I want to open a makerspace-specific public inventory site, so that I can browse only the inventory visible for that makerspace.

2. As a public visitor, I want the public site to show the correct makerspace name, logo, colors, and enabled workflows, so that the experience feels local to that makerspace.

3. As a public visitor, I want the public inventory UI to hide workflows that the makerspace has disabled, so that I am not shown actions I cannot complete.

4. As a checked-in requester, I want to submit a hardware request from any approved frontend, so that makerspaces can use their own public website without losing the common workflow.

5. As a checked-in requester, I want request status links to work across supported frontends, so that I can follow up without knowing which backend service powers the workflow.

6. As a space manager, I want an admin dashboard that can manage only my assigned makerspaces, so that multi-makerspace hosting does not create cross-tenant access risk.

7. As a space manager, I want to configure the public domains allowed for my makerspace, so that only approved websites can use the public browser API.

8. As a space manager, I want to enable or disable modules such as public inventory, borrowing, self-checkout, printing, and Telegram, so that my makerspace can start small and adopt features gradually.

9. As a space manager, I want to configure branding for my makerspace, so that the default public portal and kiosk UI match local identity.

10. As a space manager, I want to issue publishable browser client credentials, so that approved public frontends can call public API routes without embedding secrets.

11. As a space manager, I want to revoke a frontend domain or API client, so that a compromised or abandoned frontend can be cut off without disabling the makerspace.

12. As an inventory manager, I want the staff frontend to discover enabled modules, so that I do not see printing, maintenance, procurement, or borrowing screens that are disabled for my makerspace.

13. As an inventory manager, I want every operational view to use the same backend workflows, so that accepting, issuing, returning, scanning, and auditing behave the same across all frontends.

14. As a guest admin, I want a simplified handover app, so that I can issue accepted requests without seeing inventory management, staff management, or makerspace settings.

15. As a guest admin, I want the handover app to work well on a phone, so that I can scan QR codes and upload issue evidence near the physical hardware.

16. As a return desk operator, I want a scanner-first UI, so that I can scan a box, request, or tool QR code and immediately see the allowed next action.

17. As a superadmin, I want to manage all makerspace domains from one console, so that each makerspace can have one or more approved public, kiosk, scanner, or admin frontends.

18. As a superadmin, I want to see which frontends and API clients are connected to each makerspace, so that I can audit platform access.

19. As a superadmin, I want to disable a feature module for one makerspace without affecting others, so that rollout and support can be staged safely.

20. As a superadmin, I want global defaults for modules and branding, so that new makerspaces get a working setup without manual configuration.

21. As a superadmin, I want all frontend/client changes to create audit log entries, so that platform access changes are traceable.

22. As a third-party makerspace developer, I want an OpenAPI-backed TypeScript client, so that I can build a custom frontend without hand-writing API bindings.

23. As a third-party makerspace developer, I want a bootstrap endpoint, so that my frontend can resolve tenant identity, branding, public API settings, and enabled workflows at runtime.

24. As a third-party makerspace developer, I want a browser-safe publishable client model, so that I never need to place HMAC secrets in a JavaScript bundle.

25. As a third-party integration developer, I want server API clients with HMAC signing, so that backend-to-backend integrations can safely access allowed scopes.

26. As a third-party integration developer, I want API client scopes, so that a reporting integration does not receive inventory mutation permissions.

27. As a platform operator, I want clear frontend types, so that public, admin, handover, scanner, kiosk, and third-party clients can be governed differently.

28. As a platform operator, I want per-domain CORS configuration derived from registered domains, so that public API access is consistently enforced.

29. As a platform operator, I want rate limits tied to client type and makerspace, so that public portals and third-party clients cannot overload the shared backend.

30. As a platform operator, I want unsupported module calls to fail clearly, so that disabled workflows cannot be invoked accidentally through direct API calls.

31. As a platform operator, I want every data access path to remain makerspace-scoped, so that one makerspace cannot infer or access another makerspace's data.

32. As a frontend engineer, I want a shared API client package, so that public, admin, scanner, and kiosk apps all use the same request/response types.

33. As a frontend engineer, I want runtime feature flags from the backend, so that a frontend can render safely even when different makerspaces have different modules enabled.

34. As a frontend engineer, I want stable bootstrap data, so that a frontend can load tenant configuration before rendering routes.

35. As a kiosk user, I want a simplified public UI optimized for a shared device, so that visitors can browse, verify check-in, or request hardware without staff-only screens.

36. As a scanner app user, I want QR scan results to resolve to the correct object and allowed actions, so that I do not need to know whether the QR belongs to a box, asset, product, or request.

37. As a future procurement manager, I want procurement to be a module rather than a separate system, so that purchasing can share makerspace, supplier, stock, and audit data.

38. As a future maintenance manager, I want maintenance to be a module rather than a separate system, so that damaged assets, repair history, and availability stay connected.

39. As a future fabrication manager, I want 3D printing and fabrication workflows to reuse the same makerspace, RBAC, notification, and audit infrastructure, so that operational tools remain consistent.

40. As a platform maintainer, I want the platform layer to be incremental, so that existing public inventory and staff panels keep working while new frontends are introduced.

## Implementation Decisions

- The backend remains a single multi-tenant API platform. Do not create separate backend deployments or duplicated APIs per frontend.

- `Makerspace` remains the root tenant boundary. Every operational object continues to be scoped by makerspace directly or indirectly.

- Add a domain registry concept for makerspace-owned hostnames. Each domain records the makerspace, hostname, frontend type, primary status, and active status.

- Add a frontend bootstrap endpoint that resolves tenant and frontend context from hostname, explicit makerspace slug, or public code.

- The bootstrap response should include makerspace identity, frontend type, theme data, enabled modules, public API client hints, and route/workflow availability.

- Add a makerspace theme/settings concept for logo, display name, colors, support contact, and public-facing metadata.

- Add per-makerspace feature/module flags. Initial modules should include public inventory, request workflow, self-checkout, staff admin, guest handover, scanner, printing, Telegram, evidence uploads, QR management, and bulk import.

- Feature flags must be enforced by backend permission or guard checks, not only hidden in the frontend.

- Keep browser clients publishable-only. Browser frontends may use publishable client IDs or publishable keys plus Origin/CORS validation. They must not use HMAC secrets.

- Keep HMAC signing for server-to-server clients only. Server clients must have explicit scopes, makerspace scope where applicable, replay protection, and audit logs for creation/revocation.

- API clients should have a client type, allowed origins where relevant, allowed scopes, active status, optional makerspace scope, rate-limit tier, and audit history.

- Domain registrations and publishable browser clients should drive CORS allowlists instead of relying only on manually edited JSON fields.

- Frontend type should be explicit. Initial types should be public portal, staff admin, guest handover, scanner, kiosk, superadmin console, and third-party.

- The public inventory portal should continue to use anonymous/public API access and must not expose storage locations, internal QR data, evidence, requester history, hidden counts, audit logs, or internal notes.

- The staff/admin frontend should continue to require user authentication and RBAC checks.

- The guest handover frontend should continue to use the same backend issue workflow and must not get independent state mutation endpoints.

- The scanner frontend should resolve QR codes through backend APIs and receive allowed actions based on object type, makerspace, actor role, current state, and enabled modules.

- The superadmin console should manage makerspaces, domains, module flags, API clients, integrations, global defaults, and platform-level audit views.

- The OpenAPI schema should become the source for a generated TypeScript client used by first-party frontends and optionally distributed to third-party developers.

- New platform endpoints should use the existing versioned API namespace.

- The platform layer must preserve existing hard rules: request status changes only through workflow services, availability owns quantity math, evidence and QR scan records remain immutable, and audit logs remain append-only.

- Existing public and staff frontends should be migrated incrementally to use bootstrap configuration rather than hardcoded environment assumptions.

- The initial implementation should not require separate databases, schemas, or deployments per makerspace. Those may be considered later for very large tenants.

## Testing Decisions

- Tests should focus on external behavior, security boundaries, and tenant isolation rather than implementation details.

- Bootstrap tests should verify that a known domain resolves to the correct makerspace, frontend type, theme, and enabled modules.

- Bootstrap tests should verify that unknown, inactive, or disabled domains fail safely.

- Domain registry tests should verify hostname uniqueness, active/inactive behavior, primary-domain behavior, and audit logs.

- CORS/client tests should verify that only registered origins can call public browser endpoints.

- Client-auth tests should verify that browser clients never require or accept HMAC secrets.

- Server-client tests should verify HMAC signing, timestamp replay protection, scope enforcement, makerspace scoping, and revocation.

- Feature flag tests should verify that disabled modules are hidden in bootstrap data and blocked at backend API guard points.

- Tenant isolation tests should verify that a frontend or API client scoped to one makerspace cannot read or mutate another makerspace.

- RBAC tests should verify that user roles still control staff/admin/guest/scanner actions independently from frontend identity.

- Public API tests should verify that public frontends cannot access internal inventory data, evidence, QR internals, requester history, or audit logs.

- Scanner tests should verify QR resolution for box, asset, product, and request codes with allowed actions based on current state.

- OpenAPI/SDK tests should verify that schema generation succeeds and that generated clients match the deployed API contract.

- Regression tests should preserve existing request workflow, evidence, return, audit, API client, QR, and public inventory behavior.

## Out of Scope

- Rewriting the existing backend into microservices.

- Creating separate backend deployments per makerspace.

- Multi-database or per-tenant database sharding.

- Billing and subscription management.

- Marketplace-style public app installation.

- Native iOS or Android apps.

- Full procurement, maintenance, or ERP functionality in the first platform-layer release.

- Replacing existing lending, return, QR, evidence, Telegram, or printing workflows.

- Public user account systems beyond the existing check-in/requester model.

- White-label custom CSS beyond basic theme and branding fields.

## Further Notes

This PRD should be treated as the next platform architecture layer after the current MVP. The current system already has most lending and operational workflows implemented. The goal is not to rebuild those workflows, but to make them consumable by multiple safe, tenant-aware frontends.

The most important security decision is to keep browser clients publishable-only. Any frontend distributed as JavaScript must be treated as public. HMAC secrets are only valid for server-side clients.

The recommended implementation order is:

1. Add makerspace domain and frontend type registry.
2. Add public bootstrap endpoint.
3. Add theme/settings and module flags.
4. Enforce module flags in backend guards.
5. Refactor existing frontend boot to use bootstrap data.
6. Add API client scopes and clearer browser/server client separation.
7. Generate and consume a shared TypeScript API client from OpenAPI.
8. Add scanner/kiosk/frontends incrementally on top of the same platform contract.
