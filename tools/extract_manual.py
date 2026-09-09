"""Extract the historical manual and original media without modifying the DOCX."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile


def extract(source: Path, docs: Path) -> None:
    ns = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    media = docs / "assets" / "manual"
    media.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Original MATLAB manual",
        "",
        "Historical documentation extracted from the original DOCX. Instructions",
        "and runtime claims describe MATLAB, not the current Python implementation.",
        "See [the concise guide](legacy-workflows.md) for the workflow summary.",
        "",
    ]
    with ZipFile(source) as archive:
        relationships = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
        targets = {r.attrib["Id"]: r.attrib["Target"] for r in relationships}
        document = ET.fromstring(archive.read("word/document.xml"))
        for paragraph in document.findall(".//w:body/w:p", ns):
            text = "".join(t.text or "" for t in paragraph.findall(".//w:t", ns))
            if text:
                lines.extend([text, ""])
            for blip in paragraph.findall(".//a:blip", ns):
                filename = Path(targets[blip.attrib[f"{{{ns['r']}}}embed"]]).name
                lines.extend(
                    [f"![Original MATLAB workflow](assets/manual/{filename})", ""]
                )
        images = []
        for name in archive.namelist():
            if name.startswith("word/media/"):
                data = archive.read(name)
                (media / Path(name).name).write_bytes(data)
                images.append(
                    dict(file=Path(name).name, sha256=hashlib.sha256(data).hexdigest())
                )
    (docs / "original-manual.md").write_text("\n".join(lines))
    (media / "manifest.json").write_text(
        json.dumps(
            dict(
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                images=images,
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("docs", type=Path)
    args = parser.parse_args()
    extract(args.source, args.docs)
