// React class error boundary catches render errors in child trees and displays a fallback UI.
import { Component, ErrorInfo, ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return this.props.fallback ?? (
        <div className="p-6 rounded border border-red-500/20 bg-red-500/5 text-sm text-muted">
          <p className="font-medium text-red-400 mb-1">Something went wrong</p>
          <p className="font-mono text-xs">{this.state.error.message}</p>
        </div>
      )
    }
    return this.props.children
  }
}
