import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { useAuth } from '../contexts/AuthContext'
import api from '../api'
import toast from 'react-hot-toast'
import { Upload, FileText, Briefcase, Zap, CheckCircle, X } from 'lucide-react'
import TargetRoleSelector from '../components/TargetRoleSelector'

const STEPS = ['Upload Resume', 'Add Job Description', 'Analyze']

export default function UploadPage() {
  const [file, setFile] = useState(null)
  const [jobDescription, setJobDescription] = useState('')
  const [targetRole, setTargetRole] = useState('software_engineer')
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(0)
  const [progress, setProgress] = useState(0)
  const [progressLabel, setProgressLabel] = useState('')
  const { user, getToken } = useAuth()
  const navigate = useNavigate()

  const onDrop = useCallback((accepted) => {
    if (accepted[0]) {
      setFile(accepted[0])
      setStep(1)
      toast.success(`📄 ${accepted[0].name} uploaded!`)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    maxSize: 5 * 1024 * 1024,
    onDropRejected: (files) => {
      const err = files[0]?.errors[0]
      if (err?.code === 'file-too-large') toast.error('File too large. Max 5MB')
      else toast.error('Only PDF files are accepted')
    }
  })

  const handleAnalyze = async () => {
    if (!file) return toast.error('Please upload a resume PDF')
    if (!jobDescription.trim() || jobDescription.trim().length < 30) return toast.error('Please enter a valid job description (min 30 chars)')

    setLoading(true)
    setStep(2)
    const progressSteps = [
      { p: 10, label: '📄 Extracting text from PDF...' },
      { p: 30, label: '🔍 Extracting skills...' },
      { p: 55, label: '🧠 Computing semantic similarity...' },
      { p: 75, label: '📊 Calculating score...' },
      { p: 90, label: '✨ Generating AI feedback...' },
      { p: 98, label: '💾 Saving analysis...' },
    ]

    let stepIdx = 0
    const interval = setInterval(() => {
      if (stepIdx < progressSteps.length) {
        setProgress(progressSteps[stepIdx].p)
        setProgressLabel(progressSteps[stepIdx].label)
        stepIdx++
      }
    }, 2500)

    try {
      const token = await getToken()
      const formData = new FormData()
      formData.append('resume', file)
      formData.append('job_description', jobDescription)
      formData.append('target_role', targetRole)
      formData.append('uid', user.uid)

      const { data } = await api.post('/api/analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data', Authorization: `Bearer ${token}` },
      })
      clearInterval(interval)
      setProgress(100)
      setProgressLabel('✅ Analysis complete!')
      toast.success('Analysis complete!')
      setTimeout(() => navigate(`/results/${data.analysisId}`), 800)
    } catch (err) {
      clearInterval(interval)
      setLoading(false)
      setStep(1)
      setProgress(0)
      const msg = err.response?.data?.error || 'Analysis failed. Please try again.'
      toast.error(msg)
    }
  }

  return (
    <div className="max-w-[820px] mx-auto py-8 px-4 md:py-10 md:px-6 min-h-[calc(100vh-64px)]">
      {/* Header */}
      <div style={{ marginBottom: 36 }}>
        <h1 style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 800, fontSize: 32, color: 'var(--text-primary)', marginBottom: 8 }}>
          Analyze Your <span className="gradient-text">Resume</span>
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 15 }}>Upload your PDF resume and paste a job description to get your ATS score</p>
      </div>

      {/* Steps indicator */}
      <div className="flex items-center gap-2 md:gap-0 mb-8 overflow-x-auto pb-2 hide-scrollbar w-full">
        {STEPS.map((s, i) => (
          <div key={s} className="flex items-center shrink-0 md:flex-1">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, background: step >= i ? 'linear-gradient(135deg,#3b82f6,#8b5cf6)' : 'rgba(var(--overlay-rgb),0.06)', color: step >= i ? '#fff' : 'var(--text-muted)', transition: 'all 0.3s', flexShrink: 0 }}>
                {step > i ? <CheckCircle size={14} /> : i + 1}
              </div>
              <span style={{ fontSize: 13, fontWeight: 500, color: step >= i ? 'var(--text-secondary)' : 'var(--text-muted)', whiteSpace: 'nowrap' }}>{s}</span>
            </div>
            {i < STEPS.length - 1 && <div style={{ flex: 1, minWidth: 40, height: 1, background: step > i ? 'linear-gradient(to right,#3b82f6,#8b5cf6)' : 'rgba(var(--overlay-rgb),0.06)', margin: '0 12px', transition: 'all 0.5s' }} />}
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-5">
        {/* Resume Upload */}
        <div className="glass-card p-5 md:p-7">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
            <FileText size={18} color="#3b82f6" />
            <h2 style={{ fontWeight: 600, fontSize: 16, color: 'var(--text-primary)' }}>Resume (PDF)</h2>
          </div>

          {file ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '16px 20px', background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: 12 }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(16,185,129,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <FileText size={18} color="#10b981" />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>{file.name}</div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>{(file.size / 1024).toFixed(0)} KB</div>
              </div>
              <button onClick={() => { setFile(null); setStep(0) }} disabled={loading} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', padding: 4 }}>
                <X size={16} />
              </button>
            </div>
          ) : (
            <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`}
              id="resume-dropzone">
              <input {...getInputProps()} id="resume-file-input" />
              <div className="animate-float">
                <Upload size={36} color="#3b82f6" style={{ margin: '0 auto 14px' }} />
              </div>
              <p style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6, fontSize: 15 }}>
                {isDragActive ? 'Drop your PDF here...' : 'Drag & drop your resume PDF'}
              </p>
              <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>or click to browse · Max 5MB</p>
            </div>
          )}
        </div>

        <TargetRoleSelector
          value={targetRole}
          onChange={setTargetRole}
          disabled={loading}
        />

        {/* Job Description */}
        <div className="glass-card p-5 md:p-7">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
            <Briefcase size={18} color="#8b5cf6" />
            <h2 style={{ fontWeight: 600, fontSize: 16, color: 'var(--text-primary)' }}>Job Description</h2>
          </div>
          <textarea
            id="job-description-input"
            className="input-field"
            style={{ minHeight: 200, resize: 'vertical', lineHeight: 1.7 }}
            placeholder="Paste the full job description here...&#10;&#10;Include the required skills, responsibilities, and qualifications for best results."
            value={jobDescription}
            onChange={e => { setJobDescription(e.target.value); if (e.target.value.length > 30 && file) setStep(2) }}
            disabled={loading}
          />
          <div style={{ textAlign: 'right', marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
            {jobDescription.length} chars {jobDescription.length < 30 && jobDescription.length > 0 && <span style={{ color: '#f59e0b' }}>(min 30)</span>}
          </div>
        </div>

        {/* Progress / Analyze */}
        {loading ? (
          <div className="glass-card p-5 md:p-7">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <div style={{ width: 20, height: 20, border: '2px solid rgba(59,130,246,0.3)', borderTopColor: '#3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
              <span style={{ fontWeight: 500, color: 'var(--text-secondary)', fontSize: 14 }}>{progressLabel}</span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${progress}%`, background: 'linear-gradient(to right,#3b82f6,#8b5cf6)' }} />
            </div>
            <div style={{ textAlign: 'right', marginTop: 8, fontSize: 12, color: '#3b82f6', fontWeight: 600 }}>{progress}%</div>
          </div>
        ) : (
          <button
            id="analyze-btn"
            onClick={handleAnalyze}
            disabled={!file || !jobDescription.trim() || loading}
            className="btn-primary"
            style={{ width: '100%', justifyContent: 'center', padding: 16, fontSize: 16 }}
          >
            <Zap size={18} />
            Analyze My Resume with AI
          </button>
        )}
      </div>
    </div>
  )
}
