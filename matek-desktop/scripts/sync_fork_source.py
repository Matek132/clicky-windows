"""Keep the locally installed Matek desktop source reviewable in the user's fork."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parent.parent
fork = root / "clicky-windows"
if not (fork / ".git").exists():
    raise SystemExit("Expected local Clicky fork is missing")
target = fork / "matek-desktop"
files = [root / name for name in ("main.py", "pyproject.toml", "requirements.txt", "THIRD_PARTY.md")]
for folder, pattern in [("companion", "*.py"), ("tests", "test_*.py"), ("scripts", "*.py"),
                        ("scripts", "*.bat"), ("scripts", "*.ps1"), ("scripts/hooks", "*.py"),
                        ("config", "*.json"), ("knowledge", "*.md")]:
    files.extend((root / folder).glob(pattern))
files.extend([root / "docs/LOCAL_MEMORY.md", root / "assets/matek.ico"])
for source in files:
    dest = target / source.relative_to(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
# One shared adapter; no copied Screenpipe implementation or captured user data.
shutil.copyfile(root / "memory_backend.py", fork / "memory_backend.py")
shutil.copyfile(root / "memory_backend.py", target / "memory_backend.py")
print(f"Synced {len(files)} source files; no settings, tokens, models, recordings or binaries copied")
