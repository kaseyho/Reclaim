# Verification record

## Currently verified locally

12 October 2026:

- TypeScript/Vite production build succeeds.
- 33 pytest tests pass locally; 1 PostgreSQL-specific test is skipped locally, including Hypothesis property checks for deterministic cent rounding and solver feasibility/optimal buyer count against exhaustive small cases.
- Furniture scenario: $72 / $48 / $80. Creator scenario: $67.50 / $37.50 / $45. Bulk scenario: three $20 shares for four sealed notebooks each.
- Browser walkthrough: fresh monitor request → editable interpretation → confirmation → complete proposal → Alice, Ben, Chen and seller acceptance → separate simulated authorizations → all simulated captures → seller preparation → Chen receipt and pickup confirmation.
- Mobile (390 px) and tablet (768 px) marketplace checks show no page-level horizontal overflow. Normal desktop preview inspected visually.
- Demo parser/payment labels stay visible throughout. Simulated provider IDs begin DEMO.

These are local prototype results. They do not establish actual provider integration, PostgreSQL behavior across processes, Docker/Render runtime behavior, user research, AI precision, or Devpost submission.

## Remaining verification gates

- [ ] Actual OpenAI image/text extraction and interpretation; refusal/incomplete response and provider-timeout checks.
- [ ] Actual PayPal sandbox approvals, authorizations and captures for three buyers.
- [ ] Actual sandbox void and refund IDs verified in the merchant dashboard.
- [ ] Verified webhook delivery and duplicate handling.
- [ ] PostgreSQL locking/outbox behavior across separate API/worker processes.
- [ ] Deployment restart and an externally reachable judge flow, or complete clean-machine setup proof.
- [ ] Fresh seller form, all three category flows, changed inventory, withdrawal/replacement and error-state browser checks.
- [ ] Final accessibility/layout checks on forms, proposal and receipts at each width.
- [ ] Annotated evaluation set and real buyer/seller sessions, if obtained; otherwise disclose lack of that evidence.
- [ ] Public video watched end to end and confirmed under 180 seconds.
- [ ] Live Devpost submission confirmation and final repository state.
