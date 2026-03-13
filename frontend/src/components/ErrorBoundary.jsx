import { Component } from "react";

/**
 * Catches unhandled render errors and shows a friendly fallback UI.
 * Wrap around <App /> or individual page subtrees as needed.
 */
export default class ErrorBoundary extends Component {
  state = { hasError: false, message: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message ?? null };
  }

  componentDidCatch(error, info) {
    console.error("[ErrorBoundary]", error, info);
  }

  handleReset = () => this.setState({ hasError: false, message: null });

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-gray-950 gap-4 px-6 text-center">
        <p className="text-2xl font-bold text-white">Something went wrong.</p>
        {this.state.message && (
          <p className="text-sm text-gray-500 max-w-md">{this.state.message}</p>
        )}
        <div className="flex gap-3 mt-2">
          <button
            onClick={this.handleReset}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 transition"
          >
            Try again
          </button>
          <a
            href="/dashboard"
            className="rounded-lg border border-gray-700 px-4 py-2 text-sm hover:border-gray-500 transition"
          >
            Go to dashboard
          </a>
        </div>
      </div>
    );
  }
}
