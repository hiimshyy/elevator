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

function notifyListeners(): void {
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

function readStoredConfig(): Partial<LocalConfigState> {
  if (typeof window === "undefined") {
    return {};
  }

  const rawValue = window.localStorage.getItem(storageKey);
  if (!rawValue) {
    return {};
  }

  try {
    return JSON.parse(rawValue) as Partial<LocalConfigState>;
  } catch {
    return {};
  }
}

export function buildWsBaseUrl(apiBaseUrl: string): string {
  return normalizeApiBaseUrl(apiBaseUrl).replace(/^http/, "ws").replace(/\/api$/, "");
}

export function getLocalConfig(): LocalConfig {
  const resolved = normalizeConfig(readStoredConfig());
  const defaultApiBaseUrl = getDefaultApiBaseUrl();

  return {
    ...resolved,
    isUsingDefaults:
      resolved.apiBaseUrl === defaultApiBaseUrl && resolved.apiKey === defaultApiKey,
    wsBaseUrl: buildWsBaseUrl(resolved.apiBaseUrl)
  };
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
