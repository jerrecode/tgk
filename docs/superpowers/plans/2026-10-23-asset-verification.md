# Icon export verification implementation plan

**Goal:** Complete the existing composable icon pipeline with decoded raster checks and reproducible integrity records.

**Architecture:** Retain declarative recipes and staged publication. Choose ICO frames supported by the requested high resolution; record each generated file's digest in the deterministic manifest. Run optional raster tests in CI, without checking generated catalogs into Git.

**Tech stack:** Python 3.10+, unittest, CairoSVG, Pillow, existing C renderer.

**Spec:** User TGK/TGK Tools handoff dated 2026-10-23.

## Constraints and review focus

Preserve SVG-only installs and public APIs. Exercise tiny valid resolutions, default PNG/JPEG/ICO formats, deterministic manifests, generator input bounds, and failure before publication. Hardware touch/insets/keyboard checks remain pending. Repository AGENTS.md requires branch protections before automatic merge; current main is unprotected.

## Task 1: Verify and repair raster exports

- [x] Add a failing decoded-ICO regression for low=8, mid=9, high=10.
- [x] Add assertions for all PNG/JPEG dimensions, alpha, file signatures and per-file hashes.
- [x] Choose only supported ICO frame sizes, including a small-size fallback; close images promptly.
- [x] Bound recipe iterable consumption before materialization.
- [x] Run `make check`, optional raster tests and full catalog generation twice; compare manifests and bytes.
- [x] Update asset CI and document verification, reproducibility boundaries and Android manual test matrix.
- [ ] Commit, open PR, inspect reviews and checks. Merge only if applicable policy permits.

## Evidence ledger

Baseline `make check`: 215 tests pass. Small ICO request produces an unreadable six-byte ICO. CairoSVG 2.9.1 correctly renders normalized eight-digit RGB colors in a direct pixel probe; no color conversion change justified.

Verification: 223 tests pass in normal and UBSan runs. Two full catalogs (421 recipes, 3368 assets each) decode and match byte-for-byte. Native Android hardware remains unavailable. Independent review found no blocking icon issue. Added module CLI saved-default/explicit SVG-only regressions. No measured performance-gain claim. PR publication/checks remain pending at this commit.
