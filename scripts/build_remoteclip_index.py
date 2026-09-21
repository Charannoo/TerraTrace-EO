from __future__ import annotations

from pathlib import Path

from backend.catalog import Catalog


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    catalog = Catalog(root)
    with catalog.connection() as connection:
        records = [dict(row) for row in connection.execute("SELECT * FROM scenes ORDER BY id").fetchall()]
    print(catalog.remoteclip.build(records))


if __name__ == "__main__":
    main()

