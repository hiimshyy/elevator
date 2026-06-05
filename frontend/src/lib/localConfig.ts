import { useSyncExternalStore } from "react";

const fallbackApiBaseUrl = "http://localhost:8000/api";
const defaultApiKey = import.meta.env.VITE_API_KEY?.trim() || "elevator-secret-key-123";
const storageKey = "elevator-pdm.local-config";

interface LocalConfigState {
  apiBaseUrl: string;
  apiKey: string;
}

export interface LocalConfig extends LocalConfigState {
  isUsingDefaults: boolean;
  wsBaseUrl: string;
}

const listeners = new Set<() => void>();
let cachedConfigKey: string | null = null;
let cachedConfigSnapshot: LocalConfig | null = null;

function notifyListeners(): void {
  cachedConfigKey = null;
  cachedConfigSnapshot = null;
  listeners.forEach((listener) => listener());
}

if (typeof window !== "undefined") {
  window.addEventListener("storage", (event) => {
    if (event.key === storageKey) {
      notifyListeners();
    }
  });
}

function normalizeApiBaseUrl(value: string): string {
  const trimmed = value.trim();
  const nextValue = trimmed || getDefaultApiBaseUrl();
  return nextValue.replace(/\/+$/, "");
}

function normalizeApiKey(value: string): string {
  const trimmed = value.trim();
  return trimmed || defaultApiKey;
}

function getDefaultApiBaseUrl(): string {
  const configuredUrl = import.meta.env.VITE_API_BASE_URL?.trim();
  if (configuredUrl) {
    return configuredUrl.replace(/\/+$/, "");
  }

  if (typeof window === "undefined") {
    return fallbackApiBaseUrl;
  }

  const url = new URL(window.location.href);
  url.protocol = window.location.protocol === "https:" ? "https:" : "http:";
  url.port = "8000";
  url.pathname = "/api";
  url.search = "";
  url.hash = "";
  return url.toString().replace(/\/+$/, "");
}

function normalizeConfig(value: Partial<LocalConfigState>): LocalConfigState {
  const normalizedApiBaseUrl = normalizeApiBaseUrl(value.apiBaseUrl ?? getDefaultApiBaseUrl());
  const migratedApiBaseUrl = migrateLocalhostApiBaseUrl(normalizedApiBaseUrl);

  return {
    apiBaseUrl: migratedApiBaseUrl,
    apiKey: normalizeApiKey(value.apiKey ?? defaultApiKey)
  };
}

function isLoopbackHostname(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

function migrateLocalhostApiBaseUrl(value: string): string {
  if (typeof window === "undefined") {
    return value;
  }

  try {
    const parsed = new URL(value);
    if (
      isLoopbackHostname(parsed.hostname) &&
      !isLoopbackHostname(window.location.hostname)
    ) {
      return getDefaultApiBaseUrl();
    }
  } catch {
    return getDefaultApiBaseUrl();
  }

  return value;
}

function readStoredConfig(rawValue?: string | null): Partial<LocalConfigState> {
  const resolvedRawValue =
    rawValue ?? (typeof window !== "undefined" ? window.localStorage.getItem(storageKey) : null);
  if (!resolvedRawValue) {
    return {};
  }

  try {
    return JSON.parse(resolvedRawValue) as Partial<LocalConfigState>;
  } catch {
    return {};
  }
}

function getConfigCacheKey(rawValue: string | null, defaultApiBaseUrl: string): string {
  return JSON.stringify({
    rawValue,
    defaultApiBaseUrl,
    defaultApiKey
  });
}

function buildLocalConfigSnapshot(
  resolved: LocalConfigState,
  defaultApiBaseUrl: string
): LocalConfig {
  return {
    ...resolved,
    isUsingDefaults:
      resolved.apiBaseUrl === defaultApiBaseUrl && resolved.apiKey === defaultApiKey,
    wsBaseUrl: buildWsBaseUrl(resolved.apiBaseUrl)
  };
}

export function getLocalConfig(): LocalConfig {
  const defaultApiBaseUrl = getDefaultApiBaseUrl();
  const rawValue = typeof window !== "undefined" ? window.localStorage.getItem(storageKey) : null;
  const cacheKey = getConfigCacheKey(rawValue, defaultApiBaseUrl);

  if (cachedConfigKey === cacheKey && cachedConfigSnapshot !== null) {
    return cachedConfigSnapshot;
  }

  const resolved = normalizeConfig(readStoredConfig(rawValue));
  const snapshot = buildLocalConfigSnapshot(resolved, defaultApiBaseUrl);

  cachedConfigKey = cacheKey;
  cachedConfigSnapshot = snapshot;
  return snapshot;
}

export function saveLocalConfig(value: LocalConfigState): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(storageKey, JSON.stringify(normalizeConfig(value)));
  notifyListeners();
}

export function resetLocalConfig(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(storageKey);
  notifyListeners();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);

  return () => {
    listeners.delete(listener);
  };
}

export function useLocalConfig(): LocalConfig {
  return useSyncExternalStore(subscribe, getLocalConfig, getLocalConfig);
}

export function getDefaultLocalConfig(): LocalConfigState {
  return {
    apiBaseUrl: getDefaultApiBaseUrl(),
    apiKey: defaultApiKey
  };
}

export function buildWsBaseUrl(apiBaseUrl: string): string {
  return normalizeApiBaseUrl(apiBaseUrl).replace(/^http/, "ws").replace(/\/api$/, "");
}
