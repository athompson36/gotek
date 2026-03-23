#!/usr/bin/env python3
"""
Build FlashFloppy indexed racks from ensoniq-vfx-sd/VFX-SD Backup.

Produces two outputs (gitignored):
  - VFX-RACK-BUILD/          — full library: every disk image gets a slot (no byte-dedupe)
  - VFX-RACK-BUILD-DEDUPED/  — skips later files with identical SHA-256 to an earlier slot

Indexed filenames are exactly DSKA0000.IMG, DSKA0001.HFE, … (see docs/correction-context.txt).
No IMG.CFG is written (host=ensoniq + HFE headers suffice; on-device labels only if verified).

Does not modify the backup folder.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKUP = REPO_ROOT / "ensoniq-vfx-sd" / "VFX-SD Backup"
BUILD_FULL = REPO_ROOT / "ensoniq-vfx-sd" / "VFX-RACK-BUILD"
BUILD_DEDUPED = REPO_ROOT / "ensoniq-vfx-sd" / "VFX-RACK-BUILD-DEDUPED"
FF_TEMPLATE = BACKUP / "FF.CFG"

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


def is_disk_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def rel_from_backup(path: Path, backup: Path) -> Path:
    return path.relative_to(backup)


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


def is_os_candidate(rel: Path) -> bool:
    s = str(rel).lower()
    if "vfx" not in s or "os" not in s:
        return False
    return "2.10" in s or "vfx-sd" in s or "vfx sd" in s


def find_os_path(paths: list[Path], backup: Path) -> Path:
    candidates: list[Path] = []
    for p in paths:
        rel = rel_from_backup(p, backup)
        if is_os_candidate(rel):
            candidates.append(p)
    if not candidates:
        raise SystemExit("No OS disk candidate (expected e.g. VFX SD OS 2.10.img).")
    candidates.sort(key=lambda p: (len(rel_from_backup(p, backup).parts), str(rel_from_backup(p, backup))))
    return candidates[0]


def find_stock_path(paths: list[Path], backup: Path) -> Path | None:
    for p in paths:
        rel = rel_from_backup(p, backup)
        if len(rel.parts) != 1:
            continue
        stem = strip_image_suffix(rel.name).lower()
        if "stock" in stem and "library" in stem:
            return p
    return None


def bucket_path(p: Path, backup: Path) -> int:
    """0=root, 1=ATW, 2=Ensoniq, 3=Blanks, 4=other."""
    rel = rel_from_backup(p, backup)
    if len(rel.parts) == 1:
        return 0
    top = rel.parts[0]
    if top == "ATW":
        return 1
    if top == "Ensoniq":
        return 2
    if top == "Blanks":
        return 3
    return 4


def order_paths(paths: list[Path], backup: Path) -> list[Path]:
    """Slot order: OS, Stock library, other root, ATW, Ensoniq, Blanks, other."""
    os_p = find_os_path(paths, backup)
    stock_p = find_stock_path(paths, backup)
    if stock_p == os_p:
        stock_p = None

    used = {os_p}
    if stock_p:
        used.add(stock_p)

    rest = [p for p in paths if p not in used]
    buckets: list[list[Path]] = [[], [], [], [], []]
    for p in rest:
        buckets[bucket_path(p, backup)].append(p)
    for b in buckets:
        b.sort(key=lambda x: str(rel_from_backup(x, backup)).lower())

    ordered: list[Path] = [os_p]
    if stock_p:
        ordered.append(stock_p)
    for b in buckets:
        ordered.extend(b)
    return ordered


def friendly_label(rel: Path) -> str:
    stem = strip_image_suffix(rel.name)
    if len(rel.parts) == 1:
        return stem
    return str(rel.with_suffix("")).replace("/", " ")


def clear_build_dir(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for old in d.iterdir():
        if old.is_file():
            old.unlink()
        elif old.is_dir():
            shutil.rmtree(old)


def patch_ff_cfg(src_text: str) -> str:
    """Align with docs/correction-context.txt; autoselect uses FlashFloppy's *-secs option."""

    def set_line(text: str, key: str, value: str) -> str:
        pat = re.compile(rf"^({re.escape(key)}\s*=\s*).*$", re.MULTILINE)
        if pat.search(text):
            return pat.sub(rf"\g<1>{value}", text, count=1)
        return text.rstrip() + f"\n{key} = {value}\n"

    t = src_text
    t = set_line(t, "interface", "shugart")
    t = set_line(t, "host", "ensoniq")
    t = set_line(t, "nav-mode", "indexed")
    t = set_line(t, "pin34", "ready")
    t = set_line(t, "display-type", "auto")
    t = set_line(t, "image-on-startup", "init")
    # correction-context mentions autoselect-file=yes; firmware uses autoselect-file-secs (non-zero = enable)
    t = set_line(t, "autoselect-file-secs", "2")
    return t


def indexed_basename(slot: int, src: Path) -> str:
    ext = src.suffix.upper()
    return f"DSKA{slot:04d}{ext}"


def compute_duplicate_groups(ordered: list[Path], backup: Path) -> dict[str, list[str]]:
    """hash -> list of relative paths (for full-build informational report)."""
    h_to_paths: dict[str, list[str]] = defaultdict(list)
    for p in ordered:
        h = sha256_file(p)
        h_to_paths[h].append(str(rel_from_backup(p, backup)))
    return {h: paths for h, paths in h_to_paths.items() if len(paths) > 1}


def write_outputs(
    build_dir: Path,
    ordered: list[Path],
    backup: Path,
    *,
    dedupe: bool,
    duplicate_groups_full: dict[str, list[str]],
) -> None:
    clear_build_dir(build_dir)

    catalog_rows: list[dict] = []
    skipped: list[dict] = []
    seen_hash: dict[str, tuple[int, Path]] = {}
    slot = 0

    for src in ordered:
        rel = rel_from_backup(src, backup)
        digest = sha256_file(src)
        ext = src.suffix.upper()
        out_name = indexed_basename(slot, src)

        if dedupe and digest in seen_hash:
            prev_slot, prev_src = seen_hash[digest]
            skipped.append(
                {
                    "duplicate_of_slot": prev_slot,
                    "duplicate_of_path": str(rel_from_backup(prev_src, backup)),
                    "path": str(rel),
                    "sha256": digest,
                    "size": src.stat().st_size,
                }
            )
            continue

        seen_hash[digest] = (slot, src)
        shutil.copy2(src, build_dir / out_name)

        catalog_rows.append(
            {
                "slot": slot,
                "indexed_filename": out_name,
                "friendly_label": friendly_label(rel),
                "source_relative_path": str(rel),
                "size_bytes": src.stat().st_size,
                "sha256": digest,
            }
        )
        slot += 1

    (build_dir / "FF.CFG").write_text(
        patch_ff_cfg(FF_TEMPLATE.read_text(encoding="utf-8", errors="replace")),
        encoding="utf-8",
    )

    # Catalog .md
    lines = [
        "# VFX-SD indexed rack catalog",
        "",
        f"Build: **`{build_dir.name}`** — {'deduplicated by SHA-256' if dedupe else 'full library (every file is a slot)'}",
        f"Source: `{backup.relative_to(REPO_ROOT)}`",
        "",
        "| Slot | Indexed file | Friendly label | Source path | Size | SHA256 (prefix) |",
        "| ---: | --- | --- | --- | ---: | --- |",
    ]
    for row in catalog_rows:
        lines.append(
            f"| {row['slot']} | `{row['indexed_filename']}` | {row['friendly_label']} | `{row['source_relative_path']}` | "
            f"{row['size_bytes']} | `{row['sha256'][:16]}…` |"
        )
    lines.append("")
    lines.append(f"**Total slots:** {len(catalog_rows)}")
    if dedupe:
        lines.append(f"**Files skipped as duplicates:** {len(skipped)}")
    else:
        lines.append("**Byte-identical groups:** see `DUPLICATES_REPORT.md` (all copies still included in this build).")
    (build_dir / "VFX_RACK_CATALOG.md").write_text("\n".join(lines), encoding="utf-8")

    # Catalog .csv
    csv_path = build_dir / "VFX_RACK_CATALOG.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["slot", "indexed_filename", "friendly_label", "source_relative_path", "size_bytes", "sha256"]
        )
        for row in catalog_rows:
            w.writerow(
                [
                    row["slot"],
                    row["indexed_filename"],
                    row["friendly_label"],
                    row["source_relative_path"],
                    row["size_bytes"],
                    row["sha256"],
                ]
            )

    (build_dir / "VFX_RACK_CATALOG.json").write_text(
        json.dumps({"slots": catalog_rows, "skipped_duplicates": skipped}, indent=2),
        encoding="utf-8",
    )

    # DUPLICATES_REPORT.md
    dup_lines = ["# Duplicate report", ""]
    if dedupe:
        dup_lines.append("Files **omitted** from this build (same SHA-256 as an earlier slot):")
        dup_lines.append("")
        if skipped:
            for s in skipped:
                dup_lines.append(
                    f"- `{s['path']}` → same bytes as slot **{s['duplicate_of_slot']}** (`{s['duplicate_of_path']}`)"
                )
        else:
            dup_lines.append("None.")
    else:
        dup_lines.append(
            "This is the **full** build: every file appears in a slot. "
            "Groups below share identical content (verify especially Blanks vs factory images):"
        )
        dup_lines.append("")
        groups = [paths for paths in duplicate_groups_full.values()]
        if groups:
            for paths in sorted(groups, key=lambda x: x[0].lower()):
                dup_lines.append(f"- **{len(paths)} copies**")
                for p in paths:
                    dup_lines.append(f"  - `{p}`")
                dup_lines.append("")
        else:
            dup_lines.append("No duplicate content detected (all unique SHA-256).")

    (build_dir / "DUPLICATES_REPORT.md").write_text("\n".join(dup_lines), encoding="utf-8")

    readme = "\n".join(
        [
            "FlashFloppy indexed rack (generated)",
            f"Variant: {'DEDUPED (unique SHA-256 only)' if dedupe else 'FULL (every source file)'}",
            "",
            f"Slots: {len(catalog_rows)}",
            "",
            "Deploy to USB root (FAT32 volume GOTEK):",
            "  cp DSKA* FF.CFG /Volumes/GOTEK/",
            "  sync",
            "",
            "Do NOT copy IMAGE_A.CFG.",
            "Do NOT copy IMG.CFG unless you add a verified FlashFloppy 3.29 label config (see docs/correction-context.txt).",
            "Geometry: FF.CFG host=ensoniq for raw .IMG; .HFE carries layout internally.",
            "",
            "FF.CFG: nav-mode=indexed, pin34=ready, image-on-startup=init, display-type=auto, autoselect-file-secs=2.",
            "If OLED misbehaves with display-type=auto, edit FF.CFG to your known-good OLED line (e.g. oled-128x32-narrow).",
            "",
            "See docs/gotek-migration-context.txt for dot_clean and diskutil steps.",
            "",
        ]
    )
    (build_dir / "BUILD_README.txt").write_text(readme, encoding="utf-8")


def main() -> None:
    if not BACKUP.is_dir():
        print(f"Missing backup folder: {BACKUP}", file=sys.stderr)
        sys.exit(1)
    if not FF_TEMPLATE.is_file():
        print(f"Missing {FF_TEMPLATE}", file=sys.stderr)
        sys.exit(1)

    raw = collect_images(BACKUP)
    ordered = order_paths(raw, BACKUP)
    dup_groups = compute_duplicate_groups(ordered, BACKUP)

    write_outputs(BUILD_FULL, ordered, BACKUP, dedupe=False, duplicate_groups_full=dup_groups)
    write_outputs(BUILD_DEDUPED, ordered, BACKUP, dedupe=True, duplicate_groups_full=dup_groups)

    n_full = len(ordered)
    n_dedup_slots = n_full - sum(len(g) - 1 for g in dup_groups.values())
    print(f"Full build:    {n_full} slots -> {BUILD_FULL}")
    print(f"Deduped build: {n_dedup_slots} slots -> {BUILD_DEDUPED}")


if __name__ == "__main__":
    main()
