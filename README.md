# gotek

Personal workspace for **Ensoniq VFX-SD** Gotek (FlashFloppy) setup: disk library, migration notes from native navigation to **indexed** mode, and vendored FlashFloppy reference files.

**Remote:** [https://github.com/athompson36/gotek](https://github.com/athompson36/gotek)

## Layout

| Path | Purpose |
|------|--------|
| [`docs/`](docs/) | Migration context, Gotek PDFs |
| [`docs/gotek-migration-context.txt`](docs/gotek-migration-context.txt) | Primary spec: indexed rack, `FF.CFG` / `IMG.CFG`, safety rules, USB deploy |
| [`ensoniq-vfx-sd/VFX-SD Backup/`](ensoniq-vfx-sd/VFX-SD%20Backup/) | VFX-SD disk images (`.HFE`, root `.img`), `FF.CFG`, `IMAGE_A.CFG` |
| [`flashfloppy/flashfloppy-3.44/`](flashfloppy/flashfloppy-3.44/) | FlashFloppy release tree (firmware hex, examples, `Host/Ensoniq/IMG.CFG`) |
| [`ensoniq-mirage/`](ensoniq-mirage/) | Separate Mirage material (not part of active VFX-SD migration) |

Generated rack builds are gitignored:

- **`ensoniq-vfx-sd/VFX-RACK-BUILD/`** — full library: every backup image **except** excess `Blanks/*` reference files gets a slot (`DSKA0000.IMG` … exact indexed names only).
- **`ensoniq-vfx-sd/VFX-RACK-BUILD-DEDUPED/`** — same order, but later byte-identical files (same SHA-256) are omitted.

Behavior matches [`docs/correction-context.txt`](docs/correction-context.txt): exact `DSKA####.ext` names; **`Blanks/`** keeps at most **10** `BlankNNN.{HFE,IMG}` templates (lowest N first)—the rest stay in the backup as **reference-only** for formatting new disks (see `BLANKS_OMITTED.md` in each build).

**`IMG.CFG`** in the build: official Ensoniq raw-.IMG geometry stanzas (from FlashFloppy examples; Mirage block omitted) plus `##` comments mapping blank template slots to `Blanks/BlankNNN` sources. Deploy it with `FF.CFG`. Full slot names: `VFX_RACK_CATALOG.md` / `.csv`.

### Build the indexed USB contents

From the repo root:

```bash
python3 scripts/build_vfx_rack.py
```

Each folder receives `FF.CFG`, **`IMG.CFG`**, `DSKA####.{IMG,HFE}`, `VFX_RACK_CATALOG.md`, `VFX_RACK_CATALOG.csv`, `VFX_RACK_CATALOG.json`, `DUPLICATES_REPORT.md`, `BLANKS_OMITTED.md`, and `BUILD_README.txt`. Deploy with `cp DSKA* FF.CFG IMG.CFG` to the USB root (see `BUILD_README.txt`); do not copy `IMAGE_A.CFG`.

Checklist: [`docs/VFX-SD-TODO.md`](docs/VFX-SD-TODO.md).

## Clone and push

```bash
git clone https://github.com/athompson36/gotek.git
cd gotek
```

After cloning an empty GitHub repo into this folder, or to connect this tree:

```bash
git init
git remote add origin https://github.com/athompson36/gotek.git
git branch -M main
git add .
git commit -m "Initial commit"
git push -u origin main
```

This repository is about **850 MB** (mostly disk images under `ensoniq-vfx-sd/`). Ensure Git HTTP buffer if needed: `git config --global http.postBuffer 524288000`.

## Licenses

- **`flashfloppy/flashfloppy-3.44/`** — See [`flashfloppy/flashfloppy-3.44/COPYING`](flashfloppy/flashfloppy-3.44/COPYING) (upstream FlashFloppy; includes public-domain/Unlicense portions and noted third-party exceptions).
- Disk images and project notes are personal/archival material unless otherwise marked.
