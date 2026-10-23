# Branch consolidation and regression repair plan

**Goal:** Preserve every audited remote branch's history and useful behavior without reverting current main, and deliver a verified install/update snapshot.

**Architecture:** Inventory pinned branch SHAs and their relationships. Port unique changes into current main; retain later replacements where old behavior is superseded. After content review, record remaining audited heads as merge parents while retaining the verified combined tree. Use merge commits so ancestry survives integration.

**Tech stack:** Git, Python 3.10+, unittest, native C, existing installers.

**Spec:** User's 2026-10-23 instruction to analyze and intelligently integrate all branches in both repositories while preserving newer main progress.

## Constraints and review focus

No force pushes or branch deletion. No wholesale replacement of newer files with stale branch copies. All branch SHAs and decisions must be recorded. Review custom preset validation, option-profile precedence, resource lifecycle, CLI defaults, archive/install update behavior, and retained native APIs. Physical Android checks remain pending without hardware; optimization claims must name measured scope. This task's explicit branch-integration instruction governs the reviewed merges for this pass; standing repository settings are unchanged.

## Tasks

- [x] Audit every remote head against main and other heads; identify exact/squashed, superseded, and unique work.
- [x] Port missing config transaction validation with regressions proving failure leaves previous bytes intact.
- [x] Guard native Canvas use after close and profile binding initialization before/after a bounded cache.
- [x] Recover Tools custom preset discovery/selection and saved pipeline limits against current safe APIs.
- [x] Align both packages/installers/bundle versions with the dormant 0.6.10 release branch.
- [x] Add branch decision reports, retain audited heads as merge ancestry, and obtain independent review.
- [ ] Run complete suites, native sanitizers, clean editable/copy installs, update/reinstall preservation, CLI/demos, deterministic assets and offline packaging.
- [ ] Publish focused consolidation PRs; inspect each current head's CI/reviews before a non-squash merge; verify all inventoried branch heads are reachable from main afterwards.

## Evidence ledger

Baseline: TGK 223 tests, Tools 146 tests pass. No initially open PRs. Head snapshots: TGK main 81e9c2e; Tools main 9893edd. Independent repo audits found genuine dormant custom-preset UI selection and pre-write effective-profile/text validation; later main functionality must remain intact.

Verification ledger: independent audits cover 43 TGK and 42 Tools heads. Recovered geometry, transaction validation, installed catalogs and saved pipeline budgets. Review findings for malformed palette/active typography now have red-to-green regressions. Core normal and UBSan suites pass 237 tests; Tools passes163. Native setup-only benchmark median1000 Canvas create/close operations changed from33.313ms to2.170ms on this Linux host; no Android latency/FPS gain is claimed. Ancestry publication and final remote CI remain pending at this commit.
