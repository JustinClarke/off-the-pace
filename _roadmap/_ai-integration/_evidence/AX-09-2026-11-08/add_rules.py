"""AX-09: append seven rules and two kinds to policy.json. Re-reads the file at run time; existing
rules are not touched (json round-trip with indent=2, ensure_ascii=False is byte-exact here)."""
import json
import sys

PATH = sys.argv[1]

BUILD_LOG = "_roadmap/_ai-integration/status/build-log.json"
AD3_QUOTE = "Query-builder results are labelled computed_not_card and the answer must state they are plain counts or averages."


def card(**kw):
    return kw


def ex(name, expect, cards, answer, question=None):
    inp = {"cards": cards, "answer": answer}
    if question:
        inp = {"question": question, **inp}
    return {"name": name, "expect": expect, "input": inp}


qcard = card(id="q3f9a1c0d2b7e", metric="qv_pit_stops.pit_lane_loss_measured_s", label="computed_not_card",
             aggregate_fn="median", n=14, n_unit="rows", source_page="qv_pit_stops")

rules = []

rules.append({
    "code": "COMPUTED_NOT_CARD_WORDING",
    "kind": "computed_not_card",
    "status": "active",
    "ruling": "AD3",
    "applies_to": {"pages": [], "metrics": ["every query_data result (AX-06), projected by queryResultToCheckerCard"]},
    "condition": "The answer uses a query-builder result. It is a plain aggregate over published, observed rows, not a fact card and not a model output (AD3, HD4 A).",
    "triggers": [{"card": [{"field": "label", "op": "eq", "value": "computed_not_card"}]}],
    "required_wording": {
        "description": "Say the number is a plain count, average, median, minimum, maximum or total, computed from the data.",
        "all_of": [
            ["\\b(plain|simple|raw|straight) (count|average|mean|median|total|sum|minimum|maximum|min|max)s?\\b"],
            ["\\bfrom the (published |app |lap |race |stint )?data\\b", "\\b(computed|counted|averaged|summed|taken) (directly |straight )?(from|over)\\b"],
        ],
    },
    "forbidden_claim": {
        "description": "Call a computed aggregate a rating, a skill measure, modelled or predicted.",
        "patterns": [
            "(?<!not a )(?<!no )\\bratings?\\b",
            "(?<!not )\\bmodell?ed\\b",
            "(?<!not )\\bpredict(ed|ion|s)?\\b",
            "(?<!not a )(?<!no )\\bskill\\b",
        ],
    },
    "sources": [{"file": BUILD_LOG, "line": None, "quote": AD3_QUOTE}],
    "examples": [
        ex("calls a median pit-lane loss a modelled skill rating", "fail", [qcard],
           "McLaren's crews rate best: their modelled pit skill is 21.4 s [result q3f9a1c0d2b7e]."),
        ex("says it is a plain median computed from the data", "pass", [qcard],
           "Across the 14 stops with a measured loss, the plain median pit-lane loss was 21.4 s, computed from the published stop data [result q3f9a1c0d2b7e]."),
        ex("a fact card with label measured does not fire it", "not_fired",
           [card(id="c1", metric="stint_length_laps", label="measured", n=40, n_unit="stints")],
           "The stint lasted 22 laps [card c1]."),
    ],
})

held = card(id="ghost_finish:2024_8:LEC", metric="predicted_finish_position", label="modelled", status="held",
            held_reason="Dirty-air-dependent: waits on wake calibration (XW).", value=None, n=0, n_unit="races")
held_plain = card(id="era_rating.season:2024:LEC", metric="era_adjusted_rating", label="modelled", status="held",
                  held_reason="Dirty-air-dependent: waits on wake calibration (XW).", value=None, n=0, n_unit="races")
rules.append({
    "code": "HELD_CARD_WORDING",
    "kind": "held_card",
    "status": "active",
    "applies_to": {"pages": [], "metrics": ["every card with status held (dirty-air-dependent, traffic-cost, ML and pit-call classes in v1)"]},
    "condition": "A card is held: the figure exists in the app but may not be quoted until wake calibration, the ML redo or the pit-call re-measure lands.",
    "triggers": [{"card": [{"field": "status", "op": "eq", "value": "held"}]}],
    "required_wording": {
        "description": "Say the figure is not available yet (held), and say what it waits on: wake calibration, the ML redo, or the pit-call re-measure.",
        "all_of": [
            ["\\bheld\\b", "\\bnot (yet )?available( yet)?\\b", "\\bnot (yet )?published\\b"],
            ["\\bwake[- ]calibration\\b", "\\b(ML|model) redo\\b", "\\bre-?measure", "\\breproduction rate\\b", "\\bdirty[- ]air (work|calibration)\\b"],
        ],
    },
    "forbidden_claim": {
        "description": "Give an estimate, a guess or a 'probably' for the held figure.",
        "patterns": [
            "\\bprobably\\b",
            "\\b(likely|roughly|approximately|around|about|~) ?[-+]?\\d",
            "\\b(my|a rough|our|best) (estimate|guess)\\b",
            "\\bI(?:'d| would) (estimate|guess)\\b",
            "\\bshould be (around|about|near)\\b",
            "\\bin the region of\\b",
        ],
    },
    "sources": [
        {"file": "_roadmap/_ai-integration/_evidence/ax-audit-2026-11-07/design-ai-access.md", "line": 143, "quote": "A `held` card is published so the assistant can say why a number is not available yet. A held card has no `value`."},
        {"file": "_roadmap/_ai-integration/status/BUILD-ORDER.md", "line": 23, "quote": "A card may only be published for a class that is live."},
    ],
    "examples": [
        ex("guesses the held figure", "fail", [held_plain],
           "Leclerc's 2024 era rating is not out yet, but it is probably around 0.2 s [card era_rating.season:2024:LEC]."),
        ex("says it is held and what it waits on", "pass", [held_plain],
           "Leclerc's 2024 era rating is held: it is not available yet because it waits on the wake calibration work [card era_rating.season:2024:LEC]."),
        ex("an active card does not fire it", "not_fired",
           [card(id="c1", metric="stint_length_laps", label="measured", status="active", n=40, n_unit="stints")],
           "The stint lasted 22 laps [card c1]."),
    ],
})

unav = card(id="teammate_corner:2023_10:HAM-RUS:T15", metric="v_min_delta_kph", label="unavailable", value=None, n=0, n_unit="laps",
            unavailable_reason="one side's telemetry is missing for this corner (CO-22)")
rules.append({
    "code": "UNAVAILABLE_IS_NOT_ZERO",
    "kind": "known_gap",
    "status": "active",
    "applies_to": {"pages": [], "metrics": ["every card with label unavailable (P5: unavailable is a value with a reason, never 0)"]},
    "condition": "A card has no value: the quantity was not measured or cannot be computed for that scope. Complements MISSING_RATING_IS_NOT_ZERO, which covers the pure-pace case.",
    "triggers": [{"card": [{"field": "label", "op": "eq", "value": "unavailable"}]}],
    "required_wording": {
        "description": "Say there is no value: not measured, unavailable, or no data for that scope.",
        "all_of": [
            ["\\bno value\\b", "\\bnot (been )?measured\\b", "\\bunavailable\\b", "\\bnot available\\b", "\\bno (data|figure|number|measurement)\\b"],
        ],
    },
    "forbidden_claim": {
        "description": "Read the missing value as 0, zero or no difference.",
        "patterns": [
            "\\b(is|was|reads|equals?|of|at|scored|rated) (0(\\.0+)?|zero)(?![.\\d])",
            "\\bno (pace )?(advantage|difference|loss|gain)\\b",
            "\\bnothing (was )?(lost|gained)\\b",
        ],
    },
    "sources": [
        {"file": "docs/decomposition/driver-isolation.mdx", "line": 168, "quote": "a missing race is not a zero"},
        {"file": "_roadmap/_ai-integration/_evidence/ax-audit-2026-11-07/design-ai-access.md", "line": 91, "quote": "\"Unavailable\" is a value with a reason, never 0"},
    ],
    "examples": [
        ex("reads an unavailable corner delta as zero", "fail", [unav],
           "Hamilton and Russell were level through Turn 15: the minimum-speed delta was 0, no difference [card teammate_corner:2023_10:HAM-RUS:T15]."),
        ex("says no value was measured", "pass", [unav],
           "There is no value for the Turn 15 minimum-speed delta between Hamilton and Russell: one side's telemetry is missing, so it was not measured [card teammate_corner:2023_10:HAM-RUS:T15]."),
        ex("a measured card does not fire it", "not_fired",
           [card(id="c1", metric="v_min_delta_kph", label="measured", value=3.2, n=12, n_unit="laps")],
           "Hamilton carried 3.2 km/h more minimum speed through Turn 15 [card c1]."),
    ],
})

lapmap = card(id="lap_map:2023_10:HAM", metric="dirty_air_lap_share", label="measured", value=0.42, n=52, n_unit="laps",
              source_page="app/dirty-air-lap-map")
rules.append({
    "code": "LAP_MAP_GREY_CELL",
    "kind": "known_gap",
    "status": "active",
    "applies_to": {"pages": ["/app/dirty-air-lap-map"], "metrics": ["per-lap air state cells and shares on the lap map"]},
    "condition": "A card comes from the dirty-air lap map, where laps with missing telemetry are drawn as free air (grey).",
    "triggers": [{"card": [{"field": "source_page", "op": "matches", "value": "dirty-air-lap-map"}]}],
    "required_wording": {
        "description": "Say a grey (free-air) cell can mean clean air or missing telemetry.",
        "all_of": [
            ["\\b(clean|free)[- ]air\\b"],
            ["\\b(missing|absent|no) (telemetry|data|gap data)\\b", "\\btelemetry (is |was )?(missing|absent)\\b"],
        ],
    },
    "forbidden_claim": {
        "description": "Read a grey cell or a free-air lap as certainly clean air.",
        "patterns": [
            "\\bgr[ae]y\\b[^.]{0,30}\\b(means|shows|is|are|=)\\b[^.]{0,15}\\b(clean|free)[- ]air\\b(?! or)",
            "\\b(definitely|certainly|always) (in )?(clean|free)[- ]air\\b",
        ],
    },
    "sources": [{"file": "docs/app/dirty-air-lap-map.mdx", "line": 21, "quote": "so a grey cell can mean clean air *or* absent data"}],
    "examples": [
        ex("reads grey cells as clean air", "fail", [lapmap],
           "The grey cells mean clean air: Hamilton spent the last 20 laps out of traffic [card lap_map:2023_10:HAM]."),
        ex("says grey can be clean air or missing telemetry", "pass", [lapmap],
           "Hamilton's lap map shows traffic on 42% of laps [card lap_map:2023_10:HAM]. A grey cell can mean free air or missing telemetry, so the grey run late in the race is not certain to be clean."),
        ex("a card from another page does not fire it", "not_fired",
           [card(id="c1", metric="stint_length_laps", label="measured", n=40, n_unit="stints", source_page="app/pit-strategy")],
           "The stint lasted 22 laps [card c1]."),
    ],
})

surv = card(id="survival:2024:SOFT", metric="km_survival_median_laps", label="computed", value=18, n=60, n_unit="stints",
            source_page="app/tyre-cliff-survival")
rules.append({
    "code": "SURVIVAL_LOWER_BOUND",
    "kind": "known_gap",
    "status": "active",
    "applies_to": {"pages": ["/app/tyre-cliff-survival"], "metrics": ["Kaplan-Meier survival curve values, median and quantile tyre life"]},
    "condition": "A card gives a tyre-life survival figure. Where most stints end in a pit stop before the cliff (censored), the curve is a lower bound on tyre life.",
    "triggers": [{"card": [
        {"field": "source_page", "op": "matches", "value": "tyre-cliff-survival"},
        {"field": "metric", "op": "matches", "value": "surviv|\\bkm_|kaplan|tyre_life|median_life"},
    ]}],
    "required_wording": {
        "description": "Say the figure is a lower bound on tyre life (because stints are censored by pit stops).",
        "all_of": [["\\blower bound\\b"]],
    },
    "forbidden_claim": {
        "description": "Say the tyre will last that long, or call it the tyre's limit.",
        "patterns": [
            "\\btyres? (will|would|can) last\\b",
            "\\bwill last\\b",
            "(?<!not )(?<!not the )\\b(true|real) (tyre )?(life|limit)\\b",
        ],
    },
    "sources": [{"file": "docs/app/tyre-cliff-survival.mdx", "line": 34, "quote": "should be read as a lower bound on tyre life"}],
    "examples": [
        ex("says the tyre will last that long", "fail", [surv],
           "The soft tyre will last 18 laps in 2024 [card survival:2024:SOFT]."),
        ex("calls it a lower bound", "pass", [surv],
           "Half the 2024 soft stints were still alive at 18 laps [card survival:2024:SOFT]. Most of them ended in a pit stop first, so read it as a lower bound on tyre life, not the tyre's limit."),
        ex("a non-survival card from the same page does not fire it", "not_fired",
           [card(id="c1", metric="stints_n", label="computed", value=60, n=60, n_unit="stints", source_page="app/tyre-cliff-survival")],
           "The page has 60 soft stints for 2024 [card c1]."),
    ],
})

ghost = card(id="ghost_standings:2021:NOR", metric="ghost_points", label="modelled", value=312, n=22, n_unit="races",
             source_page="app/ghost-race-standings")
rules.append({
    "code": "GHOST_IS_COUNTERFACTUAL",
    "kind": "known_gap",
    "status": "active",
    "applies_to": {"pages": ["/app/ghost-race-standings", "/app/counterfactual-championship", "/app/hidden-performance"],
                   "metrics": ["ghost finish positions, ghost points and transplanted-car standings"]},
    "condition": "A card comes from a ghost or counterfactual page. Those are statistical, expected-value reconstructions of equal-car pace, not simulations of the race.",
    "triggers": [{"card": [{"field": "source_page", "op": "matches", "value": "ghost-race-standings|counterfactual-championship|hidden-performance"}]}],
    "required_wording": {
        "description": "Say it is a statistical, expected-value reconstruction, not a simulation.",
        "all_of": [
            ["\\bstatistical\\b", "\\bexpected[- ]value\\b"],
            ["\\bnot a (physics |race )?simulation\\b", "\\bnot (a )?simulat(ed|ion)\\b"],
        ],
    },
    "forbidden_claim": {
        "description": "Say the driver would have won, or that the reconstruction proves anything.",
        "patterns": [
            "\\bwould have (won|beaten|taken|finished)\\b",
            "(?<!not )(?<!n't )\\bprov(e|es|ed|ing)\\b",
        ],
    },
    "sources": [
        {"file": "docs/app/ghost-race-standings.mdx", "line": 21, "quote": "This is a statistical reconstruction of equal-car pace, not a physics simulation"},
        {"file": "docs/app/counterfactual-championship.mdx", "line": 31, "quote": "expected-value** reconstruction, not a simulation"},
    ],
    "examples": [
        ex("says the driver would have won", "fail", [ghost],
           "In an equal car Norris would have won the 2021 title with 312 points [card ghost_standings:2021:NOR]; that proves the car held him back."),
        ex("calls it a statistical reconstruction, not a simulation", "pass", [ghost],
           "In the equal-car standings Norris scores 312 points for 2021 [card ghost_standings:2021:NOR]. That is a statistical, expected-value reconstruction of pace, not a simulation of the races."),
        ex("a card from another page does not fire it", "not_fired",
           [card(id="c1", metric="stint_length_laps", label="measured", n=40, n_unit="stints", source_page="app/pit-strategy")],
           "The stint lasted 22 laps [card c1]."),
    ],
})

sk1 = card(id="race_skill:2024_8:LEC", metric="rating_s", label="computed", value=-0.12, n=40, n_unit="laps", skill_measure="teammate_paired_median")
sk2 = card(id="era_rating.season:2024:LEC", metric="era_adjusted_rating", label="modelled", value=0.31, n=24, n_unit="races",
           skill_measure="era_rating", interval={"low": 0.1, "high": 0.5, "kind": "ci_normal_95"})
rules.append({
    "code": "ONE_SKILL_MEASURE",
    "kind": "known_gap",
    "status": "active",
    "applies_to": {"pages": [], "metrics": ["cards that carry policy_fields.skill_measure (waterfall residual, consistency residual, wet-race proxy, LORO race skill, era-normalised rating, corner / synthetic / qualifying proxies)"]},
    "condition": "An answer uses cards from two or more different 'skill' measures. Their ranks can disagree; they are different measures, not one scale.",
    "triggers": [{"cards_distinct_values": {"field": "skill_measure", "min": 2}}],
    "required_wording": {
        "description": "Name each measure and say they are different measures, not one scale.",
        "all_of": [
            ["\\bdifferent (skill )?(measures|definitions|metrics)\\b", "\\bnot the same (measure|scale|definition)\\b", "\\bseparate (skill )?measures\\b", "\\bnot (on )?(one|a single|the same) scale\\b"],
            ["\\b(LORO|leave-one-race-out|race[- ]skill|teammate[- ]paired|race rating)\\b", "\\bera[- ](normali[sz]ed|adjusted)\\b", "\\b(waterfall|consistency) residual\\b", "\\bwet[- ]race\\b", "\\b(corner|synthetic|qualifying) (skill|proxy|teammate)\\b"],
        ],
    },
    "forbidden_claim": {
        "description": "Rank or combine the measures as if they were one scale.",
        "patterns": [
            "(?<!not )\\bon (one|a single|the same) scale\\b",
            "\\b(overall|combined|aggregate) (skill )?(rank|ranking|score)\\b",
            "\\b(both|all) (measures|ratings) (agree|say|show) (he|she|they) (is|are) (the )?(best|better)\\b",
        ],
    },
    "sources": [{"file": "_roadmap/_ai-integration/_evidence/ax-audit-2026-11-07/audit-app.md", "line": 166, "quote": "Ranking drivers across different \"skill\" measures."}],
    "examples": [
        ex("ranks two skill measures as one scale", "fail", [sk1, sk2],
           "Leclerc's overall skill ranking is high: -0.12 s at Monaco and 0.31 s for the season [card race_skill:2024_8:LEC] [card era_rating.season:2024:LEC]."),
        ex("names both measures and says they differ", "pass", [sk1, sk2],
           "Leclerc's LORO race skill at Monaco 2024 was -0.12 s [card race_skill:2024_8:LEC], and his era-adjusted rating for 2024 was 0.31 s (95% CI 0.10 to 0.50 s) [card era_rating.season:2024:LEC]. These are different measures, not one scale, so their ranks need not agree."),
        ex("two cards on the same measure do not fire it", "not_fired",
           [sk1, {**sk1, "id": "race_skill:2024_9:LEC", "value": -0.05}],
           "Leclerc's LORO race skill was -0.12 s at Monaco and -0.05 s at Canada."),
    ],
})

with open(PATH, encoding="utf-8") as f:
    text = f.read()
policy = json.loads(text)
mine = {r["code"] for r in rules}
policy["rules"] = [r for r in policy["rules"] if r["code"] not in mine]  # idempotent re-run: replace ours only
new = rules
policy["kinds"].setdefault("computed_not_card", "A query-builder result: a plain aggregate over published observed rows, not a fact card (AD3).")
policy["kinds"].setdefault("held_card", "A card whose figure is held until wake calibration, the ML redo or a re-measure lands.")
policy["rules"].extend(new)
policy["updated"] = "2026-11-08"
with open(PATH, "w", encoding="utf-8") as f:
    f.write(json.dumps(policy, indent=2, ensure_ascii=False) + "\n")
print("added", [r["code"] for r in new], "total", len(policy["rules"]))
