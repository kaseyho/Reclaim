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
- [ ] Withdrawal/replacement and changed-inventory browser recordings; their domain behavior is covered by pytest.
- [ ] Final accessibility/layout checks on forms, proposal and receipts at each width.
- [ ] Annotated evaluation set and real buyer/seller sessions, if obtained; otherwise disclose lack of that evidence.
- [ ] Public video watched end to end and confirmed under 180 seconds.
- [ ] Live Devpost submission confirmation and final repository state.
