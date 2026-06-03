import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  buildWsBaseUrl,
  getDefaultLocalConfig,
  resetLocalConfig,
  saveLocalConfig,
  useLocalConfig
} from "../lib/localConfig";

interface DraftConfig {
  apiBaseUrl: string;
  apiKey: string;
}

interface FeedbackState {
  text: string;
  tone: "error" | "success";
}

function normalizeDraft(value: DraftConfig): DraftConfig {
  return {
    apiBaseUrl: value.apiBaseUrl.trim(),
    apiKey: value.apiKey.trim()
  };
}

function readErrorDetail(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
    return body.detail;
  }

  return `HTTP ${status}`;
}

export function ConfigPage(): JSX.Element {
  const currentConfig = useLocalConfig();
  const defaultConfig = useMemo(() => getDefaultLocalConfig(), []);
  const [draft, setDraft] = useState<DraftConfig>({
    apiBaseUrl: currentConfig.apiBaseUrl,
    apiKey: currentConfig.apiKey
  });
  const [feedback, setFeedback] = useState<FeedbackState | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    setDraft({
      apiBaseUrl: currentConfig.apiBaseUrl,
      apiKey: currentConfig.apiKey
    });
  }, [currentConfig.apiBaseUrl, currentConfig.apiKey]);

  const normalizedDraft = useMemo(() => normalizeDraft(draft), [draft]);
  const hasUnsavedChanges =
    normalizedDraft.apiBaseUrl !== currentConfig.apiBaseUrl ||
    normalizedDraft.apiKey !== currentConfig.apiKey;
  const wsPreview = buildWsBaseUrl(normalizedDraft.apiBaseUrl || currentConfig.apiBaseUrl);

  const handleSave = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();

    if (!normalizedDraft.apiBaseUrl || !normalizedDraft.apiKey) {
      setFeedback({
        text: "API base URL and API key are both required.",
        tone: "error"
      });
      return;
    }

    try {
      const parsedUrl = new URL(normalizedDraft.apiBaseUrl);
      if (!/^https?:$/.test(parsedUrl.protocol)) {
        throw new Error("unsupported-protocol");
      }
    } catch {
      setFeedback({
        text: "API base URL must be a valid absolute HTTP or HTTPS URL.",
        tone: "error"
      });
      return;
    }

    saveLocalConfig(normalizedDraft);
    setFeedback({
      text: "Local browser config saved.",
      tone: "success"
    });
  };

  const handleRestoreSaved = (): void => {
    setDraft({
      apiBaseUrl: currentConfig.apiBaseUrl,
      apiKey: currentConfig.apiKey
    });
    setFeedback(null);
  };

  const handleUseDefaults = (): void => {
    resetLocalConfig();
    setFeedback({
      text: "Reverted to built-in defaults for this browser.",
      tone: "success"
    });
  };

  const handleTestConnection = async (): Promise<void> => {
    if (!normalizedDraft.apiBaseUrl || !normalizedDraft.apiKey) {
      setFeedback({
        text: "Enter both API values before testing the connection.",
        tone: "error"
      });
      return;
    }

    try {
      setIsTesting(true);
      const response = await fetch(`${normalizedDraft.apiBaseUrl.replace(/\/+$/, "")}/elevators`, {
        headers: {
          "X-API-Key": normalizedDraft.apiKey
        }
      });

      if (!response.ok) {
        let detail = `HTTP ${response.status}`;

        try {
          detail = readErrorDetail(await response.json(), response.status);
        } catch {
          detail = `HTTP ${response.status}`;
        }

        throw new Error(detail);
      }

      const elevators = (await response.json()) as unknown[];
      setFeedback({
        text: `Connection succeeded. ${elevators.length} elevator record(s) returned.`,
        tone: "success"
      });
    } catch (error) {
      setFeedback({
        text: error instanceof Error ? `Connection failed: ${error.message}` : "Connection failed.",
        tone: "error"
      });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <section className="page">
      <header className="page__header">
        <div>
          <span className="page__eyebrow">Route</span>
          <h2>Local Config</h2>
        </div>
        <div className="status-pill">
          {currentConfig.isUsingDefaults ? "Using defaults" : "Using local overrides"}
        </div>
      </header>

      <div className="summary-strip">
        <article className="summary-card">
          <span className="fleet-card__eyebrow">Storage scope</span>
          <strong>This browser</strong>
        </article>
        <article className="summary-card">
          <span className="fleet-card__eyebrow">Current API</span>
          <strong className="summary-card__value">{currentConfig.apiBaseUrl}</strong>
        </article>
        <article className="summary-card">
          <span className="fleet-card__eyebrow">Current socket</span>
          <strong className="summary-card__value">{currentConfig.wsBaseUrl}</strong>
        </article>
        <article className="summary-card">
          <span className="fleet-card__eyebrow">Mode</span>
          <strong>{currentConfig.isUsingDefaults ? "Default" : "Custom"}</strong>
        </article>
      </div>

      <div className="card-grid card-grid--wide">
        <article className="card">
          <h3>What this page controls</h3>
          <p>
            API requests and WebSocket connections now read their endpoint and API key from browser
            storage instead of fixed build-time constants.
          </p>
        </article>
        <article className="card">
          <h3>Built-in defaults</h3>
          <p>
            <code>{defaultConfig.apiBaseUrl}</code>
            <br />
            <code>{defaultConfig.apiKey}</code>
          </p>
        </article>
      </div>

      {feedback ? (
        <div className={feedback.tone === "error" ? "callout callout--error" : "callout"}>
          {feedback.text}
        </div>
      ) : null}

      <div className="config-layout">
        <form className="panel config-form" onSubmit={handleSave}>
          <div className="panel__header">
            <div>
              <span className="fleet-card__eyebrow">Settings</span>
              <h3>Connection profile</h3>
            </div>
            <span className="status-pill">{hasUnsavedChanges ? "Unsaved changes" : "Saved"}</span>
          </div>

          <label className="field">
            <span>API base URL</span>
            <input
              type="text"
              value={draft.apiBaseUrl}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  apiBaseUrl: event.target.value
                }))
              }
              placeholder="http://localhost:8000/api"
            />
          </label>

          <label className="field">
            <span>API key</span>
            <input
              type="text"
              value={draft.apiKey}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  apiKey: event.target.value
                }))
              }
              placeholder="elevator-secret-key-123"
            />
          </label>

          <div className="toolbar__meta">
            <span>Preview REST base: {normalizedDraft.apiBaseUrl || currentConfig.apiBaseUrl}</span>
            <span>Preview socket base: {wsPreview}</span>
          </div>

          <div className="action-row">
            <button className="action-button" type="submit">
              Save local config
            </button>
            <button
              className="action-button action-button--secondary"
              onClick={() => void handleTestConnection()}
              disabled={isTesting}
              type="button"
            >
              {isTesting ? "Testing..." : "Test connection"}
            </button>
            <button
              className="action-button action-button--ghost"
              onClick={handleRestoreSaved}
              disabled={!hasUnsavedChanges}
              type="button"
            >
              Restore saved
            </button>
            <button
              className="action-button action-button--ghost"
              onClick={handleUseDefaults}
              type="button"
            >
              Use defaults
            </button>
          </div>
        </form>

        <section className="panel">
          <div className="panel__header">
            <div>
              <span className="fleet-card__eyebrow">Behavior</span>
              <h3>How it applies</h3>
            </div>
          </div>

          <div className="stack">
            <article className="workflow-card">
              <div className="workflow-card__header">
                <div>
                  <span className="fleet-card__eyebrow">Runtime</span>
                  <h4>Requests update immediately</h4>
                </div>
              </div>
              <p className="workflow-card__body">
                Saving here changes the endpoint used by fleet, live monitor, alerts, and
                maintenance requests without rebuilding the frontend.
              </p>
            </article>

            <article className="workflow-card">
              <div className="workflow-card__header">
                <div>
                  <span className="fleet-card__eyebrow">Storage</span>
                  <h4>Per-browser persistence</h4>
                </div>
              </div>
              <p className="workflow-card__body">
                Values are stored in <code>localStorage</code>, so they stay on this machine and in
                this browser profile.
              </p>
            </article>

            <article className="workflow-card">
              <div className="workflow-card__header">
                <div>
                  <span className="fleet-card__eyebrow">Fallback</span>
                  <h4>Defaults remain available</h4>
                </div>
              </div>
              <p className="workflow-card__body">
                Clearing the local override falls back to the built-in localhost configuration.
              </p>
            </article>
          </div>
        </section>
      </div>
    </section>
  );
}
