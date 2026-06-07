import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "data" / "calendar.db"


def get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def create_tables() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY,
            skill_level TEXT DEFAULT 'intermediate',
            max_cook_time_minutes INTEGER DEFAULT 60,
            weekly_budget REAL,
            dietary_restrictions TEXT DEFAULT '[]',
            food_allergies TEXT DEFAULT '',
            meal_style TEXT DEFAULT 'simple',
            meals_per_day INTEGER DEFAULT 3,
            height_cm REAL,
            weight_kg REAL,
            age INTEGER,
            sex TEXT,
            activity_level TEXT DEFAULT 'moderately_active',
            body_fat_pct REAL,
            goal TEXT DEFAULT 'maintain',
            tdee_calculated INTEGER,
            calorie_target INTEGER,
            protein_target_g INTEGER,
            carbs_target_g INTEGER,
            fat_target_g INTEGER,
            theme TEXT DEFAULT 'dark'
        );

        CREATE TABLE IF NOT EXISTS meal_preps (
            id INTEGER PRIMARY KEY,
            recipe_name TEXT NOT NULL,
            brief_description TEXT,
            total_servings INTEGER NOT NULL,
            servings_remaining INTEGER NOT NULL,
            prep_date TEXT NOT NULL,
            calories_per_serving REAL,
            protein_g_per_serving REAL,
            carbs_g_per_serving REAL,
            fat_g_per_serving REAL
        );

        CREATE TABLE IF NOT EXISTS meal_days (
            id INTEGER PRIMARY KEY,
            date TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'planned',
            confirmed_at TEXT,
            skipped_at TEXT
        );

        CREATE TABLE IF NOT EXISTS day_meals (
            id INTEGER PRIMARY KEY,
            day_id INTEGER REFERENCES meal_days(id) ON DELETE CASCADE,
            meal_number INTEGER NOT NULL,
            recipe_name TEXT NOT NULL,
            cook_time_minutes INTEGER,
            estimated_cost REAL,
            brief_description TEXT,
            instructions TEXT,
            calories_est REAL,
            protein_g_est REAL,
            carbs_g_est REAL,
            fat_g_est REAL,
            eaten INTEGER DEFAULT 0,
            skipped INTEGER DEFAULT 0,
            prep_id INTEGER REFERENCES meal_preps(id)
        );

        CREATE TABLE IF NOT EXISTS meal_ingredients (
            id INTEGER PRIMARY KEY,
            meal_id INTEGER REFERENCES day_meals(id) ON DELETE CASCADE,
            item TEXT NOT NULL,
            quantity TEXT,
            unit TEXT,
            quantity_type TEXT
        );

        CREATE TABLE IF NOT EXISTS grocery_overrides (
            item TEXT PRIMARY KEY,
            ignored INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS weight_log (
            id INTEGER PRIMARY KEY,
            date TEXT UNIQUE NOT NULL,
            weight_kg REAL NOT NULL,
            notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_meal_days_date ON meal_days(date);
        CREATE INDEX IF NOT EXISTS idx_day_meals_day_id ON day_meals(day_id);
        CREATE INDEX IF NOT EXISTS idx_meal_ingredients_meal_id ON meal_ingredients(meal_id);
        CREATE INDEX IF NOT EXISTS idx_weight_log_date ON weight_log(date);
    """)

    # Lightweight migrations for existing DBs (CREATE TABLE IF NOT EXISTS won't
    # add new columns to a table that already exists).
    _add_column_if_missing(conn, "day_meals", "instructions", "TEXT")

    conn.commit()
    conn.close()


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
