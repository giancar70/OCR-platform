'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { EyeIcon } from '@/components/EyeIcon'

interface FieldErrors {
  email?: string
  password?: string
  confirm?: string
}

export default function RegisterPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [serverError, setServerError] = useState('')
  const [loading, setLoading] = useState(false)

  const validate = (): boolean => {
    const errs: FieldErrors = {}
    if (!email.trim()) errs.email = 'Email is required'
    else if (!/^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i.test(email)) errs.email = 'Invalid email format'
    if (password.length < 8) errs.password = 'At least 8 characters required'
    if (password !== confirm) errs.confirm = 'Passwords do not match'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setServerError('')
    if (!validate()) return

    setLoading(true)
    try {
      await api.post('/auth/register', { email: email.trim(), password })
      const loginRes = await api.post('/auth/login', { email: email.trim(), password })
      localStorage.setItem('token', loginRes.data.access_token)
      router.push('/documents')
    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (err.response?.status === 409) {
        setErrors({ email: 'Email already taken' })
      } else if (typeof detail === 'string') {
        setServerError(detail)
      } else if (Array.isArray(detail)) {
        const fieldErrs: FieldErrors = {}
        for (const d of detail) {
          const field = d.loc?.[d.loc.length - 1]
          if (field === 'email') fieldErrs.email = d.msg
          if (field === 'password') fieldErrs.password = d.msg
        }
        setErrors(fieldErrs)
      } else {
        setServerError('Registration failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-slate-800">Create account</h1>
          <p className="text-slate-500 text-sm mt-1">OCR Platform</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); setErrors(p => ({ ...p, email: undefined})) }}
              className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${errors.email ? 'border-red-400' : 'border-slate-300'}`}
              placeholder="admin@admin.com"
              required
            />
            {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => { setPassword(e.target.value); setErrors(p => ({...p, password: undefined})) }}
                className={`w-full border rounded-lg px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${errors.password ? 'border-red-400' : 'border-slate-300'}`}
                placeholder="min. 8 characters"
                autoComplete="new-password"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(v => !v)}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-400 hover:text-slate-600"
                tabIndex={-1}
              >
                <EyeIcon open={showPassword} />
              </button>
            </div>
            {errors.password && <p className="text-red-500 text-xs mt-1">{errors.password}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Confirm password</label>
            <div className="relative">
              <input
                type={showConfirm ? 'text' : 'password'}
                value={confirm}
                onChange={(e) => { setConfirm(e.target.value); setErrors(p => ({...p, confirm: undefined})) }}
                className={`w-full border rounded-lg px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${errors.confirm ? 'border-red-400' : 'border-slate-300'}`}
                placeholder="repeat password"
                autoComplete="new-password"
                required
              />
              <button
                type="button"
                onClick={() => setShowConfirm(v => !v)}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-400 hover:text-slate-600"
                tabIndex={-1}
              >
                <EyeIcon open={showConfirm} />
              </button>
            </div>
            {errors.confirm && <p className="text-red-500 text-xs mt-1">{errors.confirm}</p>}
          </div>

          {serverError && (
            <p className="text-red-500 text-sm text-center bg-red-50 py-2 rounded-lg">{serverError}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold rounded-lg py-2.5 text-sm transition-colors"
          >
            {loading ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="text-center text-xs text-slate-400 mt-6">
          Already have an account?{' '}
          <a href="/login" className="text-blue-600 hover:underline font-medium">
            Sign in
          </a>
        </p>
      </div>
    </div>
  )
}
