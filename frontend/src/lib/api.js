import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL;
const TOKEN_KEY = "lotto_token";

const api = axios.create({
  baseURL: `${BASE}/api`,
  withCredentials: true,
});

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}

// Attach bearer token so auth works even when cookies are blocked (mobile webviews, ITP)
api.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auto-retry transient failures (preview cold-starts / gateway blips) so requests self-heal
const MAX_RETRIES = 4;
const RETRY_DELAY_MS = 2500;
const isTransient = (error) => {
  if (!error.response) return true; // network error / server unreachable
  return [502, 503, 504].includes(error.response.status);
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;
    if (!config || config.method === "delete") return Promise.reject(error);
    config._retryCount = config._retryCount || 0;
    if (isTransient(error) && config._retryCount < MAX_RETRIES) {
      config._retryCount += 1;
      await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
      return api(config);
    }
    return Promise.reject(error);
  }
);

export function formatApiError(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default api;
