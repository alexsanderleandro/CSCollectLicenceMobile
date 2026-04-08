from __future__ import annotations
import re
from pathlib import Path
from datetime import datetime


def compute_next_version(version_file: Path) -> str:
    today = datetime.utcnow().strftime("%y.%m.%d")
    if not version_file.exists():
        return f"{today} rev. 1"

    text = version_file.read_text(encoding="utf-8")
    m = re.search(r"(?P<date>\d{2}\.\d{2}\.\d{2})\s+rev\.?\s*(?P<rev>\d+)", text)
    if not m:
        return f"{today} rev. 1"

    prev_date = m.group("date")
    prev_rev = int(m.group("rev"))
    if prev_date == today:
        new_rev = prev_rev + 1
    else:
        new_rev = 1

    return f"{today} rev. {new_rev}"


def write_version(version_file: Path, version_str: str) -> None:
    content = "# Gerado por update_version.py\nVERSION = \"{}\"\n".format(version_str)
    version_file.write_text(content, encoding="utf-8")


def main() -> None:
    repo_root = Path(__file__).parent
    version_file = repo_root / "version.py"

    new_version = compute_next_version(version_file)
    write_version(version_file, new_version)
    print(new_version)


if __name__ == "__main__":
    main()
