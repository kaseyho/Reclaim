import { useState, type FormEvent, type ReactNode } from 'react'
import { ArrowRight, Check, Plus, Trash2, Upload } from 'lucide-react'
import { api, isoDate, localDate } from './api'
import type { Actor, Attribute, Category, Condition, Config, Demand, Lot, Need, Unit } from './types'

const conditions: Condition[] = ['good', 'like_new', 'new', 'fair', 'unknown']
const label = (value: string) => value.replace(/_/g, ' ')
const number = (value: string, fallback = 1) => Number(value) || fallback
function Field({ title, children, hint }: { title: string; children: ReactNode; hint?: string }) { return <label className="field"><span>{title}</span>{children}{hint && <small>{hint}</small>}</label> }
function conditionOptions(buyer = false) { return conditions.map(c => <option key={c} value={c}>{c === 'unknown' ? buyer ? 'No condition requirement' : 'Unknown — needs confirmation' : label(c)}</option>) }
function Attributes({ values, buyer = false, change }: { values: Attribute[]; buyer?: boolean; change: (values: Attribute[]) => void }) {
  function edit(index: number, key: keyof Attribute, value: string) { change(values.map((a, i) => i === index ? { ...a, [key]: value } : a)) }
  return <details className="attribute-editor" open={values.length > 0}><summary>{buyer ? 'Additional requirements' : 'Additional verified facts'}<span>{values.length || 'Optional'}</span></summary><p className="fineprint">{buyer ? 'Keep connector, model, compatibility, material or size requirements explicit. Unknown seller facts cannot satisfy them.' : 'Confirm facts such as connector, model number, compatibility, material, screen size or expiry. Use plain numbers with units in the key, or YYYY-MM-DD dates.'}</p>{values.map((a, i) => <div className="attribute-row" key={i}><Field title="Attribute"><input required pattern="[a-z][a-z0-9_]*" value={a.key} placeholder="connector" onChange={e => edit(i, 'key', e.target.value.toLowerCase().replace(/ /g, '_'))}/></Field>{buyer && <Field title="Rule"><select value={a.operator ?? 'equals'} onChange={e => edit(i, 'operator', e.target.value)}><option value="equals">Exactly matches</option><option value="at_least">At least (number / date)</option><option value="at_most">At most (number / date)</option><option value="includes">In confirmed list</option></select></Field>}<Field title={buyer ? 'Required value' : 'Confirmed value'}><input required value={a.value} placeholder="usb" onChange={e => edit(i, 'value', e.target.value)}/></Field><button type="button" className="icon-button danger-text" aria-label={`Remove attribute ${i + 1}`} onClick={() => change(values.filter((_, index) => index !== i))}><Trash2 size={14}/></button></div>)}<button type="button" className="text-button" onClick={() => change([...values, { key: '', value: '', ...(buyer ? { operator: 'equals' as const } : { evidence: 'Seller confirmation required' }) }])}><Plus size={13}/>Add {buyer ? 'a requirement' : 'a verified fact'}</button></details>
}
function dates(lot?: Lot) {
  const start = new Date(Date.now() + 2 * 86400000); start.setHours(10, 0, 0, 0)
  const end = new Date(start); end.setHours(18)
  return { start: localDate(lot?.pickup_start ?? start.toISOString()), end: localDate(lot?.pickup_end ?? end.toISOString()) }
}
function SuggestionNote({ unresolved, config }: { unresolved: string[]; config: Config }) {
  return <div className="notice suggestion"><strong>{config.ai_provider === 'openai' ? 'AI suggestion — your review matters' : 'Demo parser suggestion — review every field'}</strong><ul>{unresolved.map((item, i) => <li key={i}>{item}</li>)}</ul></div>
}

type Common = { token: string; actor: Actor; lot?: Lot; config: Config; done: (id?: string) => Promise<void> }
export function RequestForm({ token, actor, lot, config, done, initialText = '', existing }: Common & { initialText?: string; existing?: Demand }) {
  const timing = dates(lot)
  const [text, setText] = useState(existing?.text ?? initialText)
  const [needs, setNeeds] = useState<Need[]>(existing?.needs ?? [])
  const [budget, setBudget] = useState(existing ? String(existing.budget_minor / 100) : '')
  const [location, setLocation] = useState(existing?.location ?? lot?.location ?? 'Campus pickup')
  const [start, setStart] = useState(existing ? localDate(existing.pickup_start) : timing.start)
  const [end, setEnd] = useState(existing ? localDate(existing.pickup_end) : timing.end)
  const [deadline, setDeadline] = useState(existing ? localDate(existing.deadline) : timing.end)
  const [review, setReview] = useState(Boolean(existing))
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [unresolved, setUnresolved] = useState<string[]>([])
  function edit(index: number, field: keyof Need, value: unknown) { setNeeds(previous => previous.map((need, i) => i === index ? { ...need, [field]: value } : need)); setConfirmed(false) }
  async function interpret(e: FormEvent) {
    e.preventDefault(); setError(''); setBusy(true)
    try {
      const answer = await api<{ result: { needs: Need[]; budget_minor: number | null; location: string | null; unresolved: string[] } }>('/demands/interpret', token, { text, category: lot?.category ?? 'furniture' })
      setNeeds(answer.result.needs)
      if (answer.result.budget_minor !== null) setBudget(String(answer.result.budget_minor / 100))
      if (answer.result.location) setLocation(answer.result.location)
      setUnresolved(answer.result.unresolved); setReview(true); setConfirmed(false)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function submit(e: FormEvent) {
    e.preventDefault(); setError(''); setBusy(true)
    try {
      const result = await api<Demand>(existing ? `/demands/${existing.id}` : '/demands', token, { text, needs, budget_minor: Math.round(Number(budget) * 100), location, pickup_start: isoDate(start), pickup_end: isoDate(end), deadline: isoDate(deadline), allow_substitutions: false, confirmed }, existing ? 'PUT' : 'POST')
      await done(result.id)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <div className="creation-flow">
    <div className="eyebrow">{actor.name}'s request · {review ? '02 / Review' : '01 / Describe'}</div>
    <h2 id="form-title">What piece are you missing?</h2>
    <p className="form-intro">Tell us what you need. Confirm the details before we look for people who need the rest.</p>
    {!review ? <form onSubmit={interpret}>
      <Field title="Describe your request"><textarea autoFocus required minLength={3} maxLength={2000} rows={4} value={text} onChange={e => setText(e.target.value)} placeholder="A desk under one metre wide and a lamp, under $90. I can collect this weekend."/></Field>
      <div className="form-footer"><button type="button" className="text-button" onClick={() => { setReview(true); setNeeds([{ item_type: 'desk', quantity: 1, max_width_cm: null, minimum_condition: 'good', brand: null, sealed: null }]) }}>Enter details myself</button><button className="primary" disabled={busy || text.length < 3}>{busy ? 'Reading your request…' : 'Review my request'}<ArrowRight size={17}/></button></div>
    </form> : <form onSubmit={submit}>
      {unresolved.length > 0 && <SuggestionNote unresolved={unresolved} config={config}/>}
      <Field title="Your original request"><textarea required minLength={3} rows={2} value={text} onChange={e => { setText(e.target.value); setConfirmed(false) }}/></Field>
      <div className="section-label">The items you need <span>Every requirement must be satisfied.</span></div>
      <div className="review-rows">{needs.map((need, i) => <div className="need-editor" key={i}>
        <div className="form-grid three"><Field title="Item type"><input required pattern="[a-z][a-z0-9_]*" value={need.item_type} onChange={e => edit(i, 'item_type', e.target.value.toLowerCase().replace(/ /g, '_'))}/></Field><Field title="Quantity"><input type="number" min="1" max="100" step="1" value={need.quantity} onChange={e => edit(i, 'quantity', number(e.target.value))}/></Field><Field title="Minimum condition"><select value={need.minimum_condition} onChange={e => edit(i, 'minimum_condition', e.target.value)}>{conditionOptions(true)}</select></Field></div>
        <div className="form-grid three"><Field title="Maximum width (cm)"><input type="number" min="1" max="1000" value={need.max_width_cm ?? ''} placeholder="No width limit" onChange={e => edit(i, 'max_width_cm', e.target.value ? number(e.target.value) : null)}/></Field><Field title="Required brand"><input value={need.brand ?? ''} placeholder="Any brand" onChange={e => edit(i, 'brand', e.target.value || null)}/></Field><Field title="Packaging"><select value={need.sealed === null ? 'any' : String(need.sealed)} onChange={e => edit(i, 'sealed', e.target.value === 'any' ? null : e.target.value === 'true')}><option value="any">No seal requirement</option><option value="true">Individually sealed</option><option value="false">Unsealed is required</option></select></Field></div>
        <Attributes buyer values={need.attributes ?? []} change={value => edit(i, 'attributes', value)}/>
        <button type="button" className="text-button danger-text" onClick={() => { setNeeds(v => v.filter((_, index) => index !== i)); setConfirmed(false) }}><Trash2 size={13}/> Remove item</button>
      </div>)}</div>
      <button type="button" className="text-button" onClick={() => { setNeeds(v => [...v, { item_type: '', quantity: 1, max_width_cm: null, minimum_condition: 'good', brand: null, sealed: null }]); setConfirmed(false) }}><Plus size={15}/> Add an item</button>
      <div className="form-grid"><Field title="Maximum total budget (USD)" hint="Your budget is a limit, not the price we charge."><input required type="number" min="0.01" step="0.01" value={budget} onChange={e => { setBudget(e.target.value); setConfirmed(false) }}/></Field><Field title="Pickup location" hint="Use the same pickup point as a compatible seller."><input required value={location} onChange={e => { setLocation(e.target.value); setConfirmed(false) }}/></Field></div>
      <div className="form-grid"><Field title="Available from"><input required type="datetime-local" value={start} onChange={e => { setStart(e.target.value); setConfirmed(false) }}/></Field><Field title="Available until"><input required type="datetime-local" value={end} onChange={e => { setEnd(e.target.value); setConfirmed(false) }}/></Field></div>
      <Field title="Need the goods by"><input required type="datetime-local" value={deadline} onChange={e => { setDeadline(e.target.value); setConfirmed(false) }}/></Field>
      <label className="check-field"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)}/><span>I confirm these items, quantities, budget, and pickup requirements. Match these exact items.</span></label>
      <div className="form-footer"><button type="button" className="text-button" onClick={() => setReview(false)}>Back to description</button><button className="primary" disabled={busy || !confirmed || needs.length === 0}>{busy ? 'Saving request…' : existing ? 'Confirm updated request' : 'Confirm & find my group'}<Check size={17}/></button></div>
    </form>}
    {error && <div className="notice error" role="alert">{error}</div>}
  </div>
}

export function ListingForm({ token, actor, lot, config, done, existing }: Common & { existing?: Lot }) {
  const timing = dates(lot)
  const [title, setTitle] = useState(existing?.title ?? '')
  const [text, setText] = useState(existing?.description ?? '')
  const [category, setCategory] = useState<Category>(existing?.category ?? 'furniture')
  const [image, setImage] = useState<string | null>(existing?.image ?? null)
  const [units, setUnits] = useState<Unit[]>(existing?.units ?? [])
  const [price, setPrice] = useState(existing ? String(existing.goods_price_minor / 100) : '')
  const [prep, setPrep] = useState(existing ? String(existing.preparation_minor / 100) : '0')
  const [location, setLocation] = useState(existing?.location ?? lot?.location ?? 'Campus pickup')
  const [start, setStart] = useState(existing ? localDate(existing.pickup_start) : timing.start)
  const [end, setEnd] = useState(existing ? localDate(existing.pickup_end) : timing.end)
  const [review, setReview] = useState(Boolean(existing))
  const [confirmed, setConfirmed] = useState(false)
  const [divisible, setDivisible] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [unresolved, setUnresolved] = useState<string[]>([])
  function edit(index: number, field: keyof Unit, value: unknown) { setUnits(previous => previous.map((unit, i) => i === index ? { ...unit, [field]: value } : unit)); setConfirmed(false) }
  function emptyUnit(): Unit { return { id: `item_${crypto.randomUUID().slice(0, 8)}`, name: '', item_type: '', quantity: 1, reference_weight: 1, condition: 'unknown', width_cm: null, brand: null, sealed: null, confirmed_fields: [], evidence: 'Seller confirmation required' } }
  async function photo(file?: File) {
    if (!file) return
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 2500000) { setError('Choose a PNG, JPEG or WebP smaller than 2.5 MB.'); return }
    const reader = new FileReader()
    reader.onload = () => { setImage(String(reader.result)); setError('') }
    reader.onerror = () => setError('The photograph could not be read. Try another file.')
    reader.readAsDataURL(file)
  }
  async function extract(e: FormEvent) {
    e.preventDefault(); setError(''); setBusy(true)
    try {
      const answer = await api<{ result: { units: Omit<Unit, 'id' | 'reference_weight' | 'confirmed_fields'>[]; unresolved: string[] } }>('/lots/extract', token, { text, category, image })
      setUnits(answer.result.units.map(u => ({ ...u, id: `item_${crypto.randomUUID().slice(0, 8)}`, reference_weight: 1, confirmed_fields: [] })))
      setUnresolved(answer.result.unresolved); setReview(true); setConfirmed(false)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function submit(e: FormEvent) {
    e.preventDefault(); setError(''); setBusy(true)
    try {
      const confirmedUnits = units.map(u => ({ ...u, confirmed_fields: ['item_type', 'quantity', 'reference_weight', ...(u.condition !== 'unknown' ? ['condition'] : []), ...(u.width_cm !== null ? ['width_cm'] : []), ...(u.brand ? ['brand'] : []), ...(u.sealed !== null ? ['sealed'] : []), ...(u.attributes ?? []).filter(a => !['unknown', '?', 'unverified'].includes(a.value.toLowerCase().trim())).map(a => `attribute:${a.key}`)], evidence: `Confirmed by ${actor.name}. Unknown attributes remain unresolved.` }))
      const result = await api<Lot>(existing ? `/lots/${existing.id}` : '/lots', token, { title, category, description: text, goods_price_minor: Math.round(Number(price) * 100), preparation_minor: Math.round(Number(prep) * 100), currency: 'USD', location, pickup_start: isoDate(start), pickup_end: isoDate(end), units: confirmedUnits, image, confirmed, divisible }, existing ? 'PUT' : 'POST')
      await done(result.id)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <div className="creation-flow">
    <div className="eyebrow">{actor.name}'s listing · {review ? '02 / Confirm inventory' : '01 / Describe'}</div>
    <h2 id="form-title">A bundle with more possibilities.</h2>
    <p className="form-intro">List the whole lot. Confirm what can be separated, and we'll look for a buyer for every piece.</p>
    {!review ? <form onSubmit={extract}>
      <Field title="Listing title"><input autoFocus required minLength={3} maxLength={120} value={title} onChange={e => setTitle(e.target.value)} placeholder="Moving-out room essentials"/></Field>
      <Field title="Category"><select value={category} onChange={e => setCategory(e.target.value as Category)}><option value="furniture">Furniture & room essentials</option><option value="creator">Creator equipment</option><option value="bulk">Sealed bulk goods</option></select></Field>
      <Field title="Describe what's in the lot"><textarea required minLength={3} maxLength={4000} rows={4} value={text} onChange={e => setText(e.target.value)} placeholder="One oak desk, 95 cm wide, a lamp, chair and monitor. All in good condition. I can divide them for campus pickup."/></Field>
      <label className="upload-zone"><Upload size={22}/><span>{image ? 'Photograph added · choose another' : 'Add a photograph'}<small>PNG, JPEG or WebP · up to 2.5 MB</small></span><input type="file" accept="image/png,image/jpeg,image/webp" onChange={e => photo(e.target.files?.[0])}/></label>
      {image && <img className="upload-preview" src={image} alt="Your listing photograph"/>}
      <div className="form-footer"><button type="button" className="text-button" onClick={() => { setReview(true); setUnits([emptyUnit()]) }}>Enter inventory myself</button><button className="primary" disabled={busy || text.length < 3 || title.length < 3}>{busy ? 'Reading inventory…' : 'Extract & review inventory'}<ArrowRight size={17}/></button></div>
    </form> : <form onSubmit={submit}>
      {existing?.status === 'RESERVED' && <div className="notice amber">Changing reserved inventory cancels the old proposal and starts payment recovery. Everyone will need to accept a new allocation.</div>}
      {unresolved.length > 0 && <SuggestionNote unresolved={unresolved} config={config}/>}
      <Field title="Listing title"><input required minLength={3} value={title} onChange={e => { setTitle(e.target.value); setConfirmed(false) }}/></Field>
      <div className="section-label">Confirm each item <span>Unknown details cannot satisfy hard constraints.</span></div>
      <div className="review-rows">{units.map((unit, i) => <div className="need-editor" key={unit.id}>
        <div className="form-grid"><Field title="Item name"><input required value={unit.name} onChange={e => edit(i, 'name', e.target.value)}/></Field><Field title="Item type"><input required pattern="[a-z][a-z0-9_]*" value={unit.item_type} onChange={e => edit(i, 'item_type', e.target.value.toLowerCase().replace(/ /g, '_'))}/></Field></div>
        <div className="form-grid three"><Field title="Quantity"><input type="number" min="1" max="100" step="1" value={unit.quantity} onChange={e => edit(i, 'quantity', number(e.target.value))}/></Field><Field title="Condition"><select value={unit.condition} onChange={e => edit(i, 'condition', e.target.value)}>{conditionOptions()}</select></Field><Field title="Reference weight / item" hint="Agreed weights determine the price split."><input type="number" min="1" max="100000" step="1" value={unit.reference_weight} onChange={e => edit(i, 'reference_weight', number(e.target.value))}/></Field></div>
        <div className="form-grid three"><Field title="Verified width (cm)"><input type="number" min="1" max="1000" value={unit.width_cm ?? ''} placeholder="Unknown" onChange={e => edit(i, 'width_cm', e.target.value ? number(e.target.value) : null)}/></Field><Field title="Verified brand"><input value={unit.brand ?? ''} placeholder="Unknown" onChange={e => edit(i, 'brand', e.target.value || null)}/></Field><Field title="Packaging"><select value={unit.sealed === null ? 'unknown' : String(unit.sealed)} onChange={e => edit(i, 'sealed', e.target.value === 'unknown' ? null : e.target.value === 'true')}><option value="unknown">Unknown / not applicable</option><option value="true">Individually sealed</option><option value="false">Unsealed</option></select></Field></div>
        <Attributes values={unit.attributes ?? []} change={value => edit(i, 'attributes', value)}/>
        <button type="button" className="text-button danger-text" onClick={() => { setUnits(v => v.filter((_, index) => index !== i)); setConfirmed(false) }}><Trash2 size={13}/> Remove item</button>
      </div>)}</div>
      <button type="button" className="text-button" onClick={() => { setUnits(v => [...v, emptyUnit()]); setConfirmed(false) }}><Plus size={15}/> Add an item</button>
      <div className="form-grid"><Field title="Price for the goods (USD)"><input required type="number" min="0.01" step="0.01" value={price} onChange={e => { setPrice(e.target.value); setConfirmed(false) }}/></Field><Field title="Preparation cost (USD)" hint="Disclosed and included in the total before matching."><input required type="number" min="0" step="0.01" value={prep} onChange={e => { setPrep(e.target.value); setConfirmed(false) }}/></Field></div>
      <div className="price-preview">Buyers pay a total of <strong>${((Number(price) || 0) + (Number(prep) || 0)).toFixed(2)}</strong><small>Merchant processing fees come out of the merchant's gross receipts.</small></div>
      <Field title="Pickup location"><input required value={location} onChange={e => { setLocation(e.target.value); setConfirmed(false) }}/></Field>
      <div className="form-grid"><Field title="Pickup starts"><input required type="datetime-local" value={start} onChange={e => { setStart(e.target.value); setConfirmed(false) }}/></Field><Field title="Pickup ends"><input required type="datetime-local" value={end} onChange={e => { setEnd(e.target.value); setConfirmed(false) }}/></Field></div>
      <label className="check-field"><input type="checkbox" checked={divisible} onChange={e => setDivisible(e.target.checked)}/><span>I can separate these items or quantities and fulfill each buyer's order independently.</span></label>
      <label className="check-field"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)}/><span>I confirm the inventory, attributes, reference weights, price, and pickup terms above.</span></label>
      <div className="form-footer"><button type="button" className="text-button" onClick={() => setReview(false)}>Back to description</button><button className="primary" disabled={busy || !confirmed || !divisible || units.length === 0}>{busy ? 'Publishing listing…' : existing ? 'Confirm updated inventory' : 'Publish confirmed bundle'}<Check size={17}/></button></div>
    </form>}
    {error && <div className="notice error" role="alert">{error}</div>}
  </div>
}
