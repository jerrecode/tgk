# Icon follow-up review implementation plan

Goal: preserve the new purpose-specific icons while repairing SVG compatibility and automatic-upgrade data loss.

Architecture: retain current main geometry and recipe APIs. Forward public SVG color/width parameters; keep chevrons distinct from shafted arrows. Stage automatic catalog upgrades, then validate the actual moved old directory before publication; restore on mismatch and retain the old catalog on successful automatic replacement so an already-open editor descriptor cannot lose its writes. Explicit user-requested overwrite retains its existing behavior.

Global constraints: no Android validation claim; preserve all current main progress and remote history. No arbitrary configuration execution. A generated backup is never deleted by an automatic upgrade. Never treat a matching version number alone as proof of icon integrity.

- [x] Add failing SVG color/width and chevron regressions; implement the focused geometry/forwarding repair.
- [x] Add deterministic edits/additions/link races during real SVG staging; reject changed automatic replacement and retain recovery backup on success.
- [x] Add Tools CLI color regression and fix stale output documentation; align 0.6.11 installer/dependency/bundle versions.
- [ ] Run normal/native checks, real raster decoding, all-asset visual inspection, cross-repo tests and offline installs/upgrades. Review and publish focused PRs; inspect CI and review before merging.

Review focus: concurrent external edits; partially failed publication/rollback; caller-specified SVG stroke/color; small raster legibility and out-of-canvas paths; installation against a stale framework or edited preset catalog.

Local validation: 252 core tests including real optional raster decoding pass normally and with UBSan; 166 Tools tests pass. Independent reviewer exercised publication and restoration failures and found no blocker. Remote CI/merge validation remains pending at this commit.
