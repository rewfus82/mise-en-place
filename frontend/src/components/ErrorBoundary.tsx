import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
  info: ErrorInfo | null
}

/**
 * App-level error boundary. Catches render-time crashes so the user sees an
 * actionable recovery screen (with the error detail) instead of a blank page.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, info: null }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surfaced in the browser console for troubleshooting; swap for a logging
    // service (Sentry, etc.) when one is wired up.
    console.error('Uncaught render error:', error, info.componentStack)
    this.setState({ info })
  }

  handleReload = () => {
    this.setState({ error: null, info: null })
    window.location.reload()
  }

  render() {
    const { error, info } = this.state
    if (!error) return this.props.children

    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
        <div className="max-w-lg w-full bg-slate-900 border border-rose-500/40 rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2 text-rose-400">
            <span className="text-xl">⚠</span>
            <h1 className="text-lg font-semibold">Something broke</h1>
          </div>
          <p className="text-sm text-slate-400">
            The app hit an unexpected error and stopped rendering. Reloading
            usually fixes it. If it keeps happening, the detail below helps debugging.
          </p>
          <pre className="text-xs bg-slate-950 border border-slate-800 rounded-lg p-3 overflow-auto max-h-48 text-rose-300 whitespace-pre-wrap">
            {error.message}
            {info?.componentStack ? `\n${info.componentStack}` : ''}
          </pre>
          <button
            onClick={this.handleReload}
            className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors"
          >
            Reload app
          </button>
        </div>
      </div>
    )
  }
}
