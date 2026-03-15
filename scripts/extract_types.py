"""
extract_types.py-Extract data types from SQL files and add to schema.yml

Parses CAST expressions in SQL models to infer column types.
Adds data_type to schema.yml columns that are missing it.
"""

import re
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).parent.parent
MODELS_DIR = REPO_ROOT / "transform" / "models"

def extract_casts_from_sql(sql_content: str) -> dict[str, str]:
    """Extract column names and their CAST types from SQL."""
    types = {}

    # Match CAST(expr AS TYPE) AS col_name pattern
    # Also match simpler patterns like (expr) AS col_name where we can infer type
    cast_pattern = r'CAST\s*\(\s*(\w+|\w+\.\w+)\s+AS\s+(\w+(?:\(\d+\))?)\s*\)\s+AS\s+(\w+)'

    for match in re.finditer(cast_pattern, sql_content, re.IGNORECASE):
        col_name = match.group(3)
        cast_type = match.group(2).lower()

        # Normalize DuckDB types to lowercase
        types[col_name] = cast_type

    return types

def load_schema_yml(path: Path) -> dict:
    """Load schema.yml and return parsed content."""
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f) or {}

def save_schema_yml(path: Path, data: dict) -> None:
    """Save schema.yml with nice formatting."""
    with open(path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

def add_types_to_schema(sql_file: Path, schema_file: Path) -> int:
    """Add data_type to schema.yml columns based on SQL types. Returns count of updates."""
    if not schema_file.exists():
        return 0

    sql_content = sql_file.read_text()
    extracted_types = extract_casts_from_sql(sql_content)

    if not extracted_types:
        return 0

    schema = load_schema_yml(schema_file)
    if not schema or 'models' not in schema:
        return 0

    model_name = sql_file.stem
    updated = 0

    for model in schema.get('models', []):
        if model.get('name') == model_name:
            for col in model.get('columns', []):
                col_name = col.get('name')
                if col_name in extracted_types and not col.get('data_type'):
                    col['data_type'] = extracted_types[col_name]
                    updated += 1

    if updated:
        save_schema_yml(schema_file, schema)

    return updated

def main():
    """Process all SQL files and update schema.yml files."""
    total_updated = 0

    # Organize SQL files by schema file
    schema_files = {
        MODELS_DIR / 'staging' / 'schema.yml': MODELS_DIR / 'staging',
        MODELS_DIR / 'intermediate' / 'schema.yml': MODELS_DIR / 'intermediate',
        MODELS_DIR / 'marts' / 'schema.yml': MODELS_DIR / 'marts',
        MODELS_DIR / 'reference' / 'schema.yml': MODELS_DIR / 'reference',
    }

    for schema_file, model_dir in schema_files.items():
        sql_files = sorted(model_dir.glob('*.sql'))

        if not sql_files:
            continue

        print(f"\n[{schema_file.parent.name}]")
        layer_updated = 0

        for sql_file in sql_files:
            updated = add_types_to_schema(sql_file, schema_file)
            if updated:
                print(f"  {sql_file.stem}: +{updated} types")
                layer_updated += updated

        print(f"  Total: {layer_updated} columns updated")
        total_updated += layer_updated

    print(f"\n✓ Updated {total_updated} column type definitions")

if __name__ == '__main__':
    main()
