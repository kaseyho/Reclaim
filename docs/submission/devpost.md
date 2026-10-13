# Reclaim

## Tagline

Buy the pieces you need. Reclaim finds the people who need the rest.

## Inspiration

A student furnishing a room might find a good moving-out bundle containing a desk, lamp, chair and monitor, while only needing the desk and lamp. The seller wants to clear the entire lot. The buyer has to stretch their budget, organise a group manually, or walk away.

Reclaim explores a marketplace built around complementary demand: several people can buy different goods from the same larger offering.

## What it does

Sellers describe a divisible bundle, review extracted inventory, confirm its attributes, and agree to separate fulfillment. Buyers describe what they need and confirm their budget, quantities, attributes, pickup location and deadline.

Reclaim solves for a complete allocation. It explains what blocks an incomplete group, such as a missing monitor buyer. When the group becomes feasible, each participant reviews an immutable proposal showing their exact goods and price. Prices follow disclosed seller-confirmed reference weights, with deterministic cent rounding.

Each buyer has an individual purchase from the same cooperating merchant. The PayPal sandbox adapter uses authorization before capture: Reclaim checks that all buyers and the seller have accepted, all required authorizations are ready, inventory is still valid, and the checkout window has not expired. A deal is paid only when every capture is confirmed complete.

The seller then prepares separate orders. Buyers receive individual receipts and pickup codes, and can report a problem. If a deal fails, the backend reconciles uncertain outcomes, refunds completed captures, and voids remaining authorizations before releasing inventory.

Furniture, creator equipment and divisible sealed bulk goods use the same allocation and payment engine.

## How we built it

React, Vite and TypeScript provide the marketplace, seller review, buyer review, checkout, and order workspace. FastAPI and Pydantic validate API commands. SOCLAAS supplies text/image inventory extraction and buyer interpretation through the OpenAI Python SDK's Chat Completions API. Its requested `default` alias returned `qwen3.6:35b` in the verified runs. JSON mode is followed by local schema validation. An optional OpenAI Responses adapter remains available. Seller and buyer confirmation establish usable facts; model suggestions alone do not satisfy hard constraints.

Google OR-Tools CP-SAT solves integer quantity assignments with complete-request, inventory, attribute, budget and fulfillment constraints. A separate invariant validator recomputes the published allocation and price split.

The PayPal JavaScript SDK handles buyer approval. Server-side Orders v2 and Payments v2 handle authorization, capture, void and refund. Stable request identifiers, persisted operation outcomes, verified webhook receipt and a durable job outbox support recovery and restart. PostgreSQL supports row locking; SQLite is the single-process local development adapter.

The repo contains Docker and Render deployment configuration, full local setup instructions, seeded judge scenarios, and focused automated verification.

## Challenges

Matching attractive items individually doesn't prove that an entire lot can be sold. Complete requests, confirmed attributes, quantity limits and deterministic cent rounding must all agree. We kept that computation separate from AI language interpretation and checked solver outcomes independently.

Separate buyer payments are not atomic. A successful authorization can still fail at capture, and a lost response does not mean a failed payment. The recovery workflow preserves uncertainty until the provider outcome is resolved and keeps fulfillment blocked while refunds or voids remain incomplete.

## Accomplishments

The local end-to-end walkthrough covers fresh buyer requests, complementary allocations, participant review, coordinated simulated payment outcomes, individual receipts and pickup. Focused tests exercise allocation invariants, concurrency, stale proposals, timeouts, partial capture, refunds and restart behavior.

Local application checks pass 46 tests with one PostgreSQL-only skip, including 13 AI provider-contract checks. Twelve additional checks verify the evaluation grader. PostgreSQL and Docker checks run in GitHub Actions. Browser checks include an entirely fresh seller listing and three fresh requests, all three example categories, partial-payment recovery, receipt export and independent pickup completion. Actual SOCLAAS extraction from a fictional illustration and fresh buyer interpretation also produce a complete $72 / $48 / $80 allocation after review.

The text development set contains 30 synthetic listings and 60 synthetic requests, with agent-authored labels kept out of the runtime prompts. SOCLAAS returned 90/90 validated responses at 96.48% proposal-field precision, 94.88% recall and 70/90 exact cases; median/p95 model-call latency was 1.54/2.99 seconds. The probes informed schema clarification, so these are development results, not untouched held-out accuracy or usable confirmed-fact precision. Independent labels, representative real photographs and human sessions remain pending.

**Current local status:** actual SOCLAAS text and image input are verified. PayPal sandbox credentials authenticate; Alice's actual $72 authorization and its automatic void after checkout expiry were verified through the provider API. Three distinct buyer approvals, all captures, refund recovery, merchant-dashboard review, webhook delivery, deployment verification and the final public YouTube demo remain pending. Historical payment screenshots show labelled simulations. The examples are fictional fixtures and do not establish real seller consent or user demand. The saved Devpost story still needs this latest connection status applied.

## What we learned

The useful AI contribution is finding purchase opportunities inside a larger offering and making unmet demand understandable. The transaction still needs exact, inspectable terms, independently checked allocations, and honest payment states.

## What's next

Pilot the workflow with students furnishing rooms, creators assembling equipment, and sellers clearing mixed inventory. Measure seller preparation costs, task completion, buyer affordability against equivalent alternatives, and fulfillment outcomes. Broader merchant onboarding, delivery, and transferable service units follow after that evidence.

## Built with

Python, TypeScript, React, Vite, FastAPI, Pydantic, SOCLAAS, Qwen 3.6, OpenAI Python SDK, Google OR-Tools, SQLAlchemy, PostgreSQL, PayPal JavaScript SDK, PayPal Orders v2, PayPal Payments v2, pytest, Hypothesis.

Add Render to the built-with list only if a Render deployment is actually completed.

## Links / testing notes

- Repository: https://github.com/kaseyho/Reclaim
- Functional demo URL: **PENDING deployment**. Complete local run instructions are in README.md.
- Public YouTube video: **PENDING user's recording and final edit**.
- Payment environment: sandbox only; no real-money payments.
- Provider modes are independent. Actual SOCLAAS AI and PayPal sandbox are configured locally. Keep the applicable mode labels visible in footage, including historical simulations.
- All listing examples and original SVG illustrations are fictional fixtures; they are not evidence of real seller consent or demand.

## Saved technical custom-field answers

Main technology requirement (under 255 characters):

> PayPal JS SDK + Orders/Payments v2 manage authorization, capture and void/refund. SOCLAAS Chat Completions (default, returned qwen3.6:35b) extracts text/images and buyer needs; OR-Tools validates allocations. AI calls verified; sandbox payments pending.

AI tools used while building (under 255 characters):

> Codex assisted coding, verification and submission preparation. The app now uses SOCLAAS through the OpenAI Python SDK, with default resolving to qwen3.6:35b in verified text/image calls. The optional OpenAI Responses adapter remains available.

Testing instructions (under 255 characters):

> Run README's setup; use Maya for listings and Alice/Ben/Chen for requests, acceptance and pickup. Configure SOCLAAS or OpenAI for AI. Current payments are simulated; real sandbox needs .env keys and three PayPal test buyers. No shared credentials.

## Submission state

On 13 October 2026, the user confirmed registration and the authenticated hackathon page exposed an existing empty draft. That draft was populated and saved; no duplicate project was created.

- Draft preview: https://devpost.com/software/reclaim-us0lrm
- Draft editor: https://devpost.com/submit-to/31302-paypal-ai-hackathon/manage/submissions/1234351-reclaim/project_details/edit
- Additional information: https://devpost.com/submit-to/31302-paypal-ai-hackathon/manage/submissions/1234351-reclaim/additional-info/edit
- Submission ID: `1234351`; project ID: `1479953`.
- Saved and verified: title, tagline, original thumbnail, project story, twelve built-with tags, repository link, six captioned screenshots, factual technical answers, and the user's supplied submitter/feedback choices.
- The preview explicitly says **INCOMPLETE SUBMISSION**. The editor says **DRAFT**, with 2/5 steps complete; incomplete steps can still contain saved fields.
- Previously verified after revisiting the editor: the user's rating explanation and an optional `reclaim-source.zip` attachment from before the SOCLAAS changes. A fresh complete source ZIP is prepared locally, excludes secrets and workspace data, and contains the current application, instructions, assets and evaluation reports. Replacement of the uploaded ZIP is not verified. The latest Additional info and Project details views expose no ZIP upload control or attachment filename; the public GitHub repository contains the updated source.
- Updated and verified after the SOCLAAS connection: factual provider/tool answers, judge instructions, project story and two actual-model screenshots with captions. The gallery now has eight images. Earlier images retain their historical demo labels.
- The user confirmed all three required eligibility declarations. They were checked, saved and read back as checked. The final Rules/Terms agreement remains unchecked.
- Pending: working demo/test-build URL, public YouTube video, complete payment/recovery evidence, the latest PayPal connection status in the saved story and testing instructions, and final agreement/submission.

Complete the final evidence and video, then inspect the final form and verify Devpost's submission confirmation. A saved draft and visible project preview do not establish hackathon submission.
