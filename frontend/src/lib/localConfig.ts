import { useSyncExternalStore } from "react";

const defaultApiBaseUrl = "http://localhost:8000/api";
const defaultApiKey = "elevator-secret-key-123";
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
  const nextValue = trimmed || defaultApiBaseUrl;
  return nextValue.replace(/\/+$/, "");
}

function normalizeApiKey(value: string): string {
  const trimmed = value.trim();
  return trimmed || defaultApiKey;
}

function normalizeConfig(value: Partial<LocalConfigState>): LocalConfigState {
  return {
    apiBaseUrl: normalizeApiBaseUrl(value.apiBaseUrl ?? defaultApiBaseUrl),
    apiKey: normalizeApiKey(value.apiKey ?? defaultApiKey)
  };
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
    apiBaseUrl: defaultApiBaseUrl,
    apiKey: defaultApiKey
  };
}
