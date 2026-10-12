# Provider setup — Reclaim

This is the setup needed to replace the labelled local parser/payments with actual provider calls. Keep secrets in the ignored `.env` file locally or the host's secret environment settings. Never paste them into Devpost, GitHub or chat.

## 1. OpenAI

1. Sign in at https://platform.openai.com/ and create an API project/key at https://platform.openai.com/api-keys.
2. Ensure the project can make API calls; API usage billing is separate from a ChatGPT subscription. Choose a budget in the provider dashboard.
3. Add `OPENAI_API_KEY` to `.env`. Keep `OPENAI_MODEL=gpt-4.1-mini-2025-04-14` unless an evaluated replacement is chosen.
4. Restart the API and reload the browser. **Connection status** should say OpenAI configured. A successful fresh extraction establishes the actual provider call.
5. As Maya, extract a fresh listing containing text and a photo. As Chen, interpret a fresh request. Inspect **Activity & evidence → AI traces** for the actual model, response ID, latency and token usage.

The chosen snapshot supports image inputs, Responses API and structured outputs. [Model documentation](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

## 2. PayPal sandbox

1. Sign in at https://developer.paypal.com/dashboard/. Use the **Sandbox** environment.
2. Create or select a business sandbox account for the single merchant. Create three personal sandbox buyer accounts, with sufficient test balance.
3. Under **Apps & Credentials → Sandbox**, create an app associated with that merchant.
4. Copy the app's client ID to `PAYPAL_CLIENT_ID` and secret to `PAYPAL_CLIENT_SECRET`. Set `PAYMENT_MODE=sandbox`.
5. Restart the API, reload the browser, and start a new isolated example. The app should show **PayPal sandbox · test transactions only**. The purchase button must open PayPal checkout, not the demo authorization button. Existing demo deals remain bound to their simulated provider and cannot be turned into sandbox payments.
6. Complete the moving bundle in Reclaim. Accept separately as Alice, Ben, Chen and Maya. Use a distinct personal sandbox account for each actual approval. Sandbox passwords stay in PayPal's login page.
7. Check each resulting authorization and capture ID in the sandbox merchant dashboard. Record the IDs and statuses, with buyer identifiers redacted, in the release evidence.

Reclaim always targets `https://api-m.sandbox.paypal.com`. It has no live payment mode. Each PayPal order uses authorization intent and a server-calculated USD amount. [Authorization and capture](https://developer.paypal.com/docs/checkout/standard/customize/authorization/), [Orders v2](https://developer.paypal.com/api/orders/v2/), [Payments v2](https://developer.paypal.com/api/payments/v2/).

### Webhook

After the API has a reachable HTTPS URL, register:

```text
https://YOUR-API-HOST/api/webhooks/paypal
```

Subscribe to relevant order approval, authorization created/voided, capture completed/denied/refunded, and refund outcome events offered in the sandbox dashboard. Set the returned webhook ID as `PAYPAL_WEBHOOK_ID` and restart the service. The endpoint verifies signatures through PayPal's verification API before accepting or deduplicating an event. It stores event identifiers and schedules provider reconciliation; an unverified client event cannot mark a purchase paid.

Confirm delivery in the sandbox webhook dashboard and test a repeated event. [Webhook documentation](https://developer.paypal.com/api/rest/webhooks/), [idempotency](https://developer.paypal.com/api/rest/reference/idempotency/).

### Cancellation evidence

Use a second fresh workspace and approve only one buyer. Withdraw before every buyer authorizes. Verify the existing authorization becomes voided. For refund evidence, complete a group, then request cancellation before any pickup is recorded and verify each refund status directly. Do not claim that a requested or pending refund is complete.

The visible demo recovery lab can demonstrate partial failure, but it does not create sandbox payment evidence. Actual sandbox negative testing must be separately verified.

## 3. PostgreSQL / Supabase

1. Create or select a PostgreSQL project. Supabase is compatible.
2. Obtain its connection URL using a supported direct or pooled connection from the host. Use SSL where required by the provider.
3. Set `DATABASE_URL` on the API and any separate worker. Standard `postgres://` and `postgresql://` URLs are converted to the psycopg SQLAlchemy driver.
4. Start the app once to create its tables. Confirm `/api/health` reports `postgresql`.
5. Check that a workspace and a queued job survive a service restart.

For isolated judge access, leave `AUTH_MODE=workspace`. Each judge receives separate random persona tokens in a separate workspace. For a signed-in walkthrough, set `AUTH_MODE=supabase`, `SUPABASE_URL`, and the public `SUPABASE_PUBLISHABLE_KEY`, then create a judge test account in Supabase. The app has email/password sign-in and token refresh; the API verifies JWT issuer, audience, expiry and subject against workspace ownership. Use asymmetric signing keys exposed by the project's JWKS endpoint. Never put a service-role or secret key in the public client-key setting. Verify the actual account access path before distributing judge credentials.

This hackathon build stores uploaded listing image data inside the private workspace aggregate. A dedicated private object-storage adapter is a later storage improvement; do not describe it as already integrated.

## 4. Render

1. Connect https://github.com/kaseyho/Reclaim to a Python/Docker-capable Render service, using Dockerfile.
2. Set `APP_URL` to the public HTTPS URL and `CORS_ORIGINS` to that same origin.
3. Set the database and provider secrets. Choose an always-on service if it must run cancellation and payment recovery while no browser is open.
4. Deploy, inspect health, run the principal flow through the deployed app, restart during queued work, and verify all provider IDs against the dashboard.
5. Keep access available through 16 December 2026, 00:00 Singapore time, when the published judging period ends. Verify current resource expiry, uptime limits and cost in your account before confirming the service plan.

An optional separate worker uses `PYTHONPATH=backend python -m reclaim.worker`, shares the database/provider settings, and needs `AUTO_WORKER=false` on the API. [Render background workers](https://render.com/docs/background-workers).

## Information still needed to finish the connected release

- A local `.env` populated with OpenAI and PayPal sandbox settings, or the exact hosting project/configuration location.
- A database/hosting account and chosen plan if a hosted demo is desired.
- Actual sandbox buyer approvals and captured/refunded/voided provider evidence.
- The user's talking-head recording for the final edit.
- Authenticated Devpost and YouTube access for the draft, upload and final submission.

Account signup, binding terms, credentials and paid service choices must be completed in the relevant provider account; they are not inferred from missing configuration.
