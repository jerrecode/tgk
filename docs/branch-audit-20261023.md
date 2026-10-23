# TGK remote branch audit

Audit baseline origin/main=81e9c2e, 43 remote branch heads excluding main/HEAD. Audit itself was read-only; subsequent explicitly assigned additive adaptive recovery committed as 8afcf99. No remote refs changed. Metadata in audit-tgk-branches.json.

Method: merge-base, left/right ancestry counts, git cherry patch equivalence, compare all branch-modified file blobs to matching first-parent main integration commits, inspect alternate implementations and run alternate tests against current main. A + in git cherry alone is insufficient because main squashed most PR histories.

## Per-branch classification

| Remote branch (origin/ omitted) | Head | Main integration | Classification and evidence |
|---|---|---|---|
| chore/version-0610-android-fixes-20261023 | a9501ef | version-only/ancestor | Version only: net two 0.6.9→0.6.10 assignments; two same-purpose release commits; no missing Android fix code. |
| feat/config-explicit-pins-batch-20261023 | 6b07715 | 8382397 | Mostly superseded by 8382397 + concurrency/security hardening, and its six pin tests pass main. UNIQUE FIX: resolve_text_style() validates selected custom typography properties before config replacement; recover these lines in main locked transaction. |
| feat/config-multipatch-raster-default-20261023 | f35a292 | b86d6eb | Exact content of EVERY file modified on branch exists in main integration b86d6eb; later main improvements explain present-day differences. Preserve main tree. |
| feat/fluid-window-scaling-breakpoint-grid-20261023 | a3071b3 | 6e52232 | Core behavior superseded by c2a3715 + 6e52232. UNIQUE additive helpers RECOVERED in 8afcf99: ScreenMetrics.safe_content_size_dp/is_landscape; LayoutScale.available_width; column_width optional columns argument. Main retains newer dp/sp/px conversions, bounded gutters and layout-managed heights. Old root-height expectation is a regression. |
| feat/persistent-config-presets-20261023 | 4f52e0c | af221f0 | Unselected alternative TGK_CONFIG_DIR/defaults/window/backend schema, helper APIs and catalog file layout. Main TGK_CONFIG_HOME/ui/runtime/per-file presets covers functional defaults, validation, cache, themes/text, layout, I/O. Do not switch schemas or import obsolete aliases as though shipped compatibility. |
| feat/pinned-config-overrides-20261023 | 8382397 | version-only/ancestor | Already an ancestor of main (8382397); no merge needed. |
| feature/adaptive-layout-style-tokens-20261023 | ba34fdd | 2792ec2 | Exact content of EVERY file modified on branch exists in main integration 2792ec2; later main improvements explain present-day differences. Preserve main tree. |
| feature/composable-icon-assets-20261023 | 3848020 | 5722899 | Exact content of EVERY file modified on branch exists in main integration 5722899; later main improvements explain present-day differences. Preserve main tree. |
| feature/config-profile-atomic-update-20261023 | bc8f05e | 539700e | Older single-field atomic writer + alternate profile-application factoring; all 13 branch tests pass main. Main adds batch/reset/pins/concurrency/no-follow/cache identity. No missing feature detected. |
| feature/install-generated-icon-catalog-20261023 | 008b395 | 16964a7 | Exact content of EVERY file modified on branch exists in main integration 16964a7; later main improvements explain present-day differences. Preserve main tree. |
| feature/navigation-windows-typography-icons-20261023 | e2f1225 | 6519f7e | Exact content of EVERY file modified on branch exists in main integration 6519f7e; later main improvements explain present-day differences. Preserve main tree. |
| feature/persistent-config-presets-20261023 | 59eb798 | af221f0 | Unselected aggregate registries under presets/{colors,typography,options}.json; color_registry/text_registry/option_registry/set_defaults APIs replace an incompatible config schema. Main supports selected custom per-file presets and audits them. Explicit arbitrary named palette/style selection and enumeration is useful to tools but must be ported using current per-file schema, not old files. |
| feature/persistent-runtime-presets-config-20261023 | a042147 | af221f0 | Exact content of EVERY file modified on branch exists in main integration af221f0; later main improvements explain present-day differences. Preserve main tree. |
| feature/semantic-themes-and-ui-labs-20261023 | 5b42ef3 | d58013f | Exact content of EVERY file modified on branch exists in main integration d58013f; later main improvements explain present-day differences. Preserve main tree. |
| feature/viewport-size-spec-current-main-20261023 | d23df30 | fdd914f | Exact content of EVERY file modified on branch exists in main integration fdd914f; later main improvements explain present-day differences. Preserve main tree. |
| fix/accessibility-breakpoints-current-main-20261023 | 764d8dd | 6e52232 | Equivalent breakpoint/font-scale/layout-managed sizing through main _set_touch_height; branch calls renamed _refresh_touch_height. Four portable tests pass, two depend on obsolete private method. Main additionally honors explicit opt-out height and validates component styles. |
| fix/android-input-frame-fill-and-overlay-20261023 | f283b22 | a777fd9 | Exact content of EVERY file modified on branch exists in main integration a777fd9; later main improvements explain present-day differences. Preserve main tree. |
| fix/clock-budget-iterative-native-tree-20261023 | e95692e | 6d55b48 | Exact content of EVERY file modified on branch exists in main integration 6d55b48; later main improvements explain present-day differences. Preserve main tree. |
| fix/compact-footer-live-window-background-20261023 | 18d47e9 | 13ce9cc | Exact content of EVERY file modified on branch exists in main integration 13ce9cc; later main improvements explain present-day differences. Preserve main tree. |
| fix/config-atomic-settings-20261023 | 519ee17 | 539700e | Exact content of EVERY file modified on branch exists in main integration 539700e; later main improvements explain present-day differences. Preserve main tree. |
| fix/config-atomic-updates-unified-defaults-20261023 | 7c9e242 | 539700e | Batch API superseded by main; raster=None saved-default handling present main. UNIQUE prewrite custom typography resolution also present here (_validated_config_patch); recover validation. One old test deliberately corrupts a palette then expects unrelated update to succeed; reject because main correctly validates selected preset. |
| fix/config-cache-atomic-replacement-20261023 | 13fca05 | abeefe5 | Exact content of EVERY file modified on branch exists in main integration abeefe5; later main improvements explain present-day differences. Preserve main tree. |
| fix/config-concurrent-lock-20261023 | e243a3d | 68b229c | Exact content of EVERY file modified on branch exists in main integration 68b229c; later main improvements explain present-day differences. Preserve main tree. |
| fix/config-explicit-pins-batched-edits-v063-20261023 | ab827f7 | 8382397 | Ten alternate atomic settings tests pass main; pin/reset/batch functionality preserved. Private validation factoring not needed; inspect selected-style full validation in main separately. |
| fix/config-no-follow-preset-reads-20261023 | 440d683 | 9d4e15a | Exact content of EVERY file modified on branch exists in main integration 9d4e15a; later main improvements explain present-day differences. Preserve main tree. |
| fix/config-pinned-precedence-only-v064-20261023 | 9df7bdb | 8382397 | Five alternate pin precedence tests pass main. Only older factoring/signatures/version differ; main adds public update_settings alias, concurrency, secure reads. |
| fix/config-presets-safety-and-default-text-20261023 | adc29a4 | 9c30a87 | Typography defaults and create-only safe target behavior integrated by 9c30a87. Branch lacks 68b229c locking despite later merge base comparison; retain main implementation. |
| fix/config-profile-precedence-20261023 | bed7d6d | a653910 | Exact content of EVERY file modified on branch exists in main integration a653910; later main improvements explain present-day differences. Preserve main tree. |
| fix/configurable-responsive-columns-20261023 | 0610653 | c2a3715 | Exact content of EVERY file modified on branch exists in main integration c2a3715; later main improvements explain present-day differences. Preserve main tree. |
| fix/demo-interactive-slider-20261023 | d3db5bf | d775dd3 | Exact content of EVERY file modified on branch exists in main integration d775dd3; later main improvements explain present-day differences. Preserve main tree. |
| fix/install-audit-after-secure-reads-20261023 | 7ef7fc8 | 82bf6e8 | Exact content of EVERY file modified on branch exists in main integration 82bf6e8; later main improvements explain present-day differences. Preserve main tree. |
| fix/install-full-preset-validation-v068-20261023 | d6dde85 | 82bf6e8 | Same installer init→validate→audit commands as main; only comments and assertion naming/docstring differ versus 82bf6e8. No runtime progress missing. |
| fix/native-wheel-packaging | b455c62 | aeafa0e | Patch-equivalent main commit aeafa0e (git cherry -); two README pointer-ownership lines belong to other fix and are present main. |
| fix/persistent-config-settings-atomic-20261023-v2 | 556116b | 539700e | Old batch/pinning API predecessor; nine portable tests pass main. One branch CLI test uses an unquoted non-JSON string (main intentionally requires JSON values). Main retains stronger schema, pins/reset + locking. |
| fix/pinned-settings-on-current-main-20261023 | aee334a | 8382397 | Exact content of EVERY file modified on branch exists in main integration 8382397; later main improvements explain present-day differences. Preserve main tree. |
| fix/reactive-theme-redraw-and-bounded-pipelines-20261023 | f5fdd47 | af345e1 | Exact content of EVERY file modified on branch exists in main integration af345e1; later main improvements explain present-day differences. Preserve main tree. |
| fix/responsive-sizing-and-grid-consistency-20261023 | 06ec856 | fdd914f | SizeSpec integrated at fdd914f. logical_columns is old spelling of span_units and uses lossy round vs main ceiling. Constructor uses running App columns, superseded by backend setting effective columns at native render. Main adds viewport converters, bounded gutters, explicit dimension validation and native column immutability. |
| fix/sizing-layout-managed-and-update-docs-20261023 | 6a2808d | 6e52232 | Exact content of EVERY file modified on branch exists in main integration 6e52232; later main improvements explain present-day differences. Preserve main tree. |
| fix/slider-imageview-touch-coordinate-space | bee2fd8 | 46bdd4d | Exact content of EVERY file modified on branch exists in main integration 46bdd4d; later main improvements explain present-day differences. Preserve main tree. |
| fix/slider-pointer-ownership | 9c5483c | a0c5cd0 | Exact content of EVERY file modified on branch exists in main integration a0c5cd0; later main improvements explain present-day differences. Preserve main tree. |
| fix/validate-all-presets-bounded-json-20261023 | 4dac8ab | ee8356e | Exact content of EVERY file modified on branch exists in main integration ee8356e; later main improvements explain present-day differences. Preserve main tree. |
| fix/verified-icon-raster-20261023 | d25a3d9 | 81e9c2e | Exact content of EVERY file modified on branch exists in main integration 81e9c2e; later main improvements explain present-day differences. Preserve main tree. |
| perf/native-event-index-20261023 | c29adc6 | 08e7499 | Exact content of EVERY file modified on branch exists in main integration 08e7499; later main improvements explain present-day differences. Preserve main tree. |

## Relationships between remote heads

Only feat/pinned-config-overrides-20261023 is ancestor of other named remote heads (17 descendants); it equals main commit 8382397. All other named remote heads are incomparable by direct commit ancestry, despite logical feature succession. Their shared first-parent main bases and integrated file equivalence establish the feature sequence. Main has 12 commits beyond the pinned branch. Every other head has divergent apparent ancestry mostly because of squashed PR integration.

Main integration sequence: slider → coordinates → pointer ownership → wheel packaging → semantic themes → navigation/typography/icons → bounded reactive pipelines → event index → adaptive/style tokens → bounded clock/native tree → compact footers → layered asset builder → persistent runtime defaults → profile precedence → atomic settings → multipatch/raster defaults → pinned overrides → configured responsive columns → SizeSpec → accessible layout handling → concurrent config lock → safe defaults → full preset audit → no-follow reads → install preset audit → generated icon catalog → cache identity → Android input/frames → verified raster assets.

## Missing useful progress and recommendations

1. Recover prewrite typography resolution from feat/config-explicit-pins-batch into current patch_config. Branch does `resolve_text_style(style_obj.get("style",text_name), **style_obj["properties"])` before writing; main only checks properties is a dict. Reproduced: custom.json with unknown font_size property; patch_config succeeds and changes config bytes, then configured_text_style fails TypeError. Also test invalid size_sp and unknown base style. Keep current lock/no-follow reads, rollback semantics and public batch API.
2. Additive fluid helpers can be recovered without old widget layout code: safe_content_size_dp, is_landscape, available_width and optional explicit column-count calculation. They are genuine absent API additions but have no branch runtime callers. Preserve current converters, bounded gutters and height management.
3. Old aggregate custom-preset registries are incompatible alternatives; selected custom defaults already work in current main. For explicit arbitrary custom selection/catalog enumeration needed by tools, use current palettes/*.json, text_styles/*.json and options/*.json, secure bounded reads, load_theme and resolve_text_style. Do not resurrect registry schema or overwrite current files.
4. Version 0.6.10 branch is exactly release metadata progress; main latest raster behavior and Android repair code should remain intact.

## Additional concrete main bug found

Current patch_config validates raw stored candidate and option profile independently, but merges them only in final post-replacement load_config. Reproduced custom options/custom.json with valid layout compact_breakpoint_dp=700, expanded_breakpoint_dp=900, then patch_config selecting custom profile while explicitly setting expanded_breakpoint_dp=650: raw default compact600/expanded650 is valid and profile700/900 valid; combined effective700/650 invalid. Call raises AFTER changing config.json and leaves future loads broken. Validate full effective candidate with pins/profile precedence before replacement, ideally a shared pure resolver used by load_config and patch_config.

## Alternate branch tests exercised on main

| Branch family | Tests run | Result |
|---|---:|---|
| explicit pins batch | 6 | all pass |
| fluid responsive | 8 | 6 pass; missing geometry helper; obsolete root-height expectation fails |
| config profile atomic | 13 | all pass |
| atomic unified defaults | 15 | 14 pass; corrupt-selected-palette expectation rejected by stronger main validation |
| explicit pins batched v063 | 10 | all pass |
| pin precedence v064 | 5 | all pass |
| persistent atomic v2 | 10 | 9 pass; old test supplies unquoted non-JSON CLI string |
| accessibility breakpoint | 6 | 4 pass; 2 require renamed private _refresh_touch_height |
| responsive sizing | 8 | 6 pass; old logical_columns name and pre-render columns expectation differ |

## Ancestry-only preservation assessment

After porting selected absent helpers/typography validation and fixing effective-config transaction validation, ancestry-only merge(s) preserving main tree are supported for all superseded/exact integrated heads. Exclude already-ancestor pinned head from new parents; it is already preserved. For alternate config schemas and private-method spellings, explicitly document their supersession. For version-only head either recover release alignment first or document its supersession. Do not claim every branch had an identical patch: only the rows with explicit exact integration evidence do. Branch histories remain available as merge parents while current files retain modern behavior.

## Recovery validation

Adaptive helper recovery is committed as 8afcf99 (tgk/adaptive.py and tests/test_adaptive_recovered.py only). Six dedicated tests exercised explicit/no/oversized insets, authoritative orientation, content caps/margins, effective-column bounded gaps, one-column gaps, signature compatibility and invalid input. Initial test run failed due missing helpers/columns argument; final focused run passed. Mandatory `make check` passed 234 tests and compileall before commit (concurrent root transaction tests included). Full log: audit-tgk-adaptive-check.log.

## Consolidation outcome

Current main remains the content base. Useful missing behavior is ported in focused changes; obsolete schemas and private API variants stay superseded. Original branch tips are retained as merge parents after this audit. The final integration must use a merge commit, not squash, to preserve that ancestry. No branch deletion or force push is performed.

Recovered typography validation, effective profile/pin pre-publication validation, safe-content/orientation/column helpers and the dormant 0.6.10 release alignment. Additional resource fixes guard Canvas calls after close, synchronize close versus drawing, cache native bindings, validate malformed active palettes/styles/options, and bound audit collection before sorting.
