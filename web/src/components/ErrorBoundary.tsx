import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  reset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="terminal-panel rounded-2xl p-8 border border-red-500/30 bg-red-500/5">
          <div className="flex items-start gap-4">
            <AlertTriangle className="text-red-400 mt-1 flex-shrink-0" size={24} />
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-red-300 mb-2">Component Error</h3>
              <p className="text-sm text-slate-400 mb-4">
                {this.state.error?.message || 'An unexpected error occurred in this component'}
              </p>
              <details className="mb-4">
                <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-400">
                  Error Details
                </summary>
                <pre className="mt-2 p-2 bg-slate-900/50 rounded text-xs text-slate-400 overflow-auto max-h-40">
                  {this.state.error?.stack}
                </pre>
              </details>
              <button
                onClick={this.reset}
                className="flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/40 rounded-lg transition text-sm font-medium"
              >
                <RefreshCw size={14} />
                Try Again
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
