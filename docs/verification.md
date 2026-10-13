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
- Devpost registration was confirmed after the user's handoff. Existing draft `1234351` was filled and saved with the title, pitch, thumbnail, story, twelve technology tags, repository link, six captioned screenshots and technical additional information. User-supplied submitter and feedback choices were saved separately. The live preview says `INCOMPLETE SUBMISSION`; the final agreement remains unchecked and the project has not been submitted.
- [Text evaluation preparation](../evaluation/README.md): 30 Codex-authored synthetic listings and 60 requests, with labels excluded from inference prompts. Twelve grader checks pass. The historical offline parser returned all 90 responses, with 74.03% proposal-field precision, 60.54% recall and 2/90 exact cases. These are parser results, not usable-fact precision, photo validation or real-user evidence.

### Connected AI checks — 13 October 2026

- SOCLAAS `/models` authenticated; the user's `default` alias resolved to `qwen3.6:35b`. The server uses the exact supplied HTTPS API root, an ignored local key, Chat Completions JSON mode and Pydantic validation. No direct OpenAI-model call is claimed.
- A fresh seller listing used the original fictional furniture illustration and explicit condition/measurement text. Actual model output identified desk, monitor, lamp and chair, omitted the excluded decorative plant, retained the 92 cm text measurement and 24-inch monitor fact, and left other dimensions/brands unresolved. Seller review set the reference weights, $180 goods price and $20 preparation cost.
- Fresh Alice, Ben and Chen requests were interpreted, reviewed and saved. A monitor-diagonal clarification removed an invented width limit; a pickup-place schema clarification improved place extraction. Chen's pickup point was manually corrected during review. The resulting complete allocation is $72 / $48 / $80, independently validated by the solver.
- These earlier browser traces contain actual SOCLAAS response IDs, returned model, prompt versions, latency and token usage, alongside demo payments. The personas are fictional testing accounts, not buyer/seller research participants.
- [Final development report](../evaluation/soclaas.md): all 90 responses returned; 96.48% proposal-field precision, 94.88% recall and 70/90 exact cases. p50/p95 model-call latency is 1536/2986 ms, with 86557 input and 15729 output tokens. Cost remains unmeasured. Six of 16 ambiguity-warning checks were missed. The probes informed schema clarification, so fresh independent held-out data is still required.
- Local production build, 46 application checks with one PostgreSQL-only skip, 13 included AI contract checks and 12 grader checks pass. Mocked checks cover protocol/routing, image payloads, invalid output, refusal, truncation, empty choices, timeout and secret-free public configuration. Actual provider refusal/timeout fault injection is not claimed.
- [Main-branch CI run 38360162404](https://github.com/kaseyho/Reclaim/actions/runs/38360162404), commit `712b25d`, passes the PostgreSQL suite with 47 application tests, evaluation grader/offline benchmark, Docker build and container startup. The SOCLAAS provider change is merged in PR #5.
- The user manually created one Business merchant and three distinct Personal buyers, then created the Reclaim sandbox Merchant app. With the user's explicit authorization, its credentials were saved to the ignored local `.env` with permission `0600`; OAuth returned HTTP 200 and `/api/health` reports configured sandbox payments.
- A fresh seller/image review and three fresh buyer reviews produced another validated $72 / $48 / $80 group in sandbox mode. Ben's proposed minimum condition needed manual correction before confirmation. The in-app browser created an actual $72 order but did not expose a usable approval window; that unfinished group was cancelled without any authorization, capture, void or refund.
- Chrome then opened actual PayPal checkout for a separate moving-day example with a freshly interpreted and confirmed Chen request. Alice approved her $72 sandbox order. An authenticated provider GET confirmed its authorization status was `CREATED` and its amount was USD 72.00. At that check, Reclaim remained `AUTHORIZING`, with no capture while the other approvals were missing.
- The checkout expired at 10:03:03 UTC before the remaining buyers approved. The local worker completed automatic cleanup: the group became `EXPIRED`, Alice's payment became `VOIDED`, the other commitments were cancelled and fulfillment stayed unavailable. An authenticated PayPal GET independently confirmed authorization `86M31464EL267910C` was `VOIDED`. This establishes actual authorization and expiry-void behavior for USD 72.00, with no capture or refund in this case; merchant-dashboard review, three-buyer capture and refund evidence remain pending.
- The prepared Render Blueprint validates against Render's published JSON schema. It specifies one paid Singapore web service and an internally connected PostgreSQL 16 database, with external database connections blocked. No Render resources have been created and no provider credentials have been sent to Render.
- The Devpost preview contains the updated provider story and eight captioned images. After the user confirmed eligibility, all three required declarations were checked, saved and read back as checked. Demo/video URLs and the final Rules/Terms agreement remain pending. A new complete source ZIP is prepared locally, but replacement of the older uploaded ZIP is not verified: the latest Additional info and Project details views expose no ZIP upload control or attachment filename. Updated source remains available in the public repository.

### Connected payment and receipt checks — 13 October 2026

- Proposal v2 reset every participant's acceptance. Alice, Ben, Chen and Maya accepted the same version before checkout opened. Three distinct PayPal sandbox payer accounts then approved USD 72.00, 48.00 and 80.00 authorizations. Authenticated provider GETs confirm three `COMPLETED` captures, totaling USD 200.00, and the group reached `PAID`.
- Maya prepared the separate orders. Chen's receipt showed the correct USD 80.00 capture, sandbox mode and a pickup code. Its downloaded JSON was checked against the actual capture ID, amount and `READY_FOR_PICKUP` status. Receipt exports now explicitly retain `payment_mode`.
- The page previously hid cancellation as soon as orders were prepared, although the API permits cancellation until any buyer collects. The page now follows that rule. Cancelling the prepared group before pickup triggered three full refunds; authenticated PayPal GETs confirm every refund is `COMPLETED` and every corresponding capture is `REFUNDED`. The group is `CANCELLED`, all fulfillments are cancelled and the lot is `AVAILABLE`.
- [Redacted provider evidence](submission/paypal-sandbox-evidence.json) records these actual outcomes and the earlier expiry void. Four unchanged sandbox screenshots are in the gallery. This full-refund case does not establish a partial-capture provider failure or signed webhook delivery.
- The production build and two focused pickup/cancellation checks pass after the UI changes. The earlier PostgreSQL CI record remains above; the final change still needs its own CI result.
- Existing Render sign-in succeeded. Reclaim's Blueprint review is open in the user's workspace, but Render requires a real payment method before proceeding. No services have been created and no API secrets have been copied to Render.

## Remaining verification gates

- [x] Actual SOCLAAS text extraction, buyer interpretation and image input through the configured endpoint; mocked refusal/incomplete/schema/timeout checks. Representative real-photo accuracy remains unmeasured. The optional OpenAI adapter has mocked protocol coverage, not actual OpenAI-call evidence.
- [x] Actual PayPal sandbox approvals, authorizations and captures for three distinct buyers.
- [x] Actual USD 72 sandbox authorization and automatic void on checkout expiry, confirmed through authenticated provider GETs.
- [ ] Actual sandbox void and refund IDs verified in the merchant dashboard.
- [x] Actual expiry void and three full refunds independently confirmed through authenticated PayPal API reads.
- [ ] Verified webhook delivery and duplicate handling.
- [x] PostgreSQL transactional locking and outbox tests in CI.
- [x] Docker build, application startup, health and frontend serving in CI.
- [ ] Deployed PostgreSQL API/worker restart and recovery while actual provider operations are pending.
- [ ] Deployment restart and an externally reachable judge flow, or complete clean-machine setup proof.
- [x] Fresh seller form, all three category flows and partial-failure recovery in the browser.
- [x] Withdrawal/replacement and changed-inventory browser walkthroughs, including authorization cleanup and new acceptance versions.
- [x] Responsive layout checks on forms, proposal and receipts at 390, 768 and 1280 pixels.
- [ ] Actual provider screen recordings; connected AI/payment screenshots and provider records are available, but moving footage remains pending.
- [ ] Annotated evaluation set and real buyer/seller sessions, if obtained; otherwise disclose lack of that evidence.
- [ ] Public video watched end to end and confirmed under 180 seconds.
- [ ] Live Devpost submission confirmation and final repository state.

## Completion audit against the supplied plan

| Requirement | Current authoritative evidence | Release status |
|---|---|---|
| Fresh seller listing, inventory correction and confirmation | Browser walkthrough and `Forms.tsx`; actual SOCLAAS image/text extraction in `ai.py` | Connected flow verified with an original fictional illustration; real-photo accuracy unmeasured |
| Fresh needs, quantities, attributes, budgets and pickup constraints | Browser walkthrough; actual SOCLAAS interpretation; strict schemas, solver and invariant tests | Connected interpretation verified; suggestions still require correction and confirmation |
| Complete allocation, missing demand and transparent prices | Three category walkthroughs; exhaustive/property checks | Verified at the tested prototype scale |
| Immutable versions, reservations, all-party acceptance and recovery | Domain tests plus inventory/withdrawal browser checks above | Verified locally and in the tested PostgreSQL CI paths |
| Sandbox authorization, capture, void, refund and signed webhook delivery | Actual three-payer capture, USD 72 expiry void and USD 200 full refund verified by provider GETs; redacted evidence above | Authorization/capture/void/refund verified; merchant-dashboard review and signed webhook delivery pending |
| Individual receipt, preparation, collection and problem reporting | Three simulated pickups and open-issue checks; actual sandbox preparation, ready receipt and exported payment mode | Local flow verified; actual sandbox collection remains pending |
| Proposed private object storage and signed-in deployment | Workspace-private image data; optional Supabase JWT adapter; Docker/Render configuration | Dedicated object storage and deployed account paths are not integrated/verified |
| Model evaluation, about 30 listings/60 requests and human sessions | Synthetic 30/60 text probes, frozen labels, offline parser report and actual SOCLAAS evaluation | Actual text scores available; independent labels, model comparison, real-photo accuracy and human sessions remain unverified |
| Public licensed source and reproducible run instructions | Public repository, MIT licence, CI Docker startup and README | Available; connected run still requires provider configuration |
| Demo script, user's recording, final edit and public YouTube video | 352-word script, storyboard, original cards and app gallery | Preparation complete; recording, final video and public URL missing |
| Devpost draft and final submission confirmation | Saved draft `1234351`; live preview at https://devpost.com/software/reclaim-us0lrm shows the updated story and eight screenshots; rating explanation and three user-confirmed eligibility declarations verified; replacement of the older source attachment unverified | Draft saved; demo/video, current payment status in the story and final agreement/submission remain pending |

The full goal is not achieved. Completing the connected release requires provider/account input, the user's recording, actual provider proof, and final publication/submission. Prepared documentation and simulated results are not substitutes for those gates.
