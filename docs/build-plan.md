# Reclaim — PayPal AI Hackathon

Build baseline: the user's supplied marketplace plan, 12 October 2026.
Deadline: 13 November 2026, 04:00 Asia/Singapore.
Rules: https://paypalaihackathon.devpost.com/rules

## UX decision brief

- Job: make a larger divisible lot purchasable by people who need different goods.
- Users: occasional buyers and sellers; isolated judge personas for a complete walkthrough.
- Pattern: annotated allocation with an inspector, reviewed forms, transparent checkout, individual pickup orders.
- Primary action: fill the missing demand, then accept the exact allocated purchase.
- Core path: confirmed lot → confirmed needs → feasible group → same-version acceptance → individual authorizations → coordinated capture → receipts and pickup.
- Recovery: missing buyer, incompatible constraints, stale terms, withdrawal, expiration, capture uncertainty, partial capture, pending refund, pickup problem.
- Risk: authorizations can place holds; separate payments are not atomic. Prices and recovery outcomes must be explicit.

## UI decision brief

- Surface: marketplace product workspace, reviewed creation flows, checkout.
- Direction: warm editorial; cream paper, forest green, ink and thin rules.
- World: a campus moving sale. Metaphor: goods laid out with their new owners' labels.
- Typography: Newsreader headings, DM Sans interface, monospace for reference IDs.
- Main anchor: an interactive bundle diagram showing who receives each item.
- Layout: left navigation, large goods canvas, right allocation inspector; stack on mobile.
- Density: balanced browsing, compact payment and fulfillment rows.
- State visuals: partial allocation amber, confirmed allocation green, failure rust; literal provider status labels.
- Motion: short CSS selection, disclosure and progress transitions; respect reduced motion.
- Assets: original SVG listing illustrations, local open source fonts, curated Lucide icons, actual app screenshots for submission. No fabricated listing photos or user research.
- Track: React/Vite/TypeScript, FastAPI/Python, OR-Tools. Stateful forms and coordinated payments justify React.
- Hosting: Render-compatible Docker service serves the built frontend and API, with PostgreSQL and an optional separate worker. Local SQLite supports a single process.
- Constraints: one sandbox merchant, USD, local pickup, three categories; no real-money checkout.

## Completion checklist

- [x] Seller text/photo upload and extraction adapter, editable review, confirmed separability and inventory; fresh local seller flow verified.
- [x] Buyer interpretation adapter, editable constraints and confirmation; fresh local buyer flow verified.
- [x] Whole-lot constraint allocation, budget-safe rounding, evidence and blockers.
- [x] Immutable proposals, participant acceptance, reservations and stale-version rejection.
- [x] PayPal sandbox adapter for orders, authorization, capture, void, refund, idempotency and reconciliation; simulated lifecycle and mocked provider contracts tested.
- [x] Durable outbox and retry worker; duplicate webhooks and restart handling tested.
- [x] Receipts, pickup codes and problem reporting; all three local pickups and receipt download verified in the browser.
- [x] Fresh inputs and seeded furniture, creator and bulk examples.
- [x] Solver, payment and concurrency tests; local browser walkthroughs; PostgreSQL and Docker checks passed in GitHub Actions.
- [x] Public source repository and complete local run/configuration instructions.
- [x] Submission copy, actual app gallery and under-three-minute recording script/shot list.
- [x] Inventory-change and withdrawal/replacement browser checks; responsive creation, proposal and receipt checks; visible recipient prices and persistent judge persona.
- [x] Synthetic text evaluation preparation: 30 listing/60 request probes, offline baseline, twelve grader checks and an opt-in connected comparison runner. This does not complete real model/photo or user-research validation.
- [ ] Actual OpenAI extraction/interpretation, PayPal sandbox checkout, void/refund evidence and verified webhook delivery.
- [ ] Hosted judge access and deployed restart check, if hosting is chosen.
- [ ] Actual provider footage for the final demonstration.
- [ ] User's talking-head recording, final video edit, public YouTube link.
- [ ] Devpost submission and visible confirmation.

No provider credentials were configured at task start. Demo fixtures and simulated payment results must be visibly distinguished from actual OpenAI / PayPal sandbox results. User research and held-out AI precision targets remain evidence to collect, not claims.

The checked entries distinguish implementation and local/CI proof from the connected-release gates. They do not imply that provider validation or final submission is complete.
