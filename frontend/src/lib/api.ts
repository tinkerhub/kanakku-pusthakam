export const API_URL =
  import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

const API_V1_URL = API_URL.replace(/\/api$/, "/api/v1");
const PUBLIC_API_KEY = import.meta.env.VITE_PUBLIC_API_KEY ?? "";
const PUBLIC_CLIENT_ID = import.meta.env.VITE_PUBLIC_CLIENT_ID ?? "";
const PUBLIC_CLIENT_SECRET = import.meta.env.VITE_PUBLIC_CLIENT_SECRET ?? "";
const ACCESS_TOKEN_KEY = "makerspace.access";

function messageForStatus(status: number): string {
  if (status === 401) {
    return "Inventory client is not authorized";
  }

  if (status === 404) {
    return "Makerspace not found";
  }

  if (status >= 500) {
    return "Inventory service is unavailable";
  }

  return "Unable to load inventory";
}

async function publicHeaders(
  method: string,
  requestPath: string,
  body = "",
): Promise<HeadersInit> {
  if (PUBLIC_CLIENT_ID && PUBLIC_CLIENT_SECRET) {
    const timestamp = String(Math.floor(Date.now() / 1000));
    const message = [method.toUpperCase(), requestPath, timestamp, body].join("\n");
    return {
      "X-Client-Id": PUBLIC_CLIENT_ID,
      "X-Timestamp": timestamp,
      "X-Signature": await hmacSha256(PUBLIC_CLIENT_SECRET, message),
    };
  }
  if (PUBLIC_CLIENT_ID) {
    return { "X-Client-Id": PUBLIC_CLIENT_ID };
  }
  return PUBLIC_API_KEY ? { "X-Publishable-Key": PUBLIC_API_KEY } : {};
}

async function hmacSha256(secret: string, message: string): Promise<string> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(message));
  return Array.from(new Uint8Array(signature))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchJson<T>(url: string, requestPath: string): Promise<T> {
  const response = await fetch(url, {
    headers: await publicHeaders("GET", requestPath),
  });

  if (!response.ok) {
    throw new Error(`${messageForStatus(response.status)} (${response.status})`);
  }

  return (await response.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return fetchJson<T>(`${API_URL}${path}`, `/api${path}`);
}

export async function publicV1Request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const method = options.method ?? "GET";
  const body = typeof options.body === "string" ? options.body : "";
  const response = await fetch(`${API_V1_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(await publicHeaders(method, `/api/v1${path}`, body)),
      ...(options.headers ?? {}),
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      body.detail ??
        Object.values(body).flat().join(" ") ??
        `Request failed (${response.status})`,
    );
  }

  return (await response.json()) as T;
}

export function setAccessToken(token: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearAccessToken() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
}

export async function staffRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_V1_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers ?? {}),
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}
