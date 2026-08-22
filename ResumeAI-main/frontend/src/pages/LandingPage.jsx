import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useEffect } from 'react'
import { Zap, ArrowRight, CheckCircle, Brain, BarChart3, Shield, Search, Layers, PieChart, FileText } from 'lucide-react'

const features = [
  { icon: Brain, title: 'AI-Powered Analysis', desc: 'Advanced NLP and semantic matching using Hugging Face transformers', color: '#3b82f6' },
  { icon: BarChart3, title: 'Detailed Scoring', desc: 'Weighted scoring engine with core, secondary, and experience breakdown', color: '#8b5cf6' },
  { icon: CheckCircle, title: 'Skill Gap Detection', desc: 'Instantly see matched, missing, and extra skills vs job requirements', color: '#10b981' },
  { icon: Shield, title: 'ATS Simulation', desc: 'Simulates how Applicant Tracking Systems evaluate your resume', color: '#f59e0b' },
]

const stats = [
  { value: '95%', label: 'Accuracy Rate' },
  { value: '2s', label: 'Analysis Time' },
  { value: '10K+', label: 'Skills Database' },
  { value: 'GPT-4', label: 'AI Powered' },
]

const howItWorks = [
  { step: '1', title: 'Text Extraction', desc: 'Your PDF resume is parsed to extract clean text, preserving the logical flow of your experience and skills.', icon: FileText, color: '#3b82f6' },
  { step: '2', title: 'Skill Identification', desc: 'Our NLP engine identifies hard skills, soft skills, and tools from both your resume and the job description.', icon: Search, color: '#8b5cf6' },
  { step: '3', title: 'Semantic Matching', desc: 'A Hugging Face transformer model calculates the semantic similarity between your experience and the job requirements.', icon: Layers, color: '#f59e0b' },
  { step: '4', title: 'Score Generation', desc: 'We combine keyword matches, semantic similarity, and resume quality metrics to generate your final ATS score.', icon: PieChart, color: '#10b981' },
]

export default function LandingPage() {
  const { user } = useAuth()
  const navigate = useNavigate()



  return (
    <div>
      {/* Hero */}
      <div className="hero-bg flex items-center py-10 px-4 md:py-[60px] md:px-6 min-h-[calc(100vh-64px)]">
        <div className="max-w-[900px] mx-auto text-center">
          {/* Badge */}
          <div className="animate-fade-up" style={{ animationDelay: '0ms', display: 'inline-flex', alignItems: 'center', gap: 8, padding: '8px 16px', background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.25)', borderRadius: 999, marginBottom: 32 }}>
            <Zap size={14} color="#3b82f6" />
            <span style={{ fontSize: 13, fontWeight: 500, color: '#3b82f6' }}>AI-Powered ATS Resume Analyzer</span>
          </div>

          {/* Headline */}
          <h1 className="animate-fade-up" style={{ animationDelay: '100ms', fontFamily: 'Outfit, sans-serif', fontSize: 'clamp(40px, 6vw, 72px)', fontWeight: 800, lineHeight: 1.1, marginBottom: 24, color: 'var(--text-primary)' }}>
            Land Your Dream Job<br />
            <span className="gradient-text">Beat the ATS System</span>
          </h1>

          {/* Subtitle */}
          <p className="animate-fade-up" style={{ animationDelay: '200ms', fontSize: 18, color: 'var(--text-secondary)', lineHeight: 1.7, maxWidth: 600, margin: '0 auto 40px', fontWeight: 400 }}>
            Upload your resume, paste a job description, and get an instant AI-powered match score with detailed skill gap analysis and personalized feedback.
          </p>

          {/* CTAs */}
          <div className="animate-fade-up" style={{ animationDelay: '300ms', display: 'flex', justifyContent: 'center', gap: 16, flexWrap: 'wrap' }}>
            <Link to={user ? '/upload' : '/login'} className="btn-primary" style={{ fontSize: 16, padding: '14px 32px' }}>
              {user ? 'Analyze a Resume' : 'Get Started Free'} <ArrowRight size={18} />
            </Link>
          </div>

          {/* Stats */}
          <div className="animate-fade-up" style={{ animationDelay: '400ms', display: 'flex', justifyContent: 'center', gap: 40, marginTop: 60, flexWrap: 'wrap' }}>
            {stats.map(s => (
              <div key={s.label} style={{ textAlign: 'center' }}>
                <div style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 800, fontSize: 28, background: 'linear-gradient(135deg,#3b82f6,#8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{s.value}</div>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Features */}
      <div className="py-12 px-4 md:py-20 md:px-6 max-w-[1100px] mx-auto">
        <div style={{ textAlign: 'center', marginBottom: 56 }}>
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 700, fontSize: 36, color: 'var(--text-primary)', marginBottom: 12 }}>
            Everything you need to <span className="gradient-text">get hired</span>
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 16 }}>Powered by state-of-the-art AI and NLP models</p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 20 }}>
          {features.map((f, i) => (
            <div key={f.title} className="glass-card animate-fade-up" style={{ animationDelay: `${i * 100}ms`, padding: 28 }}>
              <div style={{ width: 48, height: 48, borderRadius: 12, background: `${f.color}1a`, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
                <f.icon size={22} color={f.color} />
              </div>
              <h3 style={{ fontWeight: 600, fontSize: 16, color: 'var(--text-primary)', marginBottom: 8 }}>{f.title}</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* How it Works / Evaluation */}
      <div className="py-12 px-4 md:py-20 md:px-6 max-w-[1100px] mx-auto border-y border-[var(--border)]" style={{ background: 'rgba(var(--overlay-rgb), 0.02)' }}>
        <div style={{ textAlign: 'center', marginBottom: 56 }}>
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 700, fontSize: 36, color: 'var(--text-primary)', marginBottom: 12 }}>
            How your <span className="gradient-text">ATS Score</span> is evaluated
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 16, maxWidth: 600, margin: '0 auto' }}>
            We look beyond simple keyword matching. Our AI reads your resume like a human recruiter would, combined with the strict parsing rules of enterprise ATS software.
          </p>
        </div>

        <div className="flex flex-col gap-6 max-w-[800px] mx-auto">
          {howItWorks.map((item, i) => (
            <div key={item.step} className="glass-card animate-fade-up flex flex-col md:flex-row gap-6 items-center text-center md:text-left p-6 md:py-6 md:px-8" style={{ animationDelay: `${i * 100}ms` }}>
              <div style={{ flexShrink: 0, width: 64, height: 64, borderRadius: 16, background: `${item.color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
                <item.icon size={28} color={item.color} />
                <div style={{ position: 'absolute', top: -10, left: -10, width: 28, height: 28, borderRadius: '50%', background: item.color, color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 14, border: '4px solid var(--bg-primary)' }}>
                  {item.step}
                </div>
              </div>
              <div>
                <h3 style={{ fontWeight: 700, fontSize: 18, color: 'var(--text-primary)', marginBottom: 8 }}>{item.title}</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: 15, lineHeight: 1.6 }}>{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* CTA Banner */}
      <div className="py-12 px-4 md:py-20 md:px-6">
        <div className="max-w-[700px] mx-auto rounded-3xl p-8 md:p-[48px_40px] text-center" style={{ background: 'linear-gradient(135deg, rgba(59,130,246,0.15), rgba(139,92,246,0.15))', border: '1px solid rgba(59,130,246,0.25)' }}>
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 700, fontSize: 30, color: 'var(--text-primary)', marginBottom: 12 }}>Ready to get your score?</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: 28, fontSize: 15 }}>{user ? 'Upload your resume and job description to get instant feedback.' : 'Sign in with Google and analyze your first resume in seconds.'}</p>
          <Link to={user ? '/upload' : '/login'} className="btn-primary" style={{ fontSize: 15, padding: '13px 28px' }}>
            Start Analyzing <ArrowRight size={16} />
          </Link>
        </div>
      </div>
    </div>
  )
}
