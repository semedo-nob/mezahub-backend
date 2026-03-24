#!/usr/bin/env python
import psycopg2
import redis
from datetime import datetime


def test_postgresql() -> bool:
    print("\nPostgreSQL Connection:")
    print("-" * 40)

    conn_params = {
        "host": "localhost",
        "port": 5433,
        "dbname": "mezahub",
        "user": "postgres",
        "password": "nelson1504",
        "connect_timeout": 5,
    }

    try:
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"✅ Connected to PostgreSQL")
        print(f"   Version: {version[:60]}...")
        cur.close()
        conn.close()
        return True
    except Exception as exc:
        print(f"❌ PostgreSQL connection failed: {exc}")
        return False


def test_redis() -> bool:
    print("\nRedis Connection:")
    print("-" * 40)
    try:
        r0 = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=True,
            socket_connect_timeout=2,
        )
        r0.ping()
        info = r0.info()
        print(f"✅ Connected to Redis (v{info.get('redis_version')})")
        r0.set("mezahub:test", f"Connected at {datetime.now()}", ex=10)
        print(f"   Test value: {r0.get('mezahub:test')}")
        return True
    except Exception as exc:
        print(f"❌ Redis connection failed: {exc}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("TESTING MEZAHUB DATABASE CONNECTIONS")
    print("=" * 60)

    pg_ok = test_postgresql()
    redis_ok = test_redis()

    print("\n" + "=" * 60)
    if pg_ok and redis_ok:
        print("✅ ALL CONNECTIONS SUCCESSFUL!")
    else:
        print("⚠️ Some connections failed")
    print("=" * 60 + "\n")

