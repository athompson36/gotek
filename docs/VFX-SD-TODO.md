# VFX-SD Gotek — project checklist

Progress is tracked here; racks are built with `scripts/build_vfx_rack.py` into `ensoniq-vfx-sd/VFX-RACK-BUILD/` (full) and `VFX-RACK-BUILD-DEDUPED/` (gitignored). Spec: [`docs/correction-context.txt`](correction-context.txt).

## Documentation

- [x] Repo layout documented (`README.md`, `docs/gotek-migration-context.txt`)
- [ ] Add FlashFloppy **3.29 vs 3.44** note and `autoselect-file-secs` wording to `gotek-migration-context.txt`
- [ ] Document `VFX_SD_Library_Inventory.xlsx` and `vfxsdownersmanual.pdf` in `README.md`
- [ ] Clarify `VFX-SD Backup.zip` vs `VFX-SD Backup/` (canonical edit tree)
- [ ] Decide fate of `flashfloppy-master.zip` (redundant with `flashfloppy-3.44/`)

## Automation & build

- [x] Rack build script: `scripts/build_vfx_rack.py` — **full** + **deduped** builds; exact `DSKA####.ext`; max **10** `Blanks/BlankNNN` templates; **`IMG.CFG`** (Ensoniq .IMG geometry + blank-slot comments); `BLANKS_OMITTED.md`
- [ ] Re-run script after any library change; commit catalog updates if you track them outside gitignore
- [ ] Optional: one-command `make rack` or shell wrapper

## Indexed rack (hardware validation)

- [ ] Copy `VFX-RACK-BUILD/` to USB (FAT32 `GOTEK`), clean metadata, test on VFX-SD
- [ ] Confirm slot 000 = OS, no “file does not exist”, OLED names readable
- [ ] Tune `FF.CFG`: `pin34`, `rotary`, `image-on-startup` if needed

## Config hygiene

- [ ] Archive native-nav `FF.CFG` + `IMAGE_A.CFG` snapshot once indexed USB is stable

## Repo / optional

- [ ] Fix executable bit on tracked `*.HFE` if desired (`git config core.fileMode` / chmod)
- [ ] GitHub topics / description

## Deferred (Mirage)

- [ ] `ensoniq-mirage/` — separate README or project; no VFX-SD tasks
