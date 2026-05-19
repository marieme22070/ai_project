const API_BASE = import.meta.env.VITE_API_URL || "";

function getToken() {
  return localStorage.getItem("access_token");
}

export function setToken(token) {
  if (token) localStorage.setItem("access_token", token);
  else localStorage.removeItem("access_token");
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  const headers = { ...options.headers };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg).join(", ")
          : JSON.stringify(err);
    throw new ApiError(message, res.status);
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function normalizeName(name, languageHint) {
  return request("/normalize-name", {
    method: "POST",
    body: JSON.stringify({ name, language_hint: languageHint || null }),
  });
}

export async function speechToName(file, languageHint) {
  const form = new FormData();
  const blob = file instanceof Blob ? file : new Blob([file], { type: "audio/webm" });
  const name = file.name || "recording.webm";
  const typed =
    blob.type && blob.type.startsWith("audio/")
      ? blob
      : new Blob([blob], { type: "audio/webm;codecs=opus" });
  form.append("file", typed, name.endsWith(".webm") || name.endsWith(".mp4") ? name : `${name}.webm`);
  const params = languageHint ? `?language_hint=${encodeURIComponent(languageHint)}` : "";
  const token = getToken();
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/speech-to-name${params}`, {
    method: "POST",
    body: form,
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const msg = Array.isArray(detail)
      ? detail.map((d) => d.msg).join(", ")
      : detail || "Échec de la transcription";
    throw new Error(msg);
  }
  return res.json();
}

export async function login(username, password) {
  return request("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function fetchMe() {
  return request("/api/v1/auth/me");
}

export async function fetchHistory() {
  return request("/api/v1/history");
}

export async function validateCorrection(historyId, approved, correctedName, correctedArabic, notes) {
  return request("/api/v1/history/validate", {
    method: "POST",
    body: JSON.stringify({
      history_id: historyId,
      approved,
      corrected_name: correctedName || null,
      corrected_arabic: correctedArabic || null,
      notes: notes || null,
    }),
  });
}

export async function fetchKnowledgeStats() {
  return request("/api/v1/knowledge/stats");
}

export async function learnName(inputName, normalized, arabicName) {
  return request("/api/v1/knowledge/learn", {
    method: "POST",
    body: JSON.stringify({
      input_name: inputName,
      normalized,
      arabic_name: arabicName || "",
    }),
  });
}

export async function healthCheck() {
  return request("/health");
}

export async function annotateNameFull(name, languageHint) {
  return request("/api/v1/annotation/annotate/full", {
    method: "POST",
    body: JSON.stringify({ name, language_hint: languageHint || null }),
  });
}

export async function annotateDocument(text, languageHint, maxNames = 100) {
  return request("/api/v1/annotation/annotate/document", {
    method: "POST",
    body: JSON.stringify({
      text,
      language_hint: languageHint || null,
      max_names: maxNames,
    }),
  });
}

/** Format JSON structuré production (entities, duplicate_clusters, summary) */
export async function annotateDocumentStructured(text, languageHint, maxNames = 100) {
  return request("/api/v1/annotation/annotate/document/structured", {
    method: "POST",
    body: JSON.stringify({
      text,
      language_hint: languageHint || null,
      max_names: maxNames,
    }),
  });
}

export async function annotateBatchUpload(file, languageHint) {
  const form = new FormData();
  form.append("file", file);
  const params = languageHint ? `?language_hint=${encodeURIComponent(languageHint)}` : "";
  const token = getToken();
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/api/v1/annotation/annotate/upload${params}`, {
    method: "POST",
    body: form,
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(err.detail || "Échec annotation batch", res.status);
  }
  return res.json();
}

export async function fetchDuplicates(threshold = 85) {
  return request(`/api/v1/duplicates?threshold=${threshold}`);
}

export async function fetchIdentityGraphStats() {
  return request("/api/v1/identity-graph/stats");
}
