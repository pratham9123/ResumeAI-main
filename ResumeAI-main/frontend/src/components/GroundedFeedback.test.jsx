import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import GroundedFeedback from './GroundedFeedback'
import { ResultsErrorState, ResultsLoadingState } from './AnalysisStates'

const structuredFeedback = {
  summary: 'The resume aligns with the backend role but needs stronger project evidence.',
  strengths: [{ strength: 'Python experience', evidence: 'Python appears in the projects section.' }],
  critical_gaps: [{ gap: 'Deployment evidence', basis: 'comparison', evidence: 'The job asks for deployment experience.' }],
  section_feedback: [{
    section: 'projects',
    assessment: 'The architecture is named without explaining responsibilities.',
    recommendation: 'Describe service boundaries and deployment choices.',
    source_ids: ['backend-001'],
  }],
  rewritten_bullets: [{
    original: 'Built a backend API.',
    improved: 'Built a backend API and documented its service boundaries.',
    reason: 'Adds architectural context without inventing results.',
    source_ids: ['backend-001'],
    requires_user_metric: true,
  }],
  priority_actions: [{ action: 'Clarify project architecture.', priority: 'high', source_ids: ['backend-001'] }],
  recommended_keywords: [{ keyword: 'Docker', reason: 'Required by the job description.', source_ids: [] }],
}

const rag = {
  enabled: true,
  used: true,
  fallbackUsed: false,
  sources: [{ id: 'backend-001', title: 'Backend project guidance', category: 'project_bullets' }],
}

describe('GroundedFeedback', () => {
  it('renders every structured feedback section', () => {
    render(<GroundedFeedback feedback={structuredFeedback} rag={rag} />)

    expect(screen.getByText('Grounded Summary')).toBeInTheDocument()
    expect(screen.getByText('Strengths')).toBeInTheDocument()
    expect(screen.getByText('Critical Gaps')).toBeInTheDocument()
    expect(screen.getByText('Section Feedback')).toBeInTheDocument()
    expect(screen.getByText('Rewritten Bullets')).toBeInTheDocument()
    expect(screen.getByText('Priority Actions')).toBeInTheDocument()
    expect(screen.getByText('Recommended Keywords')).toBeInTheDocument()
  })

  it('shows source labels and expandable explanations without similarity scores', () => {
    render(<GroundedFeedback feedback={structuredFeedback} rag={rag} />)

    expect(screen.getAllByText('Grounded in resume guidance').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Why this recommendation?').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Sources: backend-001/).length).toBeGreaterThan(0)
    expect(screen.queryByText('0.78')).not.toBeInTheDocument()
  })

  it('warns users to supply a verified metric', () => {
    render(<GroundedFeedback feedback={structuredFeedback} rag={rag} />)

    expect(screen.getByText('Add a verified metric before using this bullet.')).toBeInTheDocument()
  })

  it('shows a non-technical fallback message', () => {
    render(
      <GroundedFeedback
        legacyFeedback="Feedback based on the supplied documents."
        rag={{ enabled: true, used: false, fallbackUsed: true, sources: [] }}
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent('guidance references were temporarily unavailable')
  })

  it('renders legacy analyses without RAG fields', () => {
    render(
      <GroundedFeedback
        legacyFeedback="Legacy feedback"
        legacySuggestions={['Legacy suggestion']}
      />,
    )

    expect(screen.getByText('Legacy feedback')).toBeInTheDocument()
    expect(screen.getByText('Legacy suggestion')).toBeInTheDocument()
  })

  it('renders an explicit empty state', () => {
    render(<GroundedFeedback />)
    expect(screen.getByText('No AI feedback is available for this analysis.')).toBeInTheDocument()
  })
})

describe('result request states', () => {
  it('renders loading and error states clearly', () => {
    const loading = render(<ResultsLoadingState />)
    expect(screen.getByText('Loading results...')).toBeInTheDocument()
    loading.unmount()

    render(<MemoryRouter><ResultsErrorState /></MemoryRouter>)
    expect(screen.getByRole('alert')).toHaveTextContent('Result not found')
    expect(screen.getByRole('link', { name: 'Analyze New Resume' })).toHaveAttribute('href', '/upload')
  })
})
