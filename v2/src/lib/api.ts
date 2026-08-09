export async function apiFetch(path: string, init: RequestInit = {}) {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (
    init.body &&
    !(init.body instanceof FormData) &&
    !headers.has("Content-Type")
  )
    headers.set("Content-Type", "application/json");
  if (
    typeof document !== "undefined" &&
    !["GET", "HEAD", "OPTIONS"].includes(method)
  ) {
    const csrf = document.cookie
      .split("; ")
      .find((item) => item.startsWith("csrf_token="))
      ?.split("=")
      .slice(1)
      .join("=");
    if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  }
  return fetch(`/api${cleanPath}`, {
    ...init,
    credentials: "include",
    headers,
  });
}

export async function apiJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await apiFetch(path, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let parsed: {
      detail?:
        | string
        | { message?: string }
        | Array<{ msg?: string; message?: string }>;
    } | null = null;
    try {
      parsed = JSON.parse(text);
    } catch {
      /* Fall back to the raw response below. */
    }
    const detail = parsed?.detail;
    const message = Array.isArray(detail)
      ? detail[0]?.msg || detail[0]?.message
      : typeof detail === "string"
        ? detail
        : detail?.message;
    throw new Error(message || text || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}
