import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import api from '../api'
import { Clock, ArrowRight, Zap, Trash2, Award } from 'lucide-react'
import toast from 'react-hot-toast'

const GRADE = (s) => s >= 90 ? { label: 'Excellent', color: '#10b981' } : s >= 75 ? { label: 'Good', color: '#3b82f6' } : s >= 60 ? { label: 'Fair', color: '#f59e0b' } : { label: 'Needs Work', color: '#f43f5e' }

function SkeletonCard() {
  return (
    <div className="glass-card" style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          <div className="shimmer" style={{ height: 16, width: '60%', marginBottom: 10 }} />
          <div className="shimmer" style={{ height: 12, width: '40%', marginBottom: 16 }} />
          <div style={{ display: 'flex', gap: 8 }}>
            {[1, 2, 3].map(i => <div key={i} className="shimmer" style={{ height: 24, width: 70, borderRadius: 999 }} />)}
          </div>
        </div>
        <div className="shimmer" style={{ width: 56, height: 56, borderRadius: '50%' }} />
      </div>
    </div>
  )
}

export default function HistoryPage() {
  const { getToken } = useAuth()
  const [analyses, setAnalyses] = useState([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(null)

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const token = await getToken()
        const { data } = await api.get('/api/history', { headers: { Authorization: `Bearer ${token}` } })
        setAnalyses(data.analyses || [])
      } catch {
        toast.error('Failed to load history')
      } finally {
        setLoading(false)
      }
    }
    fetchHistory()
  }, [])

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this analysis?')) return
    setDeleting(id)
    try {
      const token = await getToken()
      await api.delete(`/api/result/${id}`, { headers: { Authorization: `Bearer ${token}` } })
      setAnalyses(prev => prev.filter(a => a._id !== id))
      toast.success('Analysis deleted')
    } catch {
      toast.error('Failed to delete')
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="max-w-[900px] mx-auto py-8 px-4 md:py-10 md:px-6 min-h-[calc(100vh-64px)]">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 32, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 800, fontSize: 30, color: 'var(--text-primary)', marginBottom: 6 }}>
            Analysis <span className="gradient-text">History</span>
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>Track all your resume analyses and score progression</p>
        </div>
        <Link to="/upload" className="btn-primary" style={{ fontSize: 13, padding: '10px 20px' }}>
          <Zap size={15} /> New Analysis
        </Link>
      </div>

      {/* Stats bar */}
      {!loading && analyses.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 md:gap-4 mb-7">
          {[
            { label: 'Total Analyses', value: analyses.length, color: '#3b82f6' },
            { label: 'Best Score', value: `${Math.max(...analyses.map(a => a.score))}%`, color: '#10b981' },
            { label: 'Average Score', value: `${Math.round(analyses.reduce((a, b) => a + b.score, 0) / analyses.length)}%`, color: '#8b5cf6' },
          ].map(s => (
            <div key={s.label} className="glass-card" style={{ padding: '16px 20px', textAlign: 'center' }}>
              <div style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 800, fontSize: 26, color: s.color }}>{s.value}</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* List */}
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
        </div>
      ) : analyses.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '80px 24px' }}>
          <div style={{ width: 72, height: 72, borderRadius: 20, background: 'rgba(59,130,246,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px' }}>
            <Clock size={32} color="#3b82f6" />
          </div>
          <h3 style={{ fontWeight: 600, fontSize: 18, color: 'var(--text-primary)', marginBottom: 8 }}>No analyses yet</h3>
          <p style={{ color: 'var(--text-muted)', marginBottom: 24, fontSize: 14 }}>Upload your first resume to see results here</p>
          <Link to="/upload" className="btn-primary">Start Analyzing</Link>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {analyses.map((a, i) => {
            const grade = GRADE(a.score)
            return (
              <div key={a._id} className="glass-card animate-fade-up p-5 md:p-6" style={{ animationDelay: `${i * 60}ms` }}>
                <div className="flex flex-col sm:flex-row items-start justify-between gap-4 md:gap-6">
                  <div className="w-full sm:w-auto sm:flex-1">
                    {/* JD snippet */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                      <Award size={14} color={grade.color} />
                      <span style={{ fontSize: 12, fontWeight: 600, color: grade.color }}>{grade.label}</span>
                      <span style={{ width: 3, height: 3, borderRadius: '50%', background: 'var(--text-muted)' }} />
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{new Date(a.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                    </div>
                    <p style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.5, marginBottom: 12, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                      {a.job_description?.slice(0, 160)}...
                    </p>
                    {/* Skill badges */}
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {a.matched_skills?.slice(0, 5).map(s => (
                        <span key={s} className="skill-badge skill-badge-matched" style={{ fontSize: 11 }}>{s}</span>
                      ))}
                      {a.missing_skills?.slice(0, 3).map(s => (
                        <span key={s} className="skill-badge skill-badge-missing" style={{ fontSize: 11 }}>{s}</span>
                      ))}
                    </div>
                  </div>

                  {/* Score + actions */}
                  <div className="flex flex-row sm:flex-col items-center justify-between sm:justify-start gap-4 sm:gap-3 shrink-0 w-full sm:w-auto mt-2 sm:mt-0 pt-4 sm:pt-0 border-t border-[var(--border)] sm:border-0">
                    <div style={{ position: 'relative', width: 64, height: 64 }}>
                      <svg width="64" height="64" viewBox="0 0 64 64">
                        <circle cx="32" cy="32" r="26" fill="none" stroke="var(--border)" strokeWidth="5" />
                        <circle cx="32" cy="32" r="26" fill="none" stroke={grade.color} strokeWidth="5"
                          strokeDasharray={2 * Math.PI * 26}
                          strokeDashoffset={2 * Math.PI * 26 * (1 - a.score / 100)}
                          strokeLinecap="round"
                          style={{ transform: 'rotate(-90deg)', transformOrigin: '32px 32px' }} />
                      </svg>
                      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Outfit, sans-serif', fontWeight: 800, fontSize: 16, color: grade.color }}>
                        {a.score}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <Link to={`/results/${a._id}`} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 14px', background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 8, color: '#3b82f6', textDecoration: 'none', fontSize: 12, fontWeight: 500, whiteSpace: 'nowrap' }}>
                        View <ArrowRight size={12} />
                      </Link>
                      <button onClick={() => handleDelete(a._id)} disabled={deleting === a._id}
                        style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 10px', background: 'transparent', border: '1px solid rgba(244,63,94,0.2)', borderRadius: 8, color: '#f43f5e', cursor: 'pointer', fontSize: 12 }}>
                        {deleting === a._id ? '...' : <Trash2 size={12} />}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
