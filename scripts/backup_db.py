import os
import shutil
from datetime import datetime


def main() -> None:
  db_path = "mezahub.db"
  if not os.path.exists(db_path):
    print("No local SQLite db to back up.")
    return
  ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
  dest = f"backups/mezahub-{ts}.db"
  os.makedirs(os.path.dirname(dest), exist_ok=True)
  shutil.copy2(db_path, dest)
  print(f"Backup created at {dest}")


if __name__ == "__main__":
  main()
