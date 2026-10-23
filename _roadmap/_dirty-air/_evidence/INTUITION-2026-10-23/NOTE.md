# Intuition review: which gap unit a viewer should see (2026-10-23)

Read-only review. Nothing was run. Sources: `../GRAIN-2026-10-23/NOTE.md` (its forking-paths and no-rescue points still stand), `../../wi/DA-design-note.md`, `../DA-01-2026-10-23-settle/NOTE.md` and the DA-01 metres facts, plus the current app copy in `app/src/features/dirty-air-lap-map/` and `app/src/features/dirty-air-cost/page.tsx`. The owner has said cost and build time do not matter, so this note is only about how easy the display is to read and trust.

**Scope.** The cost itself is in seconds under every option. The only question here is how the **gap to the car ahead** is labelled in the session replay and in the lap and sector views. The analysis stays seconds-first either way.

## 1. "How much dirty air is this lap?"

What a viewer would say out loud about a driver stuck behind another car is almost always a time: "he's been stuck within a second of Ocon for ten laps and it's cost him about half a second." Both halves of that sentence are in seconds, the exposure and the cost. "He's been 30 metres behind" is something commentators say only at very close range ("right on his gearbox"), and almost never as a running number. With seconds, the exposure and the cost are in one unit, so "1.2 s behind, losing 0.08 s per lap" reads as a single story. Metres would need the viewer to convert in their head between two units. **Seconds reads more naturally.**

## 2. Replay label next to a car

F1 viewers already see gaps in seconds: the timing tower's interval column, the "within one second" DRS rule (through 2025), and pit-window and undercut graphics. The app already uses seconds too. The lap map shows "Min gap: 0.84s" and its states are defined as "< 1.0s" and "< 1.5s". A label like "1.2 s" next to a car matches all of that. "40 m" would be a unit the viewer has not seen on an F1 screen, so they would have nothing to compare it with. **"1.2 s" is easier to read.**

## 3. Does metres change meaning around the lap?

Yes, and a viewer could not tell why. At a steady 1 s gap the metres figure is about 80 m on the straight and about 25 m in a slow corner (DA-01). Over one lap at a constant gap, a metres label would rise and fall from about 80 m to 25 m and back. To the viewer it would look like the chaser is closing in and dropping back every lap when nothing has changed.

Read the other way: 40 m in a slow corner is about 1.6 s, while 40 m on a straight is about 0.5 s. A viewer would read the two "40 m" labels as equally close. **For the model, that reading is wrong.** The cost is priced in time bands, so the straight-line 40 m sits in a much costlier band than the corner 40 m. The viewer would see the same label next to very different costs and lose trust in the number. (The physical wake is spatial, so "40 m is 40 m" is not absurd. But it is not what the shown cost measures.)

There is also a trust problem. The metres gap from distance and speed is biased by about -0.13 s at 1-2 s and -1.04 s above 2 s (DA-01). The in-house metres gap has not been checked against timing at all. A label whose errors grow with the gap is a weak thing to put next to a gated number.

## 4. Both on screen?

| Option | Intuitive? | Why |
|---|---|---|
| Seconds only | **Most** | One unit for both exposure and cost, the same unit as the broadcast, and steady around the lap. |
| Metres only | Least | An unfamiliar unit that rises and falls by corner type and does not match the cost's bands. |
| Seconds, with metres as a small secondary label | Middle | It adds a sense of physical closeness. But the secondary label rises and falls while the main one holds steady, so viewers will ask which one is right. It also invites the "pick the number that suits your argument" problem from the grain review, in a smaller form. |

Showing both helps a viewer only if they already understand that time gap and distance gap differ with speed. Most will not. In the replay the cars are already drawn on the track map, so the viewer can already see how close they are in space. A metres label adds little that the picture does not show.

## 5. Recommendation (display only)

**Seconds only** for every gap label in the replay and in the lap and sector views. The track map carries the sense of space. Metres stays where the grain review put it: a sensitivity check, shown at most as a methods-page chart.

**Strongest argument against.** The replay map will contradict the label. In a slow corner the two dots will look almost touching (about 25 m) while the label still reads "1.0 s", the same as on the straight, where the dots are visibly far apart. A viewer trusts what they see, and the wake really is a thing in space. A seconds-only label can look as if it ignores the closeness the viewer can plainly see. A small metres label would explain the picture.

**Side observation, not part of this decision.** The current lap-map page says its gap is "distance-to-driver-ahead ÷ speed". That is the conversion DA-01 found biased above 1 s. Its seconds labels are therefore already carrying a metres-derived error.

## Owner decision

1. Display: seconds only, or seconds with a small secondary metres label. Metres only is not recommended by either the grain review or this one.
2. If a secondary label is chosen: show it only after the in-house metres gap passes the same timing check as seconds (median error under 0.1 s below 2 s), and add tooltip copy explaining why it changes with speed.
