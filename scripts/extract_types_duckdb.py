"""
extract_types_duckdb.py-Extract actual column types from compiled DuckDB database

Queries the DuckDB information_schema to get the real column types for each model,
then updates schema.yml files with this information.
"""

import duckdb
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "data" / "dev.duckdb"
MODELS_DIR = REPO_ROOT / "transform" / "models"

# Map DuckDB types to normalized names (how they appear in schema.yml)
TYPE_MAPPING = {
    'BIGINT': 'bigint',
    'INTEGER': 'integer',
    'SMALLINT': 'smallint',
    'TINYINT': 'tinyint',
    'HUGEINT': 'hugeint',
    'DOUBLE': 'double',
    'FLOAT': 'float',
    'DECIMAL': 'decimal',
    'BOOLEAN': 'boolean',
    'VARCHAR': 'varchar',
    'CHAR': 'char',
    'TEXT': 'varchar',
    'DATE': 'date',
    'TIME': 'time',
    'TIMESTAMP': 'timestamp',
    'INTERVAL': 'interval',
}

def normalize_type(duckdb_type: str) -> str:
    """Convert DuckDB type to normalized schema.yml format."""
    base_type = duckdb_type.split('(')[0].strip().upper()
    return TYPE_MAPPING.get(base_type, base_type.lower())

def get_model_columns(conn: duckdb.DuckDBPyConnection, schema: str, table: str) -> dict[str, str]:
    """Get column names and types from a table/view."""
    try:
        result = conn.execute(f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = '{schema}' AND table_name = '{table}'
            ORDER BY ordinal_position
        """).fetchall()
        return {col_name: normalize_type(col_type) for col_name, col_type in result}
    except Exception as e:
        return {}

def load_schema_yml(path: Path) -> dict:
    """Load schema.yml."""
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f) or {}

def save_schema_yml(path: Path, data: dict) -> None:
    """Save schema.yml with nice formatting."""
    with open(path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

def update_schema_with_types(schema_file: Path, model_schema: str, types_by_model: dict) -> int:
    """Update schema.yml with types from DuckDB. Returns count of updates."""
    schema = load_schema_yml(schema_file)
    if not schema or 'models' not in schema:
        return 0

    updated = 0
    for model in schema.get('models', []):
        model_name = model.get('name')
        model_types = types_by_model.get(model_name, {})

        if not model_types:
            continue

        for col in model.get('columns', []):
            col_name = col.get('name')
            if col_name in model_types and not col.get('data_type'):
                col['data_type'] = model_types[col_name]
                updated += 1

    if updated:
        save_schema_yml(schema_file, schema)

    return updated

def main():
    """Extract types from DuckDB and update all schema.yml files."""
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found. Run 'make dbt-dev' first.")
        return

    conn = duckdb.connect(str(DB_PATH))

    # Map schema.yml files to their DuckDB schemas
    schema_mappings = {
        MODELS_DIR / 'staging' / 'schema.yml': 'main',
        MODELS_DIR / 'intermediate' / 'schema.yml': 'main',
        MODELS_DIR / 'marts' / 'schema.yml': 'main',
        MODELS_DIR / 'reference' / 'schema.yml': 'main',
    }

    total_updated = 0

    for schema_file, duckdb_schema in schema_mappings.items():
        if not schema_file.exists():
            continue

        schema_yaml = load_schema_yml(schema_file)
        if not schema_yaml:
            continue

        print(f"\n[{schema_file.parent.name}]")
        types_by_model = {}

        # Collect types for all models in this schema file
        for model in schema_yaml.get('models', []):
            model_name = model.get('name')
            model_types = get_model_columns(conn, duckdb_schema, model_name)
            if model_types:
                types_by_model[model_name] = model_types

        # Update schema file
        updated = update_schema_with_types(schema_file, duckdb_schema, types_by_model)
        if updated:
            print(f"  Updated {updated} column types")
            total_updated += updated
        else:
            print(f"  No updates needed")

    conn.close()
    print(f"\n✓ Total: {total_updated} column type definitions added")

if __name__ == '__main__':
    main()
