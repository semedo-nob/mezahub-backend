#!/usr/bin/env python
import os
import psycopg2
from urllib.parse import urlparse

from dotenv import load_dotenv


load_dotenv()

print("DEBUGGING DATABASE CONNECTION")
print("=" * 50)

print("\nEnvironment variables:")
print(f"DB_HOST: {os.getenv('DB_HOST', 'not set')}")
print(f"DB_PORT: {os.getenv('DB_PORT', 'not set')}")
print(f"DB_NAME: {os.getenv('DB_NAME', 'not set')}")
print(f"DB_USER: {os.getenv('DB_USER', 'not set')}")
pwd = os.getenv("DB_PASSWORD")
print(f"DB_PASSWORD: {'*' * len(pwd) if pwd else 'not set'}")
print(f"DATABASE_URL: {os.getenv('DATABASE_URL', 'not set')}")

print("\nTrying different connection methods:")


def try_connect(label: str, **params):
    print(f"\n{label}")
    try:
        conn = psycopg2.connect(**params)
        conn.close()
        print("  ✅ SUCCESS")
    except Exception as exc:
        print(f"  ❌ {exc}")


# Method 1: env vars
try_connect(
    "Method 1 (env vars)",
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5433")),
    dbname=os.getenv("DB_NAME", "mezahub"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "nelson1504"),
)

# Method 2: DATABASE_URL
url = os.getenv("DATABASE_URL")
if url:
    parsed = urlparse(url)
    try_connect(
        "Method 2 (DATABASE_URL)",
        host=parsed.hostname or "localhost",
        port=parsed.port or 5433,
        dbname=(parsed.path or "/mezahub").lstrip("/"),
        user=parsed.username or "postgres",
        password=parsed.password or "nelson1504",
    )
else:
    print("\nMethod 2 (DATABASE_URL): not set")

# Method 3: explicit 127.0.0.1
try_connect(
    "Method 3 (127.0.0.1)",
    host="127.0.0.1",
    port=5433,
    dbname="mezahub",
    user="postgres",
    password="nelson1504",
)

# Method 4: explicit localhost
try_connect(
    "Method 4 (localhost)",
    host="localhost",
    port=5433,
    dbname="mezahub",
    user="postgres",
    password="nelson1504",
)

print("\n" + "=" * 50)

