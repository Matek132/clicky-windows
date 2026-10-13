"""Copy installed package licence notices and metadata for local build review."""
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys

destination = Path(sys.argv[1]).resolve()
destination.mkdir(parents=True, exist_ok=True)
rows = []
for package in metadata.distributions():
    name = package.metadata.get("Name", "unknown")
    row = {"package": name, "version": package.version,
           "licence": package.metadata.get("License-Expression") or package.metadata.get("License"),
           "project_urls": package.metadata.get_all("Project-URL", [])}
    rows.append(row)
    for file in package.files or []:
        if any(word in file.name.upper() for word in ("LICENSE", "LICENCE", "COPYING", "NOTICE")):
            source = Path(package.locate_file(file))
            if source.is_file():
                relative = Path(name) / str(file).replace("..", "_")
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
(destination / "inventory.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
