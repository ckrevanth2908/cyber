const API_BASE_URL = "PASTE_YOUR_RENDER_BACKEND_URL_HERE";

async function apiRequest(path, options = {}) {
  if (API_BASE_URL.includes("PASTE_")) {
    throw new Error("Update API_BASE_URL in frontend/config.js first.");
  }

  const response = await fetch(API_BASE_URL + path, {
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
    ...options
  });

  const result = await response.json().catch(() => ({}));
  if (!response.ok || result.success === false) {
    throw new Error(result.error || "Request failed");
  }
  return result.data;
}
