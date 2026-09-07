# Module 08 — CLI Tools with argparse

> **Goal:** Build command-line tools with proper argument parsing — the interface every script in this repo uses.

---

## 1. Concept: Basic argparse

```python
import argparse

def main():
    parser = argparse.ArgumentParser(description="My tool")
    parser.add_argument("--name", type=str, required=True, help="Your name")
    parser.add_argument("--count", type=int, default=1, help="Number of greetings")
    args = parser.parse_args()
    
    for _ in range(args.count):
        print(f"Hello, {args.name}!")

if __name__ == "__main__":
    main()
```

```bash
python tool.py --name Justin --count 3
# Hello, Justin!
# Hello, Justin!
# Hello, Justin!
```

---

## 2. Concept: Argument types

```python
parser = argparse.ArgumentParser()

# Positional argument (no --)
parser.add_argument("filename", help="Input file")

# Optional with short form
parser.add_argument("-s", "--season", type=int)

# Boolean flags
parser.add_argument("--force", action="store_true")     # --force → True, absent → False
parser.add_argument("--no-cache", action="store_true")

# Choices
parser.add_argument("--session", choices=["R", "Q", "both"], default="both")

# List of values
parser.add_argument("--years", type=int, nargs="+", help="One or more years")
```

### Codebase connection

The ingestion CLI uses all of these:

```python
# ingestion/src/ingest.py (lines 631-673)
p.add_argument("-s", "--season", type=int, metavar="YEAR")
p.add_argument("--session", dest="sessions", choices=["R", "Q", "both"], default="both")
p.add_argument("--skip-telemetry", action="store_true")
p.add_argument("--force", action="store_true")
p.add_argument("--dry-run", action="store_true")
```

---

## 3. Concept: Mutually exclusive groups

Sometimes arguments conflict — you can't use both at once.

```python
parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--start-season", type=int)    # can't use with --season
group.add_argument("-s", "--season", type=int)     # can't use with --start-season
```

### Codebase connection

```python
# ingestion/src/ingest.py (lines 633-641)
season_group = p.add_mutually_exclusive_group(required=True)
season_group.add_argument("--start-season", type=int, metavar="YEAR")
season_group.add_argument("-s", "--season", type=int, metavar="YEAR")
```

This means you must use either `--season 2024` or `--start-season 2018 --end-season 2024`, but not both.

---

## 4. Concept: Post-parse validation

argparse handles basic validation (types, choices, required). For complex rules, validate after parsing:

```python
args = parser.parse_args()

if args.season is not None:
    start_year = end_year = args.season
else:
    start_year = args.start_season
    end_year = args.end_season or args.start_season

if start_year > end_year:
    parser.error(f"--start-season {start_year} is after --end-season {end_year}")

if args.round is not None and start_year != end_year:
    parser.error("--round requires a single season (use -s/--season)")
```

`parser.error()` prints the error message with usage info and exits with code 2.

### Codebase connection

This is exactly the validation in `ingest.py` lines 684–694.

---

## 5. Concept: Epilog for usage examples

```python
parser = argparse.ArgumentParser(
    description="My tool",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""\
Examples:
  python tool.py --season 2024 --session R
  python tool.py --start-season 2018 --end-season 2024
  python tool.py --season 2024 --force --dry-run
    """,
)
```

`RawDescriptionHelpFormatter` preserves whitespace in the epilog. Without it, argparse collapses your examples into a single paragraph.

---

## 6. Concept: The `dest` trick

```python
parser.add_argument("--session", dest="sessions", choices=["R", "Q", "both"])
# args.sessions (not args.session) — renames the attribute
```

This is useful when the CLI flag name doesn't match the variable name you want internally.

---

## 7. Guided exercises

### Exercise 1: Build an ingestion CLI

```python
import argparse

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="F1 data ingestion tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python ingest.py --season 2024 --session R
  python ingest.py --start-season 2018 --end-season 2024 --session both
  python ingest.py --season 2024 --round 1 --force
        """,
    )
    
    # YOUR CODE: Add a mutually exclusive group for --season vs --start-season
    # YOUR CODE: Add --end-season (used with --start-season)
    # YOUR CODE: Add --round (single round, int, optional)
    # YOUR CODE: Add --session (choices: R, Q, both; default: both)
    # YOUR CODE: Add --force (boolean flag)
    # YOUR CODE: Add --dry-run (boolean flag)
    
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    
    # Resolve season range
    if args.season is not None:
        start, end = args.season, args.season
    else:
        start = args.start_season
        end = args.end_season or args.start_season
    
    # Validate
    if start > end:
        parser.error(f"--start-season {start} > --end-season {end}")
    
    if args.round and start != end:
        parser.error("--round requires a single season")
    
    # Show what would happen
    print(f"Seasons: {start}–{end}")
    print(f"Session: {args.session}")
    print(f"Force: {args.force}")
    print(f"Dry run: {args.dry_run}")
    if args.round:
        print(f"Round: {args.round}")


if __name__ == "__main__":
    main()
```

Test it:

```bash
python ingest.py --season 2024 --session R
python ingest.py --season 2024 --round 1 --force
python ingest.py --start-season 2018 --end-season 2024 --session both --dry-run
python ingest.py --season 2024 --start-season 2018  # should error: mutually exclusive
```

### Exercise 2: Build an ML training CLI

```python
import argparse

TARGETS = ["degradation_p10", "degradation_p50", "degradation_p90", "cliff_classifier", "stint_life"]

def build_parser():
    p = argparse.ArgumentParser(description="ML model training")
    p.add_argument("--target", choices=TARGETS, help="Single target to train")
    p.add_argument("--all", action="store_true", help="Train all targets")
    p.add_argument("--version", default="v1", help="Model version")
    p.add_argument("--smoke", action="store_true", help="Fast smoke test (small params)")
    p.add_argument("--params", type=str, help="Path to best_params.json")
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    
    # Resolve targets
    targets = TARGETS if args.all else ([args.target] if args.target else None)
    if not targets:
        parser.error("pass --target <name> or --all")
    
    version = "smoke" if args.smoke else args.version
    
    for t in targets:
        print(f"Training {t} (version={version})")

if __name__ == "__main__":
    main()
```

---

## 8. Interview drills

**Q1:** Why use argparse instead of just reading `sys.argv`?

> **A:** argparse provides: type conversion, validation, help text generation, error messages, default values, mutually exclusive groups, and auto-generated `--help`. Reading `sys.argv` manually requires reimplementing all of this. argparse also prevents common bugs like forgetting to convert `sys.argv[1]` from string to int.

**Q2:** What does `parser.error()` do?

> **A:** It prints the error message alongside the usage string, then exits with code 2 (the Unix convention for command-line usage errors). It's better than `sys.exit(1)` because it includes context about valid arguments.

**Q3:** Why use `action="store_true"` for boolean flags?

> **A:** `store_true` means the flag is `False` by default and becomes `True` when present. The user writes `--force` (no value needed), not `--force True`. This is the standard CLI convention for flags.

**Q4:** What's the purpose of `metavar` in `add_argument`?

> **A:** `metavar` changes the placeholder text in help messages. Without it, `--season SEASON` is shown. With `metavar="YEAR"`, it shows `--season YEAR`, which is more descriptive. It doesn't affect parsing.

---

## 9. Checkpoint

You should now be able to:

- [ ] Build a CLI with argparse (positional, optional, boolean args)
- [ ] Use mutually exclusive groups for conflicting arguments
- [ ] Add post-parse validation with `parser.error()`
- [ ] Write usage examples with `epilog` and `RawDescriptionHelpFormatter`
- [ ] Explain the `--all` vs `--target` pattern used in the ML layer
