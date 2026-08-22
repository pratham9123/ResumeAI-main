import { Link } from 'react-router-dom'

export function ResultsLoadingState() {
  return (
    <div aria-live="polite" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 64px)' }}>
      <div style={{ textAlign: 'center' }}>
        <div aria-hidden="true" style={{ width: 48, height: 48, border: '3px solid var(--border)', borderTopColor: '#3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 16px' }} />
        <p style={{ color: 'var(--text-secondary)' }}>Loading results...</p>
      </div>
    </div>
  )
}

export function ResultsErrorState() {
  return (
    <div role="alert" style={{ textAlign: 'center', padding: '80px 24px' }}>
      <p style={{ color: 'var(--text-secondary)', fontSize: 16 }}>Result not found</p>
      <Link to="/upload" className="btn-primary" style={{ marginTop: 16 }}>Analyze New Resume</Link>
    </div>
  )
}
