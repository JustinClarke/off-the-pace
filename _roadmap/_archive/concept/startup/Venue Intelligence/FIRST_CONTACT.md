# First Contact Message — Event Management Partner

> Copy-paste-ready. Adjust tone to match your relationship with this person.

---

## Casual version (if you know him well)

Hey [name],

Quick question — I'm building a data analytics tool for event operations and
I think your world is the perfect testbed.

The idea: take the data you already collect (ticket scans, POS transactions,
guest lists) and turn it into a post-event ops report that shows you exactly
when and where you were understaffed or overstaffed — down to the 15-minute
window.

I'd do the first one completely free. All I'd need is:

1. Ticket scan data from 1–2 past events (CSV export from whatever ticketing
   platform you use — Eventbrite, Platinumlist, etc.)
2. If you have it: POS/bar transaction timestamps
3. A staff schedule from the same event (even rough — "3 people on the door,
   5 on bar")

The output would be a report showing: "At 9:15pm, 400 people arrived in 10
minutes at Gate A. You had 2 staff there. Here's the arrival curve, here's
when the surge peaked, here's the recommended staffing plan for next time."

Would you be open to sharing data from a past event so I can build a prototype?
Your data stays private — this is just proof-of-concept.

---

## Professional version (if it's more of a business relationship)

Hi [name],

I'm developing a data analytics platform for event operations — specifically
focused on optimizing staffing and crowd flow using data that event managers
already collect but rarely analyze systematically.

I'd like to pilot the tool using historical data from one of your past events.
The deliverable would be a complimentary post-event operations report covering:

- Arrival/departure curves by gate/zone
- Peak occupancy windows (15-minute granularity)
- Staffing adequacy analysis (attendees-per-staff by zone and time)
- Revenue-per-head velocity (if POS data is available)

What I'd need from you:
1. Ticket scan exports (timestamps + gate identifiers) from 1–2 events
2. Staff schedule for the same event(s)
3. Optionally: POS transaction timestamps

All data would be handled confidentially and used solely for this prototype.
Would you be open to a quick call to discuss?

---

## Three questions to ask on the call

These determine your entire Phase 1 architecture:

1. **"What ticketing platform do you use, and can you export scan data as CSV?"**
   → Determines ingestion format. Eventbrite, Platinumlist, and most platforms
   allow CSV export. If they use a custom system, ask what fields are available.

2. **"Do you have any data on when people actually leave, or just when they
   arrive?"**
   → Most events only scan on entry, not exit. If there's no exit data, you
   model departure curves from POS activity dropoff or make assumptions. This
   is a critical constraint to know upfront.

3. **"What's the one question you wish you could answer after every event but
   can't?"**
   → Let him define the problem. His answer might be completely different from
   what you expect — and it's the answer that determines what the product
   actually does.
