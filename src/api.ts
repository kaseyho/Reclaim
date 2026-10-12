import type { Session } from './types'
import { authHeaders } from './auth'

const base = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
export class ApiError extends Error { constructor(message: string, public status: number) { super(message) } }
export async function api<T>(path: string, token?: string, body?: unknown, method = body === undefined ? 'GET' : 'POST'): Promise<T> {
  const response = await fetch(`${base}/api${path}`, {
    method, headers: { 'Content-Type': 'application/json', ...(path === '/config' || path === '/health' ? {} : await authHeaders(token)) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = data?.detail
    const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((e: { loc: string[]; msg: string }) => `${e.loc.slice(1).join(' ')}: ${e.msg}`).join('; ') : 'The server could not complete this action. Retry after checking your connection.'
    throw new ApiError(message, response.status)
  }
  return data as T
}
export const savedSession = () => { try { return JSON.parse(localStorage.getItem('reclaim-session') ?? 'null') as Session | null } catch { return null } }
export const saveSession = (session: Session) => localStorage.setItem('reclaim-session', JSON.stringify(session))
export const dollars = (minor: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: minor % 100 ? 2 : 0 }).format(minor / 100)
export const human = (value: string) => value.toLowerCase().replace(/_/g, ' ')
export const dateLabel = (value: string) => new Date(value).toLocaleDateString('en-SG', { day: 'numeric', month: 'short' })
export const windowLabel = (start: string, end: string) => `${dateLabel(start)} · ${new Date(start).toLocaleTimeString('en-SG', { hour: 'numeric', minute: '2-digit' })}–${new Date(end).toLocaleTimeString('en-SG', { hour: 'numeric', minute: '2-digit' })}`
export const localDate = (date: string) => { const d = new Date(date); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16) }
export const isoDate = (date: string) => new Date(date).toISOString()
