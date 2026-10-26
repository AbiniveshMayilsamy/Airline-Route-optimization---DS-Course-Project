import { Component, ReactNode, ErrorInfo } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          height: '100vh', background: '#0f172a', color: '#f1f5f9', fontFamily: 'Trebuchet MS, sans-serif', gap: 16
        }}>
          <div style={{ fontSize: 48 }}>✈️</div>
          <h2 style={{ margin: 0, color: '#ea580c' }}>Component Error</h2>
          <p style={{ color: '#94a3b8', maxWidth: 500, textAlign: 'center', margin: 0 }}>
            {this.state.error.message}
          </p>
          <button
            onClick={() => this.setState({ error: null })}
            style={{
              marginTop: 16, padding: '10px 24px', background: '#ea580c', color: '#fff',
              border: 'none', cursor: 'pointer', fontFamily: 'inherit', fontSize: 14
            }}
          >
            Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
