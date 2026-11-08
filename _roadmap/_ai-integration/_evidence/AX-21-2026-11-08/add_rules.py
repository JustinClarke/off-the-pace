"""AX-21: add the playbook conclusion rules to policy.json and make the THIN_SAMPLE trigger skip
held and unavailable cards. Loads the file at run time (other lanes edit it), verifies a byte-exact
JSON round trip, drops only this item's codes, appends them, and rewrites with indent=2.
Idempotent: re-running yields the same file. Run from the repo root:
    python3 _roadmap/_ai-integration/_evidence/AX-21-2026-11-08/add_rules.py
"""
import json
import sys

PATH = "app/src/assistant/honesty/policy.json"

TEAMMATE_NAMES = [
    "\\bteammate[- ]paired\\b",
    "\\bpaired[- ]laps?\\b",
    "\\bmedian (lap[- ]time )?gap\\b",
    "\\bera[- ](rating|adjusted|normali[sz]ed)\\b",
    "\\bLORO\\b",
    "\\brace[- ]skill\\b",
    "\\b(lap|waterfall|consistency) residual\\b",
    "\\bwet[- ]race (proxy|skill)\\b",
    "\\bcorner[- ](skill|phase)\\b",
    "\\bsynthetic[- ]teammate\\b",
    "\\bqualifying[- ]decomposed\\b",
]


def gap_card(cid, value, n, trust, low=None, high=None, label="computed"):
    c = {
        "id": cid,
        "kind": "race.teammate_gap",
        "metric": "teammate_gap_s",
        "label": label,
        "value": value,
        "unit": "s",
        "n": n,
        "n_unit": "laps",
        "rating_trust_label": trust,
        "skill_measure": "teammate_paired_median",
        "shared_input_group": "race_rating",
    }
    if low is not None:
        c["interval"] = {"low": low, "high": high, "kind": "ci_order_stat_median"}
    return c


THIN = gap_card("race.teammate_gap:2019_1:NOR", -0.472, 8, "thin", -0.926, 0.336)
SUPP = gap_card("race.teammate_gap:2020_14:HAM", None, 0, "suppressed", label="unavailable")
SUPP["unavailable_reason"] = "rated on 1 paired lap (fewer than 6): suppressed, no value"
OK = gap_card("race.teammate_gap:2024_1:VER", -0.622, 46, "ok", -0.755, -0.39)

SEASON = {
    "id": "season.teammate_gap:2023:NOR",
    "kind": "season.teammate_gap",
    "metric": "season_teammate_gap_s",
    "label": "computed",
    "value": -0.15,
    "unit": "s",
    "n": 22,
    "n_unit": "races",
    "interval": {"low": -0.25, "high": -0.05, "kind": "ci_normal_95"},
    "rank": 3,
    "rank_separated_from_next": False,
    "skill_measure": "teammate_paired_median",
    "shared_input_group": "race_rating",
    "scope": {"season": 2023, "driver_id": "NOR"},
}
SEASON_SEP = dict(SEASON, id="season.teammate_gap:2023:VER", rank=1, rank_separated_from_next=True, value=-0.6,
                  interval={"low": -0.8, "high": -0.4, "kind": "ci_normal_95"}, scope={"season": 2023, "driver_id": "VER"})

POOLED = {
    "id": "race_control.pooled_rate:sc",
    "kind": "race_control.pooled_rate",
    "metric": "sc_onset_rate_per_race",
    "label": "computed",
    "value": 0.43,
    "n": 173,
    "n_unit": "races",
    "interval": {"low": 0.36, "high": 0.5, "kind": "wilson_95"},
    "source_page": "race-control",
}
CAUTIONS = {
    "id": "race.cautions:2020_14",
    "kind": "race.cautions",
    "metric": "caution_laps",
    "label": "measured",
    "value": 4,
    "unit": "laps",
    "n": 58,
    "n_unit": "laps",
    "source_page": "race-control",
}
ERA = {
    "id": "era_rating.season:2024:LEC",
    "kind": "era_rating.season",
    "metric": "era_adjusted_rating",
    "label": "modelled",
    "value": 0.31,
    "unit": "s",
    "n": 24,
    "n_unit": "races",
    "interval": {"low": 0.1, "high": 0.5, "kind": "ci_normal_95"},
    "skill_measure": "era_rating",
    "shared_input_group": "race_rating",
}
ERA23 = dict(ERA, id="era_rating.season:2023:LEC", value=0.22, interval={"low": 0.02, "high": 0.42, "kind": "ci_normal_95"})
AFFINITY = {
    "id": "driver_circuit_affinity.circuit:2024:LEC:monaco",
    "kind": "driver_circuit_affinity.circuit",
    "metric": "affinity_deviation_s",
    "label": "modelled",
    "value": 0.4,
    "unit": "s",
    "n": 6,
    "n_unit": "races",
    "shared_input_group": "race_rating",
}
QRESULT = {
    "id": "q7c1d2e3f4a5b",
    "metric": "qv_laps.lap_time_s",
    "label": "computed_not_card",
    "aggregate_fn": "count",
    "n": 4,
    "n_unit": "rows",
    "source_page": "qv_laps",
}
NOSKILL = {"id": "race.result:2024_1:VER", "kind": "race.result", "metric": "finish_position", "label": "measured",
           "value": 1, "n": 1, "n_unit": "races"}


def ex(name, expect, cards, answer, question=None):
    inp = {"cards": cards, "answer": answer}
    if question:
        inp = {"question": question, **inp}
    return {"name": name, "expect": expect, "input": inp}


RULES = [
    {
        "code": "RATING_TRUST_LABEL",
        "kind": "thin_sample",
        "status": "active",
        "applies_to": {"pages": [], "metrics": ["race.teammate_gap (rating_s, TX-01 trust label in policy_fields.rating_trust_label)"]},
        "condition": "A teammate-gap card is thin (6 to 11 paired laps) or suppressed (fewer than 6: no CI, no value). A thin gap is quoted with a hedge; a suppressed gap has no value at all (AX-21).",
        "triggers": [{"card": [{"field": "rating_trust_label", "op": "in", "value": ["suppressed", "thin"]}]}],
        "required_wording": {
            "description": "Suppressed: say there is no reliable gap. Thin: say it rests on few paired laps and is directional.",
            "all_of": [[
                "\\bno reliable (gap|rating|value|number)\\b",
                "\\bthin\\b",
                "\\b(only|just) \\d+ paired laps?\\b",
                "\\b(few|fewer than \\d+) paired laps\\b",
                "\\bsmall sample\\b",
                "\\btentative\\b",
                "\\bdirectional\\b",
            ]],
        },
        "forbidden_claim": {
            "description": "State a thin or suppressed gap with certainty.",
            "patterns": ["\\b(clearly|definitely|conclusively|certainly|decisively)\\b", "\\b(dominated|destroyed|thrashed|crushed)\\b"],
        },
        "sources": [{
            "file": "transform/models/marts/schema.yml",
            "line": 2952,
            "quote": "How far to trust rating_s, from paired_lap_count: 'suppressed' when n < 6 (too few",
        }],
        "examples": [
            ex("states a thin gap with certainty", "fail", [THIN],
               "Norris clearly beat Sainz by 0.472 s per lap in race 2019_1 [card race.teammate_gap:2019_1:NOR]."),
            ex("quotes a suppressed rating as a number", "fail", [SUPP],
               "Hamilton was definitely 6.6 s per lap quicker than Bottas in race 2020_14 [card race.teammate_gap:2020_14:HAM]."),
            ex("hedges a thin gap", "pass", [THIN],
               "Norris's median gap to Sainz in race 2019_1 was -0.472 s per lap (95% CI -0.926 to 0.336) [card race.teammate_gap:2019_1:NOR], but it rests on only 8 paired laps, so it is thin: read it as directional."),
            ex("says a suppressed gap has no reliable value", "pass", [SUPP],
               "There is no reliable gap for Hamilton against Bottas in race 2020_14: there is no value, because he was rated on only 1 paired lap [card race.teammate_gap:2020_14:HAM]."),
            ex("an ok gap does not fire it", "not_fired", [OK],
               "Verstappen's median gap to Perez on 46 paired laps was -0.622 s per lap [card race.teammate_gap:2024_1:VER]."),
        ],
    },
    {
        "code": "RANK_WITHIN_CI",
        "kind": "low_confidence",
        "status": "active",
        "applies_to": {"pages": [], "metrics": ["season.teammate_gap rank (TX-06 rank_separated_from_next in policy_fields)"]},
        "condition": "A season card's rank is not separated from the next driver's by the CI (rank_separated_from_next false). Adjacent ranks are almost never separated.",
        "triggers": [{"card": [{"field": "rank_separated_from_next", "op": "eq", "value": False}]}],
        "required_wording": {
            "description": "Say the driver is in a group whose intervals overlap, not at a clear place.",
            "all_of": [[
                "\\b(intervals?|CIs?|confidence intervals?|ranges?) overlap\\b",
                "\\bnot (clearly |reliably )?separated\\b",
                "\\bcannot be (separated|ranked|told apart)\\b",
                "\\bin a group\\b",
            ]],
        },
        "forbidden_claim": {
            "description": "An ordinal claim (ranked 3rd, second-best, top of the field) for an unseparated rank.",
            "patterns": [
                "(?<!not )\\brank(ed|s)? (\\d+(st|nd|rd|th)|first|second|third|fourth|fifth|top|highest|lowest)\\b",
                "\\b(\\d+(st|nd|rd|th)|first|second|third|fourth|fifth)[- ](best|fastest|quickest|placed)\\b",
                "\\b(is|was) (the )?(\\d+(st|nd|rd|th)|first|second|third|fourth|fifth) (best|fastest|quickest|strongest)\\b",
                "\\b(top|best) (of|in) the (season|field|grid|year)\\b",
            ],
        },
        "sources": [{
            "file": "transform/models/marts/schema.yml",
            "line": 2633,
            "quote": "so quote a rank only with the CI; rank_separated_from_next says when it",
        }],
        "examples": [
            ex("gives an unseparated rank as a place", "fail", [SEASON],
               "Norris ranked 3rd against his teammate in 2023, with a median gap of -0.15 s per lap [card season.teammate_gap:2023:NOR]."),
            ex("places the driver in an overlapping group", "pass", [SEASON],
               "Norris's 2023 season median gap to his teammate was -0.15 s per lap (95% CI -0.25 to -0.05) [card season.teammate_gap:2023:NOR]. His interval overlaps the next driver's, so he sits in a group whose intervals overlap rather than at a clear place."),
            ex("a separated rank does not fire it", "not_fired", [SEASON_SEP],
               "Verstappen's 2023 season median gap to his teammate was -0.6 s per lap (95% CI -0.8 to -0.4) [card season.teammate_gap:2023:VER]."),
        ],
    },
    {
        "code": "POOLED_SC_RATE_ONLY",
        "kind": "known_gap",
        "status": "active",
        "applies_to": {"pages": ["/race-craft/race-control"], "metrics": ["race_control.pooled_rate (Wilson rate per race or per lap)"]},
        "condition": "A caution rate from Race Control. The between-circuit share is 0.000, so only the pooled rate exists; no circuit has its own safety-car probability. race.cautions (a per-race lap count) shares the page but carries no rate and does not fire this.",
        "triggers": [
            {"card": [{"field": "kind", "op": "eq", "value": "race_control.pooled_rate"}]},
            {"card": [{"field": "source_page", "op": "matches", "value": "race-control"},
                      {"field": "metric", "op": "matches", "value": "rate|probab|hazard|per_lap|per_race"}]},
        ],
        "required_wording": {
            "description": "Say the rate is pooled across circuits and that the data shows no reliable difference between circuits.",
            "all_of": [
                ["\\bpooled\\b", "\\bacross (all|every) (circuits|races|tracks|seasons)\\b"],
                ["\\bno (reliable |measurable |detectable )?difference between (circuits|tracks|venues)\\b",
                 "\\b(circuits|tracks) (do not|don't) (reliably )?differ\\b",
                 "\\bnot (a )?(per|single)[- ](circuit|track)\\b",
                 "\\bindistinguishable\\b"],
            ],
        },
        "forbidden_claim": {
            "description": "Give one circuit its own safety-car probability or call a circuit more or less prone to them.",
            "patterns": [
                "\\b(chance|probability|likelihood|odds|risk) of an? (safety[- ]car|SC|VSC|caution)\\b[^.]{0,30}\\b(at|in) (?!all\\b|any\\b|every\\b|each\\b|a\\b|the field\\b)\\w+",
                "\\b(at|in) (?!all\\b|any\\b|every\\b|each\\b|a\\b|the\\b)\\w+[^.]{0,25}\\b(chance|probability|likelihood|odds|risk) of an? (safety[- ]car|SC|VSC)\\b",
                "\\b(safety[- ]car|SC|VSC|caution) (probability|chance|odds|risk|rate) (at|for|in) (?!all\\b|any\\b|every\\b|each\\b|a\\b)\\w+",
                "\\b(more|less) (likely|prone) to (bring out|have|see|produce|get) (a )?(safety[- ]cars?|SCs?|VSCs?|cautions?)\\b",
                "\\bsafety[- ]car (magnet|hotspot)\\b",
            ],
        },
        "sources": [
            {"file": "docs/app/race-control.mdx", "line": 42, "quote": "So the only caution probability shown is **pooled** across every circuit and season"},
            {"file": "docs/app/race-control.mdx", "line": 35, "quote": "puts the between-circuit share at **0.000** for any caution"},
        ],
        "examples": [
            ex("gives Monaco its own safety-car chance", "fail", [POOLED],
               "At Monaco there is a 60% chance of a safety car [card race_control.pooled_rate:sc]."),
            ex("quotes the pooled rate and says circuits do not differ", "pass", [POOLED],
               "Across every circuit and season the pooled rate is 0.43 safety-car periods per race (95% CI 0.36 to 0.50, 173 races) [card race_control.pooled_rate:sc]. The data shows no reliable difference between circuits, so I cannot give Monaco a figure of its own."),
            ex("a per-race caution lap count does not fire it", "not_fired", [CAUTIONS],
               "Race 2020_14 had 4 laps under caution, all under the VSC [card race.cautions:2020_14]."),
        ],
    },
    {
        "code": "NOT_INDEPENDENT_EVIDENCE",
        "kind": "known_gap",
        "status": "active",
        "applies_to": {"pages": ["/drivers/circuit-affinity", "/drivers/ratings-timeline", "/drivers/era-translator", "/ghost-car/standings", "/constructors/structural", "/constructors/team-averages", "/tyre-strategy/party-mode"],
                       "metrics": ["cards sharing policy_fields.shared_input_group race_rating or constructor_pace"]},
        "condition": "Two or more different card kinds from one shared-input group are used together: affinity, era ratings and ghost standings share the race-grain rating; Team Averages' car term, Structural Pace and Party Mode share the car-pace laps. They are not separate confirmations.",
        "triggers": [
            {"cards_distinct_values": {"field": "kind", "min": 2, "where": {"field": "shared_input_group", "eq": "race_rating"}}},
            {"cards_distinct_values": {"field": "kind", "min": 2, "where": {"field": "shared_input_group", "eq": "constructor_pace"}}},
        ],
        "required_wording": {
            "description": "Say the figures share their inputs and are not independent evidence.",
            "all_of": [[
                "\\bnot independent\\b",
                "\\bshare (the same |their )?(inputs?|data|laps|rating)\\b",
                "\\b(built|based) on the same\\b",
                "\\bsame (underlying )?(laps|data|rating|inputs?)\\b",
                "\\bnot (two|three|separate) (confirmations|checks)\\b",
            ]],
        },
        "forbidden_claim": {
            "description": "Count them as separate confirmations.",
            "patterns": [
                "(?<!not )(?<!not as )(?<!not an )\\b(independent|separate) (confirmations?|evidence|checks?|lines of evidence)\\b",
                "\\b(both|all three|two|three) (pages|measures|sources|numbers|ratings) (confirm|corroborate|independently)\\b",
                "\\bconfirm(s|ed)? each other\\b",
                "\\bindependently (confirm|corroborate|support)s?\\b",
            ],
        },
        "sources": [
            {"file": "docs/app/driver-circuit-affinity.mdx", "line": 35, "quote": "Affinity and the era ratings share the same race-grain rating; do not stack them as if independent."},
            {"file": "_roadmap/_ai-integration/_evidence/ax-audit-2026-11-07/audit-app.md", "line": 176, "quote": "Team Averages `constructor_component_s` against the Structural Pace panel FE."},
        ],
        "examples": [
            ex("stacks affinity on the era rating", "fail", [ERA, AFFINITY],
               "Leclerc's era rating of 0.31 s [card era_rating.season:2024:LEC] and his Monaco affinity of +0.40 s [card driver_circuit_affinity.circuit:2024:LEC:monaco] are two independent confirmations that he excels there."),
            ex("says they share the race-grain rating", "pass", [ERA, AFFINITY],
               "Leclerc's 2024 era rating is 0.31 s (95% CI 0.10 to 0.50) [card era_rating.season:2024:LEC] and his Monaco affinity is +0.40 s [card driver_circuit_affinity.circuit:2024:LEC:monaco]. They share the same race-grain rating, so they are not independent: read them as one signal."),
            ex("one kind across two seasons does not fire it", "not_fired", [ERA, ERA23],
               "Leclerc's era rating was 0.22 s in 2023 and 0.31 s in 2024 [card era_rating.season:2023:LEC] [card era_rating.season:2024:LEC]."),
        ],
    },
    {
        "code": "COUNT_NOT_CAUSE",
        "kind": "known_gap",
        "status": "active",
        "applies_to": {"pages": [], "metrics": ["query_data results (computed_not_card, n_unit rows)", "context cards: race.cautions, driver_race.pit_stops, race.coverage, data_quality.race"]},
        "condition": "The answer uses a count, a query result or a context card. In v1 no live card is a time-loss breakdown, so a count can be consistent with a gap but never explains it (AX-21).",
        "triggers": [
            {"card": [{"field": "label", "op": "eq", "value": "computed_not_card"}]},
            {"card": [{"field": "n_unit", "op": "eq", "value": "rows"}]},
            {"card": [{"field": "kind", "op": "in", "value": ["race.cautions", "driver_race.pit_stops", "race.coverage", "data_quality.race"]}]},
        ],
        "required_wording": {"description": "None. The rule forbids causal wording; 'consistent with' is the allowed form.", "all_of": []},
        "forbidden_claim": {
            "description": "Give the count as the cause of a gap or a result.",
            "patterns": [
                "\\bbecause of\\b",
                "\\bcaused by\\b",
                "\\bdue to\\b",
                "\\b(cost|lost) (him|her|them) (the race|the win|\\d)",
                "(?<!not )(?<!n't )\\bexplains? (the|his|her|their|why)\\b",
            ],
        },
        "sources": [{"file": "_roadmap/_ai-integration/wi/AX-21.md", "line": 20, "quote": "Never \"because\" or \"caused by\" from a count, a `computed_not_card` result, or context cards."}],
        "examples": [
            ex("blames the gap on the caution laps", "fail", [OK, CAUTIONS],
               "Verstappen's -0.622 s per lap median gap to Perez on 46 paired laps [card race.teammate_gap:2024_1:VER] was caused by the 4 VSC laps [card race.cautions:2020_14]."),
            ex("calls a query count the reason", "fail", [QRESULT],
               "He finished behind due to the 4 slow laps, a plain count computed from the lap data [result q7c1d2e3f4a5b]."),
            ex("reports the count as context only", "pass", [CAUTIONS],
               "Race 2020_14 had 4 laps under caution [card race.cautions:2020_14]. That is context: a count does not split lap time into causes."),
            ex("a card without counts does not fire it", "not_fired", [NOSKILL],
               "Verstappen won from pole [card race.result:2024_1:VER]."),
        ],
    },
    {
        "code": "ONE_SKILL_MEASURE_NAMED",
        "kind": "known_gap",
        "status": "active",
        "applies_to": {"pages": [], "metrics": ["any card carrying policy_fields.skill_measure (AX-21 glossary)"]},
        "condition": "The single-card case of ONE_SKILL_MEASURE: any skill card is quoted. At least six 'skill' measures ship and their ranks can disagree, so the answer names the one it quotes. A separate code because ONE_SKILL_MEASURE's wording (\"different measures\") only fits two or more.",
        "triggers": [{"cards_distinct_values": {"field": "skill_measure", "min": 1}}],
        "required_wording": {"description": "Name the measure quoted (teammate-paired median gap, era rating, lap residual, ...).", "all_of": [TEAMMATE_NAMES]},
        "forbidden_claim": {
            "description": "Read a residual as driver error, or a measure as the driver's true skill.",
            "patterns": ["(?<!not )(?<!not a )(?<!n't )\\bdriver errors?\\b", "\\b(his|her|their) (true|real|overall) skill\\b"],
        },
        "sources": [
            {"file": "_roadmap/_ai-integration/_evidence/ax-audit-2026-11-07/audit-app.md", "line": 174, "quote": "An assistant must name which one it quotes."},
            {"file": "_roadmap/_ai-integration/wi/AX-21.md", "line": 80, "quote": "It means \"unexplained\", not \"driver error\"."},
        ],
        "examples": [
            ex("quotes a skill card without naming the measure", "fail", [OK],
               "Verstappen's true skill put him 0.622 s per lap ahead of Perez in race 2024_1 [card race.teammate_gap:2024_1:VER]."),
            ex("names the measure", "pass", [OK],
               "Verstappen's median gap to Perez on 46 paired laps in race 2024_1 was -0.622 s per lap (95% CI -0.755 to -0.390) [card race.teammate_gap:2024_1:VER]."),
            ex("a card with no skill measure does not fire it", "not_fired", [NOSKILL],
               "Verstappen won from pole [card race.result:2024_1:VER]."),
        ],
    },
]

CODES = {r["code"] for r in RULES}
THIN_EXTRA = [{"field": "status", "op": "ne", "value": "held"}, {"field": "label", "op": "ne", "value": "unavailable"}]


def main():
    raw = open(PATH, encoding="utf-8").read()
    pol = json.loads(raw)
    if json.dumps(pol, indent=2, ensure_ascii=False) + "\n" != raw:
        sys.exit("policy.json does not round-trip byte-exact; refusing to write")
    for r in pol["rules"]:
        if r["code"] == "THIN_SAMPLE":
            t = r["triggers"][1]["card"]
            assert t[0]["field"] == "n_unit" and t[1]["field"] == "n", t
            r["triggers"][1]["card"] = t[:2] + THIN_EXTRA
    pol["rules"] = [r for r in pol["rules"] if r["code"] not in CODES] + RULES
    open(PATH, "w", encoding="utf-8").write(json.dumps(pol, indent=2, ensure_ascii=False) + "\n")
    print(len(pol["rules"]), "rules")


if __name__ == "__main__":
    main()
