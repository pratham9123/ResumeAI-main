import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import api from '../api'
import { CheckCircle, XCircle, Plus, Zap, ArrowLeft, History, TrendingUp, Award } from 'lucide-react'
import toast from 'react-hot-toast'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts'
import GroundedFeedback from '../components/GroundedFeedback'
import { ResultsErrorState, ResultsLoadingState } from '../components/AnalysisStates'

function ScoreRing({ score }) {
  const r = 60
  const circ = 2 * Math.PI * r
  const [displayed, setDisplayed] = useState(0)

  useEffect(() => {
    let start = 0
    const end = score
    const dur = 1500
    const step = end / (dur / 16)
    const t = setInterval(() => {
      start += step
      if (start >= end) { setDisplayed(end); clearInterval(t) }
      else setDisplayed(Math.floor(start))
    }, 16)
    return () => clearInterval(t)
  }, [score])

  const offset = circ - (displayed / 100) * circ
  const color = score >= 80 ? '#10b981' : score >= 60 ? '#f59e0b' : '#f43f5e'

  return (
    <div style={{ position: 'relative', width: 160, height: 160, margin: '0 auto' }}>
      <svg width="160" height="160" viewBox="0 0 160 160">
        <circle cx="80" cy="80" r={r} fill="none" stroke="var(--border)" strokeWidth="10" />
        <circle cx="80" cy="80" r={r} fill="none" stroke={color} strokeWidth="10"
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round" className="score-ring"
          style={{ transform: 'rotate(-90deg)', transformOrigin: '80px 80px', transition: 'stroke-dashoffset 0.05s linear, stroke 0.5s ease' }} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 800, fontSize: 38, color, lineHeight: 1 }}>{displayed}</span>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 500 }}>/ 100</span>
      </div>
    </div>
  )
}

const GRADE = (s) => s >= 90 ? { label: 'Excellent', color: '#10b981' } : s >= 75 ? { label: 'Good', color: '#3b82f6' } : s >= 60 ? { label: 'Fair', color: '#f59e0b' } : { label: 'Needs Work', color: '#f43f5e' }

export default function ResultsPage() {
  const { id } = useParams()
  const { getToken } = useAuth()
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')

  useEffect(() => {
    const fetchResult = async () => {
      try {
        const token = await getToken()
        const { data } = await api.get(`/api/result/${id}`, { headers: { Authorization: `Bearer ${token}` } })
        setResult(data)
        
        const histRes = await api.get(`/api/history`, { headers: { Authorization: `Bearer ${token}` } })
        if (histRes.data && histRes.data.analyses) {
          setHistory(histRes.data.analyses.slice(0, 5).reverse())
        }
      } catch {
        toast.error('Failed to load results')
      } finally {
        setLoading(false)
      }
    }
    fetchResult()
  }, [id])

  if (loading) return <ResultsLoadingState />
  if (!result) return <ResultsErrorState />

  const grade = GRADE(result.score)
  const radarData = [
    { skill: 'Core Skills', value: Math.round(result.breakdown?.core * 100 || 0) },
    { skill: 'Secondary Skills', value: Math.round(result.breakdown?.secondary * 100 || 0) },
    { skill: 'Experience', value: Math.round(result.breakdown?.experience * 100 || 0) },
    { skill: 'Semantic Match', value: Math.round(result.similarity_score * 100 || 0) },
    { skill: 'Overall', value: result.score },
  ]

  const tabs = ['overview', 'skills', 'ai-feedback']

  return (
    <div className="max-w-[1000px] mx-auto py-8 px-4 md:py-10 md:px-6 min-h-[calc(100vh-64px)]">
      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 32, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <Link to="/history" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)', textDecoration: 'none', fontSize: 13, marginBottom: 8 }}>
            <ArrowLeft size={14} /> Back to History
          </Link>
          <h1 style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 800, fontSize: 28, color: 'var(--text-primary)' }}>Analysis <span className="gradient-text">Results</span></h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 4 }}>{new Date(result.created_at).toLocaleString()}</p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <Link to="/upload" className="btn-primary" style={{ fontSize: 13, padding: '9px 18px' }}><Zap size={14} /> New Analysis</Link>
          <Link to="/history" className="btn-secondary" style={{ fontSize: 13, padding: '9px 18px' }}><History size={14} /> History</Link>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 24, flexDirection: 'column', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Tabs */}
          <div className="flex gap-1 mb-7 bg-[rgba(var(--overlay-rgb),0.03)] rounded-xl p-1 border border-[var(--border)] w-fit max-w-full overflow-x-auto hide-scrollbar">
        {tabs.map(t => (
          <button key={t} onClick={() => setActiveTab(t)}
            style={{ padding: '8px 18px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 500, fontFamily: 'Inter, sans-serif', transition: 'all 0.2s', background: activeTab === t ? 'rgba(59,130,246,0.15)' : 'transparent', color: activeTab === t ? '#3b82f6' : 'var(--text-secondary)' }}>
            {t === 'overview' ? '📊 Overview' : t === 'skills' ? '🎯 Skills' : '✨ AI Feedback'}
          </button>
        ))}
      </div>

      {/* OVERVIEW TAB */}
      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gap: 20 }}>
          {/* Score + grade */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="glass-card p-6 md:p-8 text-center">
              <ScoreRing score={result.score} />
              <div style={{ marginTop: 16 }}>
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 14px', background: `${grade.color}1a`, border: `1px solid ${grade.color}40`, borderRadius: 999 }}>
                  <Award size={13} color={grade.color} />
                  <span style={{ color: grade.color, fontWeight: 600, fontSize: 13 }}>{grade.label} Match</span>
                </div>
                <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 10 }}>ATS Compatibility Score</p>
              </div>
            </div>

            {/* Breakdown */}
            <div className="glass-card p-5 md:p-7">
              <h3 style={{ fontWeight: 600, fontSize: 15, color: 'var(--text-primary)', marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
                <TrendingUp size={16} color="#3b82f6" /> Score Breakdown
              </h3>
              {[
                { label: 'Core Skills (40%)', value: result.breakdown?.core * 100 || 0, color: '#3b82f6' },
                { label: 'Resume Quality (40%)', value: result.breakdown?.quality * 100 || 0, color: '#8b5cf6' },
                { label: 'Semantic Similarity (10%)', value: result.similarity_score * 100 || 0, color: '#f59e0b' },
                { label: 'Experience Signal (10%)', value: result.breakdown?.experience * 100 || 0, color: '#10b981' },
              ].map(item => (
                <div key={item.label} style={{ marginBottom: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                    <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{item.label}</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: item.color }}>{Math.round(item.value)}%</span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${Math.round(item.value)}%`, background: item.color }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Radar chart */}
          <div className="glass-card p-5 md:p-7">
            <h3 style={{ fontWeight: 600, fontSize: 15, color: 'var(--text-primary)', marginBottom: 20 }}>Skill Radar</h3>
            <ResponsiveContainer width="100%" height={250}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="var(--border)" />
                <PolarAngleAxis dataKey="skill" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
                <Radar name="Score" dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} strokeWidth={2} />
                <Tooltip contentStyle={{ background: 'var(--bg-tooltip)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 13 }} formatter={(v) => [`${v}%`, 'Score']} />
              </RadarChart>
            </ResponsiveContainer>

            {/* Metric explanations */}
            <div style={{ marginTop: 24, borderTop: '1px solid var(--border)', paddingTop: 20 }}>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 14 }}>What each metric means</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {[
                  {
                    color: '#3b82f6',
                    dot: '⬤',
                    title: 'Core Skills',
                    desc: 'How many of the skills explicitly listed in the job description appear in your resume. This is the heaviest factor — a high score means your tech stack directly matches what the employer asked for.',
                  },
                  {
                    color: '#f59e0b',
                    dot: '⬤',
                    title: 'Semantic Similarity',
                    desc: 'How conceptually similar your resume is to the job description, even when the exact words differ. An AI model reads both documents and measures how aligned the meaning is — catching synonyms and related concepts.',
                  },
                  {
                    color: '#10b981',
                    dot: '⬤',
                    title: 'Experience Signal',
                    desc: 'An estimate of your seniority based on year spans in your work history, leadership keywords (led, managed, architected…), and internship mentions. It rewards demonstrated ownership, not just years.',
                  },
                  {
                    color: '#8b5cf6',
                    dot: '⬤',
                    title: 'Resume Quality',
                    desc: 'How strong your resume is on its own — independent of the job description. Covers resume structure, ATS formatting, achievements with numbers, contact completeness, and keyword density.',
                  },
                ].map(m => (
                  <div key={m.title} style={{ padding: '12px 14px', background: 'rgba(var(--overlay-rgb),0.02)', border: '1px solid rgba(var(--overlay-rgb),0.05)', borderRadius: 10, borderLeft: `3px solid ${m.color}` }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 6 }}>
                      <span style={{ color: m.color, fontSize: 9 }}>{m.dot}</span>
                      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{m.title}</span>
                    </div>
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.65, margin: 0 }}>{m.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
          
          {/* Section Scores */}
          {result.section_scores && Object.keys(result.section_scores).length > 0 && (
            <div className="glass-card p-5 md:p-7">
              <h3 style={{ fontWeight: 600, fontSize: 15, color: 'var(--text-primary)', marginBottom: 20 }}>Section Analysis (out of 10)</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {Object.entries(result.section_scores).map(([sec, score]) => {
                  const percent = score * 10
                  const color = percent >= 80 ? '#10b981' : percent >= 50 ? '#f59e0b' : '#f43f5e'
                  return (
                    <div key={sec}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                        <span style={{ fontSize: 13, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{sec}</span>
                        <span style={{ fontSize: 13, fontWeight: 600, color }}>{score}/10</span>
                      </div>
                      <div className="progress-bar" style={{ height: 6 }}>
                        <div className="progress-fill" style={{ width: `${percent}%`, background: color }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Trend Chart */}
          {history.length > 1 && (
            <div className="glass-card p-5 md:p-7">
              <h3 style={{ fontWeight: 600, fontSize: 15, color: 'var(--text-primary)', marginBottom: 20 }}>ATS Score Trend (Last 5)</h3>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={history}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="created_at" tickFormatter={(t) => new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: 'var(--bg-tooltip)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)' }} labelFormatter={(t) => new Date(t).toLocaleDateString()} />
                  <Line type="monotone" dataKey="score" stroke="#10b981" strokeWidth={3} dot={{ r: 4, fill: '#10b981' }} activeDot={{ r: 6 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* SKILLS TAB */}
      {activeTab === 'skills' && (
        <div style={{ display: 'grid', gap: 16 }}>
          <SkillSection title="✅ Matched Skills" skills={result.matched_skills} type="matched" count={result.matched_skills?.length} />
          <SkillSection title="❌ Missing Skills" skills={result.missing_skills} type="missing" count={result.missing_skills?.length} />
          <SkillSection title="✨ Extra Skills" skills={result.extra_skills} type="extra" count={result.extra_skills?.length} />
          

        </div>
      )}

      {/* AI FEEDBACK TAB */}
      {activeTab === 'ai-feedback' && (
        <GroundedFeedback
          feedback={result.generated_feedback}
          legacyFeedback={result.feedback}
          legacySuggestions={result.suggestions}
          rag={result.rag}
        />
      )}
        </div>
      </div>
    </div>
  )
}

function SkillSection({ title, skills = [], type, count }) {
  const typeMap = { matched: 'skill-badge-matched', missing: 'skill-badge-missing', extra: 'skill-badge-extra' }
  const iconMap = { matched: <CheckCircle size={11} />, missing: <XCircle size={11} />, extra: <Plus size={11} /> }
  const colorMap = { matched: '#10b981', missing: '#f43f5e', extra: '#3b82f6' }

  return (
    <div className="glass-card p-5 md:p-6">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h3 style={{ fontWeight: 600, fontSize: 15, color: 'var(--text-primary)' }}>{title}</h3>
        <span style={{ padding: '3px 10px', borderRadius: 999, fontSize: 12, fontWeight: 600, background: `${colorMap[type]}1a`, color: colorMap[type] }}>{count}</span>
      </div>
      {skills.length === 0 ? (
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>None found</p>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {skills.map(s => (
            <span key={s} className={`skill-badge ${typeMap[type]}`}>
              {iconMap[type]} {s}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
