# Reclaim

## Tagline

Buy the pieces you need. Reclaim finds the people who need the rest.

## Inspiration

A student furnishing a room might find a good moving-out bundle containing a desk, lamp, chair and monitor, while only needing the desk and lamp. The seller wants to clear the entire lot. The buyer has to stretch their budget, organise a group manually, or walk away.

Reclaim explores a marketplace built around complementary demand: several people can buy different goods from the same larger offering.

## What it does

Sellers describe a divisible bundle, review extracted inventory, confirm its attributes, and agree to separate fulfillment. Buyers describe what they need and confirm their budget, quantities, attributes, pickup location and deadline.

Reclaim solves for a complete allocation. It explains what blocks an incomplete group, such as a missing monitor buyer. When the group becomes feasible, each participant reviews an immutable proposal showing their exact goods and price. Prices follow disclosed seller-confirmed reference weights, with deterministic cent rounding.

Each buyer pays the same cooperating merchant through an individual PayPal sandbox order. Authorization precedes capture: Reclaim checks that all buyers and the seller have accepted, all required authorizations are ready, inventory is still valid, and the checkout window has not expired. A deal is paid only when every capture is confirmed complete.

The seller then prepares separate orders. Buyers receive individual receipts and pickup codes, and can report a problem. If a deal fails, the backend reconciles uncertain outcomes, refunds completed captures, and voids remaining authorizations before releasing inventory.

Furniture, creator equipment and divisible sealed bulk goods use the same allocation and payment engine.

## How we built it

React, Vite and TypeScript provide the marketplace, seller review, buyer review, checkout, and order workspace. FastAPI and Pydantic validate API commands. OpenAI's Responses API supplies structured inventory extraction and request interpretation through a provider adapter. Seller and buyer confirmation establish usable facts; model suggestions alone do not satisfy hard constraints.

Google OR-Tools CP-SAT solves integer quantity assignments with complete-request, inventory, attribute, budget and fulfillment constraints. A separate invariant validator recomputes the published allocation and price split.

The PayPal JavaScript SDK handles buyer approval. Server-side Orders v2 and Payments v2 handle authorization, capture, void and refund. Stable request identifiers, persisted operation outcomes, verified webhook receipt and a durable job outbox support recovery and restart. PostgreSQL supports row locking; SQLite is the single-process local development adapter.

The repo contains Docker and Render deployment configuration, full local setup instructions, seeded judge scenarios, and focused automated verification.

## Challenges

Matching attractive items individually doesn't prove that an entire lot can be sold. Complete requests, confirmed attributes, quantity limits and deterministic cent rounding must all agree. We kept that computation separate from AI language interpretation and checked solver outcomes independently.

Separate buyer payments are not atomic. A successful authorization can still fail at capture, and a lost response does not mean a failed payment. The recovery workflow preserves uncertainty until the provider outcome is resolved and keeps fulfillment blocked while refunds or voids remain incomplete.

## Accomplishments

The local end-to-end walkthrough covers fresh buyer requests, complementary allocations, participant review, coordinated simulated payment outcomes, individual receipts and pickup. Focused tests exercise allocation invariants, concurrency, stale proposals, timeouts, partial capture, refunds and restart behavior.

The full suite passes 34 tests against PostgreSQL 16 in GitHub Actions. The Docker image builds, starts and serves the application. Browser checks include an entirely fresh seller listing and three fresh requests, all three example categories, partial-payment recovery, receipt export and independent pickup completion.

**Release evidence to add before submitting:** actual OpenAI extraction/interpretation traces; actual PayPal sandbox authorization/capture/void/refund IDs; final browser verification report; hosted URL or verified complete run instructions; final public YouTube demo.

## What we learned

The useful AI contribution is finding purchase opportunities inside a larger offering and making unmet demand understandable. The transaction still needs exact, inspectable terms, independently checked allocations, and honest payment states.

## What's next

Pilot the workflow with students furnishing rooms, creators assembling equipment, and sellers clearing mixed inventory. Measure seller preparation costs, task completion, buyer affordability against equivalent alternatives, and fulfillment outcomes. Broader merchant onboarding, delivery, and transferable service units follow after that evidence.

## Built with

Python, TypeScript, React, Vite, FastAPI, Pydantic, OpenAI Responses API, Google OR-Tools, SQLAlchemy, PostgreSQL, PayPal JavaScript SDK, PayPal Orders v2, PayPal Payments v2, pytest, Hypothesis.

Add Render to the built-with list only if a Render deployment is actually completed.

## Links / testing notes

- Repository: https://github.com/kaseyho/Reclaim
- Functional demo URL: **PENDING deployment**. Complete local run instructions are in README.md.
- Public YouTube video: **PENDING user's recording and final edit**.
- Payment environment: sandbox only; no real-money payments.
- Local demo mode clearly labels its deterministic parser and simulated payments. Those labels must remain visible in any footage using that mode.
- All listing examples and original SVG illustrations are fictional fixtures; they are not evidence of real seller consent or demand.

## Short custom-field answers

PayPal integration (under 255 characters):

> Individual PayPal sandbox orders authorize each buyer's exact allocated purchase. Capture starts after all approvals. The backend reconciles failures, refunds completed captures, and voids remaining authorizations before releasing inventory.

AI integration (under 255 characters):

> OpenAI Responses API proposes structured inventory and buyer requirements. People review the facts; OR-Tools checks quantities, budgets and pickup constraints. Reclaim explains the missing demand that prevents a whole bundle from selling.

## Submission state

This is prepared copy, not proof of a saved or submitted Devpost entry. Verify the live Devpost project before creating or resubmitting anything. Complete the final evidence and video first, then inspect the final form and confirm submission on Devpost.

Live check on 12 October 2026: the signed-in account's **My projects** page says to register for this hackathon and shows no project entry. Registration requires personal-experience answers, eligibility confirmation and agreement to the official rules/Devpost terms. The registration form was opened for the user; it has not been submitted by the agent.
