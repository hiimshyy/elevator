import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  buildWsBaseUrl,
  getDefaultLocalConfig,
  resetLocalConfig,
  saveLocalConfig,
  useLocalConfig
} from "../lib/localConfig";

import { PageContainer, ResponsiveGrid } from "../components/layout/PageContainer";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { TextInput } from "../components/ui/Field";

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
  const [fieldErrors, setFieldErrors] = useState<{ apiBaseUrl?: string; apiKey?: string }>({});

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
    setFieldErrors({});

    if (!normalizedDraft.apiBaseUrl || !normalizedDraft.apiKey) {
      const errors: { apiBaseUrl?: string; apiKey?: string } = {};
      if (!normalizedDraft.apiBaseUrl) {
        errors.apiBaseUrl = "API base URL is required.";
      }
      if (!normalizedDraft.apiKey) {
        errors.apiKey = "API key is required.";
      }
      setFieldErrors(errors);
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
      setFieldErrors({ apiBaseUrl: "Must be a valid absolute HTTP or HTTPS URL." });
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
    setFieldErrors({});
    setFeedback(null);
  };

  const handleUseDefaults = (): void => {
    resetLocalConfig();
    setFieldErrors({});
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
    <PageContainer>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "var(--spacing-3)" }}>
        <div>
          <span style={{ fontSize: "var(--font-size-xs)", textTransform: "uppercase", letterSpacing: "0.05em", opacity: 0.7 }}>Route</span>
          <h2 style={{ margin: 0 }}>Local Config</h2>
        </div>
        <span style={{ padding: "var(--spacing-1) var(--spacing-3)", borderRadius: "var(--radius-full, 9999px)", fontSize: "var(--font-size-sm)", background: "var(--color-surface-alt, #e2e8f0)", color: "var(--color-text)" }}>
          {currentConfig.isUsingDefaults ? "Using defaults" : "Using local overrides"}
        </span>
      </header>

      <ResponsiveGrid maxColumns={4}>
        <Card elevation="flat" title="Storage scope" headingLevel={3}>
          <strong>This browser</strong>
        </Card>
        <Card elevation="flat" title="Current API" headingLevel={3}>
          <strong style={{ wordBreak: "break-all" }}>{currentConfig.apiBaseUrl}</strong>
        </Card>
        <Card elevation="flat" title="Current socket" headingLevel={3}>
          <strong style={{ wordBreak: "break-all" }}>{currentConfig.wsBaseUrl}</strong>
        </Card>
        <Card elevation="flat" title="Mode" headingLevel={3}>
          <strong>{currentConfig.isUsingDefaults ? "Default" : "Custom"}</strong>
        </Card>
      </ResponsiveGrid>

      <ResponsiveGrid maxColumns={2}>
        <Card title="What this page controls" headingLevel={3}>
          <p>
            API requests and WebSocket connections now read their endpoint and API key from browser
            storage instead of fixed build-time constants.
          </p>
        </Card>
        <Card title="Built-in defaults" headingLevel={3}>
          <p>
            <code>{defaultConfig.apiBaseUrl}</code>
            <br />
            <code>{defaultConfig.apiKey}</code>
          </p>
        </Card>
      </ResponsiveGrid>

      {feedback ? (
        <div
          role="alert"
          aria-live="polite"
          style={{
            padding: "var(--spacing-3) var(--spacing-4)",
            borderRadius: "var(--radius-md, 6px)",
            background: feedback.tone === "error"
              ? "var(--color-status-critical-bg, #fee2e2)"
              : "var(--color-status-healthy-bg, #d1fae5)",
            color: feedback.tone === "error"
              ? "var(--color-status-critical, #dc2626)"
              : "var(--color-status-healthy, #16a34a)",
            marginBlock: "var(--spacing-3)"
          }}
        >
          {feedback.text}
        </div>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 400px), 1fr))", gap: "var(--spacing-4)" }}>
        <Card
          header={
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "var(--spacing-2)" }}>
              <div>
                <span style={{ fontSize: "var(--font-size-xs)", textTransform: "uppercase", letterSpacing: "0.05em", opacity: 0.7 }}>Settings</span>
                <h3 style={{ margin: 0 }}>Connection profile</h3>
              </div>
              <span style={{ padding: "var(--spacing-1) var(--spacing-3)", borderRadius: "var(--radius-full, 9999px)", fontSize: "var(--font-size-sm)", background: "var(--color-surface-alt, #e2e8f0)", color: "var(--color-text)" }}>
                {hasUnsavedChanges ? "Unsaved changes" : "Saved"}
              </span>
            </div>
          }
        >
          <form onSubmit={handleSave}>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-4)" }}>
              <TextInput
                label="API base URL"
                value={draft.apiBaseUrl}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    apiBaseUrl: event.target.value
                  }))
                }
                placeholder="http://localhost:8000/api"
                required
                validationMessage={fieldErrors.apiBaseUrl}
              />

              <TextInput
                label="API key"
                value={draft.apiKey}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    apiKey: event.target.value
                  }))
                }
                placeholder="elevator-secret-key-123"
                required
                validationMessage={fieldErrors.apiKey}
              />

              <div style={{ fontSize: "var(--font-size-sm)", opacity: 0.8 }}>
                <span>Preview REST base: {normalizedDraft.apiBaseUrl || currentConfig.apiBaseUrl}</span>
                <br />
                <span>Preview socket base: {wsPreview}</span>
              </div>

              <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--spacing-3)" }}>
                <Button variant="primary" type="submit">
                  Save local config
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => void handleTestConnection()}
                  disabled={isTesting}
                >
                  {isTesting ? "Testing..." : "Test connection"}
                </Button>
                <Button
                  variant="ghost"
                  onClick={handleRestoreSaved}
                  disabled={!hasUnsavedChanges}
                >
                  Restore saved
                </Button>
                <Button
                  variant="ghost"
                  onClick={handleUseDefaults}
                >
                  Use defaults
                </Button>
              </div>
            </div>
          </form>
        </Card>

        <Card
          header={
            <div>
              <span style={{ fontSize: "var(--font-size-xs)", textTransform: "uppercase", letterSpacing: "0.05em", opacity: 0.7 }}>Behavior</span>
              <h3 style={{ margin: 0 }}>How it applies</h3>
            </div>
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-4)" }}>
            <Card elevation="flat" headingLevel={4}>
              <div>
                <span style={{ fontSize: "var(--font-size-xs)", textTransform: "uppercase", letterSpacing: "0.05em", opacity: 0.7 }}>Runtime</span>
                <h4 style={{ margin: 0 }}>Requests update immediately</h4>
              </div>
              <p>
                Saving here changes the endpoint used by fleet, live monitor, alerts, and
                maintenance requests without rebuilding the frontend.
              </p>
            </Card>

            <Card elevation="flat" headingLevel={4}>
              <div>
                <span style={{ fontSize: "var(--font-size-xs)", textTransform: "uppercase", letterSpacing: "0.05em", opacity: 0.7 }}>Storage</span>
                <h4 style={{ margin: 0 }}>Per-browser persistence</h4>
              </div>
              <p>
                Values are stored in <code>localStorage</code>, so they stay on this machine and in
                this browser profile.
              </p>
            </Card>

            <Card elevation="flat" headingLevel={4}>
              <div>
                <span style={{ fontSize: "var(--font-size-xs)", textTransform: "uppercase", letterSpacing: "0.05em", opacity: 0.7 }}>Fallback</span>
                <h4 style={{ margin: 0 }}>Defaults remain available</h4>
              </div>
              <p>
                Clearing the local override falls back to the built-in localhost configuration.
              </p>
            </Card>
          </div>
        </Card>
      </div>
    </PageContainer>
  );
}
