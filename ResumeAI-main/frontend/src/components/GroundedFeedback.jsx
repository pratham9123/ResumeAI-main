import { AlertTriangle, BookOpen, CheckCircle, Lightbulb, Sparkles, Target } from 'lucide-react'

function SourceDetails({ sourceIds = [], sourceCatalog = [] }) {
  if (!sourceIds.length) return null
  const knownSources = sourceIds.map(id => sourceCatalog.find(source => source.id === id))

  return (
    <div style={{ marginTop: 10 }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, borderRadius: 999, padding: '4px 9px', background: 'rgba(59,130,246,0.1)', color: '#3b82f6', fontSize: 11, fontWeight: 600 }}>
        <BookOpen size={11} aria-hidden="true" /> Grounded in resume guidance
      </span>
      <details style={{ marginTop: 8 }}>
        <summary style={{ cursor: 'pointer', color: 'var(--text-secondary)', fontSize: 12 }}>Why this recommendation?</summary>
        <div style={{ marginTop: 7, color: 'var(--text-muted)', fontSize: 12, lineHeight: 1.6 }}>
          <div>Sources: {sourceIds.join(', ')}</div>
          {knownSources.some(Boolean) && (
            <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
              {knownSources.filter(Boolean).map(source => <li key={source.id}>{source.title || source.id}</li>)}
            </ul>
          )}
        </div>
      </details>
    </div>
  )
}

function FeedbackCard({ children, accent = '#3b82f6' }) {
  return (
    <div style={{ padding: '14px 16px', background: 'rgba(var(--overlay-rgb),0.025)', border: '1px solid var(--border)', borderLeft: `3px solid ${accent}`, borderRadius: 10 }}>
      {children}
    </div>
  )
}

function SectionTitle({ icon, children }) {
  return (
    <h3 style={{ fontWeight: 600, fontSize: 15, color: 'var(--text-primary)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
      {icon}{children}
    </h3>
  )
}

export default function GroundedFeedback({ feedback, legacyFeedback = '', legacySuggestions = [], rag }) {
  const structured = feedback?.summary ? feedback : null
  const sources = rag?.sources || []

  if (!structured && !legacyFeedback && !legacySuggestions?.length) {
    return (
      <div className="glass-card p-5 md:p-7">
        <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>No AI feedback is available for this analysis.</p>
      </div>
    )
  }

  return (
    <div style={{ display: 'grid', gap: 20 }}>
      {rag?.enabled && rag?.fallbackUsed && (
        <div role="status" style={{ padding: '13px 16px', border: '1px solid rgba(245,158,11,0.25)', background: 'rgba(245,158,11,0.08)', borderRadius: 10, color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6 }}>
          Resume guidance references were temporarily unavailable. Your scores are unchanged, and the feedback below was generated from your resume and job description.
        </div>
      )}

      {(structured?.summary || legacyFeedback) && (
        <div className="glass-card p-5 md:p-7">
          <SectionTitle icon={<Sparkles size={16} color="#8b5cf6" aria-hidden="true" />}>Grounded Summary</SectionTitle>
          <p style={{ color: 'var(--text-secondary)', lineHeight: 1.8, fontSize: 15 }}>{structured?.summary || legacyFeedback}</p>
        </div>
      )}

      {structured?.strengths?.length > 0 && (
        <div className="glass-card p-5 md:p-7">
          <SectionTitle icon={<CheckCircle size={16} color="#10b981" aria-hidden="true" />}>Strengths</SectionTitle>
          <div style={{ display: 'grid', gap: 10 }}>
            {structured.strengths.map((item, index) => (
              <FeedbackCard key={`${item.strength}-${index}`} accent="#10b981">
                <strong style={{ color: 'var(--text-primary)', fontSize: 14 }}>{item.strength}</strong>
                <p style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6, marginTop: 5 }}>{item.evidence}</p>
              </FeedbackCard>
            ))}
          </div>
        </div>
      )}

      {structured?.critical_gaps?.length > 0 && (
        <div className="glass-card p-5 md:p-7">
          <SectionTitle icon={<AlertTriangle size={16} color="#f43f5e" aria-hidden="true" />}>Critical Gaps</SectionTitle>
          <div style={{ display: 'grid', gap: 10 }}>
            {structured.critical_gaps.map((item, index) => (
              <FeedbackCard key={`${item.gap}-${index}`} accent="#f43f5e">
                <strong style={{ color: 'var(--text-primary)', fontSize: 14 }}>{item.gap}</strong>
                <p style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6, marginTop: 5 }}>{item.evidence}</p>
              </FeedbackCard>
            ))}
          </div>
        </div>
      )}

      {structured?.section_feedback?.length > 0 && (
        <div className="glass-card p-5 md:p-7">
          <SectionTitle icon={<BookOpen size={16} color="#3b82f6" aria-hidden="true" />}>Section Feedback</SectionTitle>
          <div style={{ display: 'grid', gap: 12 }}>
            {structured.section_feedback.map((item, index) => (
              <FeedbackCard key={`${item.section}-${index}`}>
                <strong style={{ color: 'var(--text-primary)', textTransform: 'capitalize' }}>{item.section}</strong>
                <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 5 }}>{item.assessment}</p>
                <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.65, marginTop: 7 }}>{item.recommendation}</p>
                <SourceDetails sourceIds={item.source_ids} sourceCatalog={sources} />
              </FeedbackCard>
            ))}
          </div>
        </div>
      )}

      {structured?.rewritten_bullets?.length > 0 && (
        <div className="glass-card p-5 md:p-7">
          <SectionTitle icon={<Lightbulb size={16} color="#f59e0b" aria-hidden="true" />}>Rewritten Bullets</SectionTitle>
          <div style={{ display: 'grid', gap: 14 }}>
            {structured.rewritten_bullets.map((item, index) => (
              <FeedbackCard key={`${item.original}-${index}`} accent="#f59e0b">
                <p style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 7 }}><strong>Original:</strong> {item.original}</p>
                <p style={{ color: 'var(--text-primary)', fontSize: 14, lineHeight: 1.65 }}><strong>Improved:</strong> {item.improved}</p>
                <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 7 }}>{item.reason}</p>
                {item.requires_user_metric && (
                  <div role="alert" style={{ color: '#f59e0b', fontSize: 12, fontWeight: 600, marginTop: 9 }}>
                    Add a verified metric before using this bullet.
                  </div>
                )}
                <SourceDetails sourceIds={item.source_ids} sourceCatalog={sources} />
              </FeedbackCard>
            ))}
          </div>
        </div>
      )}

      {structured?.priority_actions?.length > 0 && (
        <div className="glass-card p-5 md:p-7">
          <SectionTitle icon={<Target size={16} color="#8b5cf6" aria-hidden="true" />}>Priority Actions</SectionTitle>
          <div style={{ display: 'grid', gap: 10 }}>
            {structured.priority_actions.map((item, index) => (
              <FeedbackCard key={`${item.action}-${index}`} accent={item.priority === 'high' ? '#f43f5e' : '#8b5cf6'}>
                <span style={{ textTransform: 'uppercase', fontSize: 10, color: 'var(--text-muted)', fontWeight: 700 }}>{item.priority} priority</span>
                <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.65, marginTop: 5 }}>{item.action}</p>
                <SourceDetails sourceIds={item.source_ids} sourceCatalog={sources} />
              </FeedbackCard>
            ))}
          </div>
        </div>
      )}

      {structured?.recommended_keywords?.length > 0 && (
        <div className="glass-card p-5 md:p-7">
          <SectionTitle icon={<Target size={16} color="#10b981" aria-hidden="true" />}>Recommended Keywords</SectionTitle>
          <div style={{ display: 'grid', gap: 10 }}>
            {structured.recommended_keywords.map((item, index) => (
              <FeedbackCard key={`${item.keyword}-${index}`} accent="#10b981">
                <strong style={{ color: 'var(--text-primary)', fontSize: 14 }}>{item.keyword}</strong>
                <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 5 }}>{item.reason}</p>
                <SourceDetails sourceIds={item.source_ids} sourceCatalog={sources} />
              </FeedbackCard>
            ))}
          </div>
        </div>
      )}

      {!structured && legacySuggestions?.length > 0 && (
        <div className="glass-card p-5 md:p-7">
          <SectionTitle icon={<Lightbulb size={16} color="#10b981" aria-hidden="true" />}>Improvement Suggestions</SectionTitle>
          <div style={{ display: 'grid', gap: 10 }}>
            {legacySuggestions.map((suggestion, index) => (
              <FeedbackCard key={`${suggestion}-${index}`} accent="#10b981">
                <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6 }}>{suggestion}</p>
              </FeedbackCard>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
