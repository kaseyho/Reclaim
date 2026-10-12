import { useEffect, useRef, useState } from 'react'
import { api, dollars } from './api'
import type { Config, Commitment } from './types'

type Buttons = { render: (element: HTMLElement) => Promise<void>; close: () => void }
type PayPal = { Buttons: (options: Record<string, unknown>) => Buttons }
declare global { interface Window { paypal?: PayPal } }
let sdkPromise: Promise<void> | undefined
function loadSDK(clientId: string) {
  if (window.paypal) return Promise.resolve()
  if (!sdkPromise) sdkPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&currency=USD&intent=authorize&components=buttons&disable-funding=credit,card`
    script.onload = () => resolve()
    script.onerror = () => { sdkPromise = undefined; script.remove(); reject(new Error('PayPal checkout could not load. Check your connection and retry.')) }
    document.head.appendChild(script)
  })
  return sdkPromise
}

export function PayPalCheckout({ config, commitment, token, refresh }: { config: Config; commitment: Commitment; token: string; refresh: () => Promise<void> }) {
  const target = useRef<HTMLDivElement>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    if (config.payment_mode !== 'sandbox' || !config.paypal_client_id || !config.paypal_configured) return
    let cancelled = false
    let buttons: Buttons | undefined
    loadSDK(config.paypal_client_id).then(async () => {
      if (cancelled || !target.current || !window.paypal) return
      buttons = window.paypal.Buttons({
        style: { layout: 'vertical', color: 'gold', shape: 'rect', label: 'paypal', height: 46 },
        createOrder: async () => {
          setError('')
          const order = await api<{ id: string }>(`/commitments/${commitment.id}/paypal-order`, token, {})
          return order.id
        },
        onApprove: async (data: { orderID: string }) => {
          try { await api(`/commitments/${commitment.id}/authorize`, token, { order_id: data.orderID }); await refresh() }
          catch (e) { setError((e as Error).message); await refresh() }
        },
        onCancel: () => setError('Checkout cancelled. Your purchase is still incomplete; you can retry or withdraw before capture.'),
        onError: (e: Error) => setError(e.message || 'PayPal could not approve this purchase. Retry or withdraw.'),
      })
      await buttons.render(target.current)
    }).catch(e => setError((e as Error).message))
    return () => { cancelled = true; if (buttons) buttons.close() }
  }, [commitment.id, config.paypal_client_id, config.paypal_configured, config.payment_mode, token, retry])

  async function simulate() {
    setBusy(true); setError('')
    try {
      const order = await api<{ id: string }>(`/commitments/${commitment.id}/paypal-order`, token, {})
      await api(`/commitments/${commitment.id}/authorize`, token, { order_id: order.id })
      await refresh()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <div className="checkout-control">
    <h3>Authorize {dollars(commitment.price_minor)}</h3>
    <p>For {commitment.items.map(i => i.name.toLowerCase()).join(' and ')}. An authorization can place a temporary hold. Capture starts when the whole group is ready.</p>
    {config.payment_mode === 'demo' ? <><button className="primary paypal-demo" disabled={busy} onClick={simulate}>{busy ? 'Authorizing…' : `Simulate authorization · ${dollars(commitment.price_minor)}`}</button><p className="fineprint">Demo payment. No PayPal request or real hold is made.</p></> : !config.paypal_configured ? <div className="notice amber">PayPal sandbox credentials need to be configured on the server before checkout is available.</div> : <div ref={target} className="paypal-target"/>}
    {error && <div role="alert" className="notice error">{error}{config.payment_mode === 'sandbox' && <button className="text-button" onClick={() => { setError(''); setRetry(v => v + 1) }}>Reload checkout</button>}</div>}
  </div>
}
