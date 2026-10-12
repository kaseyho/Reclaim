# Verification record

## Verified build and behavior

12 October 2026:

- TypeScript/Vite production build succeeds.
- 33 pytest tests pass locally; 1 PostgreSQL-specific test is skipped locally, including Hypothesis property checks for deterministic cent rounding and solver feasibility/optimal buyer count against exhaustive small cases.
- Furniture scenario: $72 / $48 / $80. Creator scenario: $67.50 / $37.50 / $45. Bulk scenario: three $20 shares for four sealed notebooks each.
- Browser walkthrough: fresh monitor request → editable interpretation → confirmation → complete proposal → Alice, Ben, Chen and seller acceptance → separate simulated authorizations → all simulated captures → seller preparation → Chen receipt and pickup confirmation.
- Fresh workspace: seller text extraction → four corrected items, explicit condition/width/weights, price and division confirmation → publication → three fresh buyer requests → validated $72 / $48 / $80 proposal. The monitor's 24-inch requirement and seller-confirmed fact remain inspectable.
- Creator and bulk examples were completed through fresh browser requests: $67.50 / $37.50 / $45 for the creator kit; four sealed notebooks per buyer at $20 each for the bulk case.
- Browser recovery: scheduled Ben capture failure → Alice capture refunded, Ben and Chen authorizations voided, cancelled group and unavailable pickup. DEMO references remain visible.
- Mobile (390 px) and tablet (768 px) marketplace checks show no page-level horizontal overflow. Normal desktop preview inspected visually.
- Mobile buyer-review dialog inspected at 390 × 844; fields stack, the dialog scrolls, and the page stays within the viewport.
- Browser receipt checks: an incorrect pickup code is rejected without marking collection; valid codes complete Chen, Alice and Ben's orders independently, and the deal reaches `COMPLETED`. Alice's JSON receipt downloads successfully and records the simulated payment mode.
- Demo parser/payment labels stay visible throughout. Simulated provider IDs begin DEMO.
- [GitHub Actions run 38259306008](https://github.com/kaseyho/Reclaim/actions/runs/38259306008), commit `0be54f2`: **34 tests passed on PostgreSQL 16**, including separate Store locking/outbox checks. The Docker image built, started, and served both `/api/health` and the frontend. PostgreSQL test workspaces and worker queues use a unique schema per test.
- Actual browser screenshots are in [the gallery](submission/gallery/README.md). They show the labelled local walkthrough.

These checks establish local behavior and the tested CI database/container paths. They do not establish actual OpenAI/PayPal integration, Render deployment, user research, AI precision, or Devpost submission.

### Additional release checks — 13 October 2026

- Changing the confirmed desk width from 95 cm to 110 cm while Alice holds an authorization cancels the original proposal, confirms a simulated void, and excludes Alice's 100 cm request. The blocker states the exact width mismatch.
- Restoring the width creates proposal v2 with every participant's acceptance cleared. Chen's withdrawal voids the held authorization and restores the missing-monitor state. A fresh monitor request produces proposal v3; all participants must accept again before checkout succeeds.
- The revised proposal reaches `PAID` after all three simulated captures. Seller preparation and the individual receipt remain usable.
- Seller review, buyer review, proposal and receipt layouts were checked at 390, 768 and 1280 pixels. Page widths match their viewports; forms remain within their dialogs. The mobile receipt and allocation inspector are saved in the gallery.
- An order problem records an `OPEN` issue without issuing or promising a refund.
- Selected-item details now expose each recipient's full purchase and exact total. Item-marker targets measure 44 × 44 pixels; right-edge labels remain within the image.
- Fresh examples retain Alice as the selected persona after reload. Creation dialogs focus the editing field; Escape dismisses them. A full keyboard and screen-reader audit is not claimed.

## Remaining verification gates

- [ ] Actual OpenAI image/text extraction and interpretation; refusal/incomplete response and provider-timeout checks.
- [ ] Actual PayPal sandbox approvals, authorizations and captures for three buyers.
- [ ] Actual sandbox void and refund IDs verified in the merchant dashboard.
- [ ] Verified webhook delivery and duplicate handling.
- [x] PostgreSQL transactional locking and outbox tests in CI.
- [x] Docker build, application startup, health and frontend serving in CI.
- [ ] Deployed PostgreSQL API/worker restart and recovery while actual provider operations are pending.
- [ ] Deployment restart and an externally reachable judge flow, or complete clean-machine setup proof.
- [x] Fresh seller form, all three category flows and partial-failure recovery in the browser.
- [x] Withdrawal/replacement and changed-inventory browser walkthroughs, including authorization cleanup and new acceptance versions.
- [x] Responsive layout checks on forms, proposal and receipts at 390, 768 and 1280 pixels.
- [ ] Actual provider recordings; the verified local walkthroughs use simulated outcomes.
- [ ] Annotated evaluation set and real buyer/seller sessions, if obtained; otherwise disclose lack of that evidence.
- [ ] Public video watched end to end and confirmed under 180 seconds.
- [ ] Live Devpost submission confirmation and final repository state.

## Completion audit against the supplied plan

| Requirement | Current authoritative evidence | Release status |
|---|---|---|
| Fresh seller listing, inventory correction and confirmation | Browser walkthrough and `Forms.tsx`; image/text adapter in `ai.py` | Local flow verified; actual image/model call awaits credentials |
| Fresh needs, quantities, attributes, budgets and pickup constraints | Browser walkthrough; strict schemas, solver and invariant tests | Local flow verified; actual interpretation awaits credentials |
| Complete allocation, missing demand and transparent prices | Three category walkthroughs; exhaustive/property checks | Verified at the tested prototype scale |
| Immutable versions, reservations, all-party acceptance and recovery | Domain tests plus inventory/withdrawal browser checks above | Verified locally and in the tested PostgreSQL CI paths |
| Sandbox authorization, capture, void, refund and signed webhook delivery | Adapter and mocked contracts; simulated journal/outbox results | Actual provider evidence missing; completion is unproven |
| Individual receipt, preparation, collection and problem reporting | All three pickups, JSON receipt and open-issue browser checks | Local flow verified |
| Proposed private object storage and signed-in deployment | Workspace-private image data; optional Supabase JWT adapter; Docker/Render configuration | Dedicated object storage and deployed account paths are not integrated/verified |
| Model evaluation, about 30 listings/60 requests and human sessions | No evaluated model comparison or real-session evidence supplied | Proposed targets remain unmet; no precision, savings or interview claims made |
| Public licensed source and reproducible run instructions | Public repository, MIT licence, CI Docker startup and README | Available; connected run still requires provider configuration |
| Demo script, user's recording, final edit and public YouTube video | 352-word script, storyboard, original cards and app gallery | Preparation complete; recording, final video and public URL missing |
| Devpost draft and final submission confirmation | Fresh My projects page still requires hackathon registration | No draft or submission exists; user declarations/terms are required |

The full goal is not achieved. Completing the connected release requires provider/account input, the user's recording, actual provider proof, and final publication/submission. Prepared documentation and simulated results are not substitutes for those gates.
