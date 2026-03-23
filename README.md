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

Generated rack builds go under `ensoniq-vfx-sd/VFX-RACK-BUILD/` when you create them; that path is gitignored.

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
