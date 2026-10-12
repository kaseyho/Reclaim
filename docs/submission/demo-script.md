# Reclaim demo — talking-head script

Target: approximately 2 minutes 40 seconds, leaving room for opening/closing cards under the three-minute limit. Read naturally, around 135–145 words per minute. Record the voice in one take; the product footage will cover most of the middle, with your talking head returning at the end.

This script describes the intended connected release. Before publishing it, verify a fresh OpenAI extraction and actual PayPal sandbox authorizations, captures, and cancellation recovery. The current local walkthrough labels its parser and payments as simulated. Do not cover those labels and present the simulation as a live integration.

## Read this

Imagine you’re furnishing a student room. You need a desk and a lamp, but the seller is offering them with a chair and a monitor. Buying everything stretches your budget, and leaves you with things you don’t need.

Reclaim makes that bundle purchasable together. You buy your pieces, and Reclaim finds the people who need the rest.

Here’s a moving-out bundle: a desk, lamp, chair, and monitor. The seller adds a description and a photograph. AI proposes the inventory, and the seller checks each item, confirms its condition, and agrees to separate the orders. Unknown dimensions stay unknown until they’re confirmed.

Alice asks for a desk under one metre wide and a lamp, with a ninety-dollar budget. Ben wants the chair, under sixty dollars. Reclaim identifies the remaining need: someone to buy the monitor.

When Chen adds that request, the group becomes complete. Alice’s share is seventy-two dollars, Ben’s is forty-eight, and Chen’s is eighty. Together, they cover the two-hundred-dollar total, including preparation.

Those prices come from seller-confirmed reference weights. Budgets set a limit; they don’t decide what someone is charged. A constraint solver checks the whole allocation, and a separate validator checks it again.

Now each buyer and the seller review the same proposal. Everyone accepts their exact goods, price, and pickup terms.

Each buyer then approves an individual PayPal sandbox authorization. Reclaim waits for every authorization before starting capture. Once every capture is confirmed, each buyer gets a receipt and pickup code, and the seller prepares the separate orders.

Separate payments can fail partway through. In this labelled failure simulation, one capture succeeds and the next fails. Reclaim refunds the completed capture, voids the remaining authorizations, and keeps pickup unavailable until recovery finishes. A lost response is reconciled using the same stored operation.

The same engine also handles creator equipment and quantities from sealed bulk cases.

The opportunity is practical: students and creators can access the pieces they need, while sellers can complete larger sales. The next step is testing that experience with real buyers and sellers.

Buy the pieces you need. Reclaim finds the people who need the rest.

## Recording instructions

- Record landscape, ideally 1920 × 1080 at 30 fps. Use the rear camera or a webcam at eye level.
- Keep your face centred with space around your head. We can crop this into a small overlay during the demo.
- Use a quiet room and a microphone close to you. Face a window or soft light.
- Read only the “Read this” paragraphs. Leave two seconds of silence at the beginning and end.
- Pause briefly between paragraphs. If you stumble, pause and repeat the whole sentence; it makes editing easier.
- Send the original video file after recording. Avoid an export that adds background music, filters, or compression.

## Editing plan

Use your talking head for the opening and closing. Show product footage for the workflow, with a small talking-head overlay where it doesn't cover controls. Keep cursor movement deliberate. Add subtitles from the actual recording, callouts for the three prices, and a visible “PayPal sandbox” label on payment footage. Use no music unless we have a suitable licence.

Final export: 1920 × 1080, H.264 video, AAC audio, under 180 seconds. YouTube visibility must be public according to the event rules. Add the public video URL to Devpost only after watching the uploaded video end to end.
