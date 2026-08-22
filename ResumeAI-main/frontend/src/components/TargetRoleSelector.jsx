import { BriefcaseBusiness } from 'lucide-react'
import { TARGET_ROLES } from '../constants/targetRoles'

export default function TargetRoleSelector({ value, onChange, disabled = false }) {
  return (
    <div className="glass-card p-5 md:p-7">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
        <BriefcaseBusiness size={18} color="#10b981" aria-hidden="true" />
        <div>
          <label htmlFor="target-role-select" style={{ fontWeight: 600, fontSize: 16, color: 'var(--text-primary)' }}>
            Target Role
          </label>
          <p style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 3 }}>
            Used to tailor resume guidance; it does not change the scoring weights.
          </p>
        </div>
      </div>
      <select
        id="target-role-select"
        className="input-field"
        value={value}
        onChange={event => onChange(event.target.value)}
        disabled={disabled}
        style={{ width: '100%', minHeight: 48 }}
      >
        {TARGET_ROLES.map(role => (
          <option key={role.value} value={role.value}>{role.label}</option>
        ))}
      </select>
    </div>
  )
}
