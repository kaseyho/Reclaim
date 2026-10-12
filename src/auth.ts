import type { Config } from './types'
type AuthSession = { access_token: string; refresh_token: string; expires_at: number }
let config: Config | undefined
let refreshing: Promise<AuthSession> | undefined
export function configureAuth(value: Config) { config = value }
export function savedAuth(): AuthSession | null { try { return JSON.parse(localStorage.getItem('reclaim-auth') ?? 'null') } catch { return null } }
export function clearAuth() { localStorage.removeItem('reclaim-auth'); localStorage.removeItem('reclaim-session') }
function saveAuth(value: AuthSession) { localStorage.setItem('reclaim-auth', JSON.stringify({ access_token: value.access_token, refresh_token: value.refresh_token, expires_at: value.expires_at })); return value }
async function tokenRequest(grant: string, body: unknown): Promise<AuthSession> {
  if (!config?.supabase_url || !config.supabase_publishable_key) throw new Error('Account sign-in has not been configured by the operator.')
  const response = await fetch(`${config.supabase_url}/auth/v1/token?grant_type=${grant}`, { method: 'POST', headers: { 'Content-Type': 'application/json', apikey: config.supabase_publishable_key }, body: JSON.stringify(body) })
  const answer = await response.json()
  if (!response.ok || !answer.access_token) throw new Error(grant === 'password' ? 'Could not sign in with that email and password.' : 'Your sign-in expired. Please sign in again.')
  return saveAuth({ access_token: answer.access_token, refresh_token: answer.refresh_token, expires_at: answer.expires_at ?? Math.floor(Date.now() / 1000) + answer.expires_in })
}
export async function signIn(email: string, password: string) { clearAuth(); return tokenRequest('password', { email, password }) }
export async function accessToken() {
  const current = savedAuth()
  if (!current) throw new Error('Sign in to open your Reclaim workspace.')
  if (current.expires_at > Date.now() / 1000 + 30) return current.access_token
  if (!refreshing) refreshing = tokenRequest('refresh_token', { refresh_token: current.refresh_token }).catch(e => { clearAuth(); throw e }).finally(() => { refreshing = undefined })
  return (await refreshing).access_token
}
export async function authHeaders(workspaceToken?: string): Promise<Record<string, string>> {
  if (config?.auth_mode === 'supabase') return { Authorization: `Bearer ${await accessToken()}`, ...(workspaceToken ? { 'X-Workspace-Token': workspaceToken } : {}) }
  return workspaceToken ? { Authorization: `Bearer ${workspaceToken}` } : {}
}
