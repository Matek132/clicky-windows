"""Bounded, offline lexical lookup over user-editable Markdown/text reference notes."""
from pathlib import Path
import re
import sys

STOPWORDS = {"what", "when", "where", "which", "that", "this", "with", "have", "does", "make", "build",
             "craft", "minecraft", "explain", "about", "could", "please", "would", "your", "from", "there"}


def reference_folder(settings):
    if settings.knowledge_folder:
        return Path(settings.knowledge_folder)
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    folder = root / "knowledge"
    return folder if folder.exists() else Path(getattr(sys, "_MEIPASS", root)) / "knowledge"


def search_references(question, settings):
    if not settings.knowledge_enabled:
        return ()
    folder = reference_folder(settings)
    if not folder.is_dir():
        return ()
    words = {w.rstrip("s") for w in re.findall(r"\w{4,}", question.casefold()) if w not in STOPWORDS}
    domains = {"minecraft", "terraria", "unity", "unreal", "python", "blender"}
    question_domains = set(re.findall(r"\w+", question.casefold())) & domains
    candidates = []
    for index, path in enumerate(sorted(folder.iterdir())):
        if index >= 100:
            break
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        if path.name.lower() == "readme.md" or path.stat().st_size > 32768:
            continue
        try:
            text = path.read_text(encoding="utf-8")[:8000]
        except (OSError, UnicodeError):
            continue
        terms = {w.rstrip("s") for w in re.findall(r"\w{4,}", text.casefold())}
        document_domains = set(re.findall(r"\w+", text.casefold())) & domains
        if question_domains and document_domains and question_domains.isdisjoint(document_domains):
            continue
        anchors = {w.rstrip("s") for w in re.findall(r"\w{4,}", path.stem.casefold() + " " + text.splitlines()[0].casefold())}
        if not words & anchors:
            continue
        score = len(words & terms)
        if score:
            candidates.append((score, path.name, text))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return tuple((name, text[:2500]) for _, name, text in candidates[:2])
