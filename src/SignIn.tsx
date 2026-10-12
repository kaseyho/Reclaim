import { useState } from 'react'
import { ArrowRight, Leaf } from 'lucide-react'
import { signIn } from './auth'
import type { Config } from './types'

export function SignIn({ config, done }: { config: Config; done: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  return <main className="sign-in-screen"><div className="brand"><Leaf size={25}/>reclaim<span>·</span></div><div className="eyebrow">A GOOD FIND STARTS HERE</div><h1>Room for <em>new beginnings.</em></h1><p>Sign in to open your private Reclaim walkthrough.</p>{config.supabase_publishable_key ? <form onSubmit={async e => { e.preventDefault(); setBusy(true); setError(''); try { await signIn(email, password); done() } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }}><label className="field"><span>Email</span><input autoFocus required type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)}/></label><label className="field"><span>Password</span><input required type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)}/></label><button className="primary full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}<ArrowRight size={16}/></button><p className="fineprint">Use the judge test account supplied by this deployment’s operator. Each signed-in judge has an isolated workspace.</p></form> : <div className="notice amber">The operator still needs to configure the public sign-in client key and a judge account.</div>}{error && <div className="notice error" role="alert">{error}</div>}</main>
}
