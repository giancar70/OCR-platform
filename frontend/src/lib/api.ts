import axios from 'axios'

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({ baseURL: `${API_URL}/v1` })

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('token')
    if (token) config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && typeof window !== 'undefined' && localStorage.getItem('token')) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export interface Document {
  id: string
  original_filename: string
  file_size: number
  mime_type: string
  status: 'uploaded' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
  ocr_text: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled'])
