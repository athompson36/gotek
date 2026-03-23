#!/usr/bin/env python3
"""
Build a FlashFloppy indexed rack from ensoniq-vfx-sd/VFX-SD Backup into
ensoniq-vfx-sd/VFX-RACK-BUILD/ (gitignored).

Does not modify the backup folder. See docs/gotek-migration-context.txt.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKUP = REPO_ROOT / "ensoniq-vfx-sd" / "VFX-SD Backup"
BUILD = REPO_ROOT / "ensoniq-vfx-sd" / "VFX-RACK-BUILD"
FF_TEMPLATE = BACKUP / "FF.CFG"
ENSONIQ_IMG_CFG = (
    REPO_ROOT / "flashfloppy" / "flashfloppy-3.44" / "examples" / "Host" / "Ensoniq" / "IMG.CFG"
)

IMAGE_SUFFIXES = {".img", ".hfe"}


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def strip_image_suffix(name: str) -> str:
    lower = name.lower()
    for suf in IMAGE_SUFFIXES:
        if lower.endswith(suf):
            return name[: -len(suf)]
    return name


def sanitize_label(rel: Path, max_len: int = 56) -> str:
    """Build a FAT-safe suffix from archive relative path (handles dots in names like 2.10)."""
    text = strip_image_suffix(rel.name)
    if rel.parent != Path("."):
        text = "/".join(rel.parent.parts) + "/" + text
    text = text.replace("\\", "/")
    stem = text.replace("/", "_").replace(" ", "_")
    stem = re.sub(r"[^A-Za-z0-9_.\-+]", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("_")
    if len(stem) > max_len:
        stem = stem[: max_len - 3] + "..."
    return stem or "disk"


def is_disk_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def rel_from_backup(path: Path, backup: Path) -> Path:
    return path.relative_to(backup)


def is_os_candidate(rel: Path) -> bool:
    s = str(rel).lower()
    if "vfx" not in s or "os" not in s:
        return False
    return "2.10" in s or "vfx-sd" in s or "vfx sd" in s


def sort_category(rel: Path) -> tuple[int, str]:
    parts = rel.parts
    if len(parts) == 1:
        return (0, str(rel))
    top = parts[0]
    if top == "ATW":
        return (2, str(rel))
    if top == "Ensoniq":
        return (3, str(rel))
    if top == "Blanks":
        return (4, str(rel))
    return (5, str(rel))


def collect_images(backup: Path) -> list[Path]:
    out: list[Path] = []
    for p in backup.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(backup)
        parts = set(rel.parts)
        if "__MACOSX" in parts or p.name.startswith("._"):
            continue
        if p.name == ".DS_Store":
            continue
        if not is_disk_image(p):
            continue
        out.append(p)
    return out


def order_files(paths: list[Path], backup: Path) -> tuple[list[Path], Path]:
    rels = [rel_from_backup(p, backup) for p in paths]
    os_candidates = [rel for rel in rels if is_os_candidate(rel)]
    if not os_candidates:
        raise SystemExit("No OS disk candidate (expected e.g. VFX SD OS 2.10.img).")
    # Prefer root-level OS image
    os_candidates.sort(key=lambda r: (len(r.parts), str(r)))
    os_rel = os_candidates[0]
    os_path = backup / os_rel

    rest = [p for p in paths if p != os_path]
    rest.sort(
        key=lambda p: (
            sort_category(rel_from_backup(p, backup)),
            str(rel_from_backup(p, backup)).lower(),
        )
    )
    ordered = [os_path] + rest
    return ordered, os_path


def patch_ff_cfg(src_text: str) -> str:
    def set_line(text: str, key: str, value: str) -> str:
        pat = re.compile(rf"^({re.escape(key)}\s*=\s*).*$", re.MULTILINE)
        if pat.search(text):
            return pat.sub(rf"\1{value}", text, count=1)
        return text.rstrip() + f"\n{key} = {value}\n"

    t = src_text
    t = set_line(t, "nav-mode", "indexed")
    t = set_line(t, "pin34", "ready")
    t = set_line(t, "image-on-startup", "init")
    return t


def main() -> None:
    if not BACKUP.is_dir():
        print(f"Missing backup folder: {BACKUP}", file=sys.stderr)
        sys.exit(1)
    if not FF_TEMPLATE.is_file():
        print(f"Missing {FF_TEMPLATE}", file=sys.stderr)
        sys.exit(1)

    BUILD.mkdir(parents=True, exist_ok=True)
    for old in BUILD.iterdir():
        if old.is_file():
            old.unlink()
        elif old.is_dir():
            shutil.rmtree(old)

    raw_paths = collect_images(BACKUP)
    ordered_paths, os_path = order_files(raw_paths, BACKUP)

    seen_hashes: dict[str, tuple[int, Path]] = {}
    duplicates: list[dict] = []
    catalog_rows: list[dict] = []

    slot = 0
    for src in ordered_paths:
        rel = rel_from_backup(src, BACKUP)
        digest = sha256_file(src)
        if digest in seen_hashes:
            dup_slot, dup_of = seen_hashes[digest]
            duplicates.append(
                {
                    "duplicate_of_slot": dup_slot,
                    "duplicate_of_path": str(dup_of.relative_to(BACKUP)),
                    "path": str(rel),
                    "sha256": digest,
                    "size": src.stat().st_size,
                }
            )
            continue
        seen_hashes[digest] = (slot, src)

        ext = src.suffix.upper()
        label = sanitize_label(rel)
        out_name = f"DSKA{slot:04d}_{label}{ext}"
        out_path = BUILD / out_name
        shutil.copy2(src, out_path)

        catalog_rows.append(
            {
                "slot": slot,
                "indexed_filename": out_name,
                "display_label": strip_image_suffix(rel.name),
                "source_filename": src.name,
                "source_relative_path": str(rel),
                "size_bytes": src.stat().st_size,
                "sha256": digest,
                "notes": "",
            }
        )
        slot += 1

    # FF.CFG
    ff_out = BUILD / "FF.CFG"
    ff_out.write_text(patch_ff_cfg(FF_TEMPLATE.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")

    # IMG.CFG: Ensoniq geometry for raw IMG; indexed display uses DSKAnnnn_* filename stem on OLED.
    img_out = BUILD / "IMG.CFG"
    if ENSONIQ_IMG_CFG.is_file():
        header = (
            "## IMG.CFG — Ensoniq geometry (from FlashFloppy 3.44 examples/Host/Ensoniq)\n"
            "## Raw .IMG sizes below; .HFE images use embedded layout.\n"
            "## OLED shows DSKAnnnn_<suffix> from indexed filenames.\n\n"
        )
        img_out.write_text(
            header + ENSONIQ_IMG_CFG.read_text(encoding="utf-8", errors="replace"),
            encoding="utf-8",
        )
    else:
        img_out.write_text(
            "## Placeholder — copy examples/Host/Ensoniq/IMG.CFG from FlashFloppy if missing.\n",
            encoding="utf-8",
        )

    # Catalog
    cat_md = BUILD / "VFX_RACK_CATALOG.md"
    lines = [
        "# VFX-SD indexed rack catalog",
        "",
        f"Built from `{BACKUP.relative_to(REPO_ROOT)}` — **do not edit the backup**; rebuild with this script.",
        "",
        "| Slot | Indexed file | Label | Source path | Size | SHA256 |",
        "| ---: | --- | --- | --- | ---: | --- |",
    ]
    for row in catalog_rows:
        lines.append(
            f"| {row['slot']} | `{row['indexed_filename']}` | {row['display_label']} | `{row['source_relative_path']}` | {row['size_bytes']} | `{row['sha256'][:16]}…` |"
        )
    lines.append("")
    lines.append(f"**Total slots:** {len(catalog_rows)}")
    lines.append(f"**Duplicates skipped:** {len(duplicates)}")
    cat_md.write_text("\n".join(lines), encoding="utf-8")

    cat_json = BUILD / "VFX_RACK_CATALOG.json"
    cat_json.write_text(
        json.dumps({"slots": catalog_rows, "duplicates": duplicates}, indent=2),
        encoding="utf-8",
    )

    dup_md = BUILD / "DUPLICATES_REPORT.md"
    if duplicates:
        dlines = ["# Duplicate disk images (same SHA-256)", ""]
        for d in duplicates:
            dlines.append(
                f"- **{d['path']}** → same as slot {d['duplicate_of_slot']} (`{d['duplicate_of_path']}`)"
            )
        dlines.append("")
        dup_md.write_text("\n".join(dlines), encoding="utf-8")
    else:
        dup_md.write_text("# Duplicates\n\nNo exact duplicates (SHA-256) found.\n", encoding="utf-8")

    readme = BUILD / "BUILD_README.txt"
    readme.write_text(
        "\n".join(
            [
                "FlashFloppy indexed rack (generated)",
                "",
                f"Slots: {len(catalog_rows)}",
                f"Duplicates omitted: {len(duplicates)}",
                "",
                "Deploy: copy DSKA* FF.CFG IMG.CFG to FAT32 USB volume GOTEK; omit IMAGE_A.CFG.",
                "See docs/gotek-migration-context.txt for dot_clean and diskutil steps.",
                "",
                "FF.CFG patches applied: nav-mode=indexed, pin34=ready, image-on-startup=init.",
                "Verify pin34/rotary on real hardware; revert in FF.CFG if needed.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Wrote {len(catalog_rows)} slots to {BUILD}")
    print(f"Skipped {len(duplicates)} duplicate files")


if __name__ == "__main__":
    main()
