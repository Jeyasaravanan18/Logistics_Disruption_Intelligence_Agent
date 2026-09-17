const rawBackend = process.env.NEXT_PUBLIC_BACKEND_URL;
const isProd = process.env.NODE_ENV === "production";
const productionBackendUrl = "https://logistics-hackathon.onrender.com";

const resolvedBackend =
  rawBackend && !rawBackend.includes("localhost") && !rawBackend.includes("127.0.0.1")
    ? rawBackend
    : (isProd ? productionBackendUrl : "http://localhost:8000");

export const BACKEND =
  typeof window !== "undefined"
    ? "/api"
    : resolvedBackend;

export const BACKEND_WS = resolvedBackend
  .replace("http://", "ws://")
  .replace("https://", "wss://");

async function parseError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(", ");
    }
  } catch {
    /* ignore */
  }
  return res.statusText || "Request failed";
}

async function refreshSession(): Promise<boolean> {
  const res = await fetch(`${BACKEND}/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  return res.ok;
}

export async function apiFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers || {});
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    if (typeof init.body === "string" && !init.body.startsWith("username=")) {
      headers.set("Content-Type", "application/json");
    }
  }
  const res = await fetch(`${BACKEND}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  if (res.status === 401 && retry && path !== "/auth/login" && path !== "/auth/refresh") {
    const ok = await refreshSession();
    if (ok) return apiFetch(path, init, false);
  }
  return res;
}

export async function loginApi(email: string, password: string) {
  const formData = new URLSearchParams();
  formData.append("username", email);
  formData.append("password", password);

  const res = await fetch(`${BACKEND}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData.toString(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchMe() {
  const res = await apiFetch("/auth/me");
  if (!res.ok) throw new Error("Failed to fetch user profile");
  return res.json();
}

export async function registerApi(email: string, password: string, name: string) {
  const res = await fetch(`${BACKEND}/auth/register`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, name }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function logoutApi() {
  await apiFetch("/auth/logout", { method: "POST" }, false);
}

export async function changePasswordApi(current_password: string, new_password: string) {
  const res = await apiFetch("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password, new_password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchShipments() {
  const res = await apiFetch("/shipments");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function createShipment(payload: Record<string, unknown>) {
  const res = await apiFetch("/shipments", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function updateShipment(id: string, payload: Record<string, unknown>) {
  const res = await apiFetch(`/shipments/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function deleteShipment(id: string) {
  const res = await apiFetch(`/shipments/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function seedDemoShipments() {
  const res = await apiFetch("/shipments/seed-demo", { method: "POST" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchDisruptions() {
  const res = await apiFetch("/disruptions");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchRiskAnalysis() {
  const res = await apiFetch("/risk-analysis");
  if (res.status === 503) return null;
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function runRiskAnalysis() {
  const res = await apiFetch("/risk-analysis/run", { method: "POST" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchHealth() {
  const res = await fetch(`${BACKEND}/health`, { cache: "no-store" });
  return res.json();
}
