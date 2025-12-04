"""Test Supabase Postgres connectivity using DATABASE_URL from TrikeGo/.env

Run from PowerShell after activating your virtualenv:

    .\env\Scripts\Activate.ps1
    pip install psycopg2-binary python-dotenv
    python TrikeGo\scripts\test_supabase_connection.py

The script prints a success message on connection or the exception on failure.
"""

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    print("Missing dependency: python-dotenv. Install with: pip install python-dotenv")
    sys.exit(2)

# Load the project's .env file (TrikeGo/.env)
ROOT = Path(__file__).resolve().parents[1]
env_path = ROOT / '.env'
if not env_path.exists():
    env_path = ROOT / 'TrikeGo' / '.env' if (ROOT / 'TrikeGo' / '.env').exists() else None
if env_path is None or not env_path.exists():
    # fallback to current working directory .env
    env_path = Path.cwd() / 'TrikeGo' / '.env'

if not env_path or not env_path.exists():
    print('Could not find TrikeGo/.env. Please ensure your .env is at TrikeGo/.env')
    sys.exit(2)

load_dotenv(str(env_path))

DB_URL = os.environ.get('DATABASE_URL')
if not DB_URL:
    print('No DATABASE_URL found in', env_path)
    sys.exit(2)

try:
    import psycopg2
except Exception:
    print('Missing dependency: psycopg2-binary. Install with: pip install psycopg2-binary')
    sys.exit(2)

print('Testing connection to:', DB_URL.split('@')[-1])
try:
    conn = psycopg2.connect(DB_URL, sslmode='require')
    conn.close()
    print('Supabase connection OK')
    sys.exit(0)
except Exception as exc:
    print('Supabase connection failed:', exc)
    sys.exit(1)
