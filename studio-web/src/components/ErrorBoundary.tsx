import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { error: Error | null };

/** Catches render errors so optional-service failures do not blank the app shell. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="page" role="alert">
          <h1>Something went wrong</h1>
          <p>The workspace hit an unexpected error. Your project data was not deleted.</p>
          <pre className="empty">{this.state.error.message}</pre>
          <button type="button" className="primary" onClick={() => this.setState({ error: null })}>
            Try Again
          </button>
          <button type="button" onClick={() => { window.location.href = "/"; }}>
            Back to Home
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
