import { Component, ErrorInfo, ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    error: null
  };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("Frontend runtime error", error, errorInfo);
  }

  private handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.error) {
      return (
        <main className="crash-screen">
          <section className="crash-card">
            <span className="page__eyebrow">Frontend Error</span>
            <h1>Page rendering failed</h1>
            <p>
              The frontend caught a runtime error instead of showing a blank page. Use the message
              below to identify the broken field or response.
            </p>
            <pre>{this.state.error.message || "Unknown frontend error"}</pre>
            <button className="action-button" onClick={this.handleReload} type="button">
              Reload page
            </button>
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}
