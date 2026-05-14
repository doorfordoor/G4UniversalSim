# Configuration Reference

The default configuration file is `config/main.ini`. Section and key names are lowercase in the standard format. Some legacy aliases are tolerated in `SimulationManager`, but new files should use the names below.

## `[run]`

| Key | Meaning | Default | Required | Example |
|---|---|---|---|---|
| `name` | Run label written to the summary. | `default_run` | No | `simple_test` |
| `threads` | Requested worker thread count. | `1` | No | `1` |
| `seed` | CLHEP random seed. | unset | No | `12345` |
| `interactive` | Start interactive mode when no macro is supplied. | `false` | No | `false` |
| `verbose` | Framework verbosity. | `0` | No | `1` |
| `check_overlaps` | Geometry overlap checks. | context default | No | `true` |
| `dry_run` | Register objects but skip macro/UI execution. | `false` | No | `false` |

## `[output]`

| Key | Meaning | Default | Required | Example |
|---|---|---|---|---|
| `dir` | Output directory. | `output` | No | `output/simple_test` |

## `[materials]`

| Key | Meaning | Default | Required | Example |
|---|---|---|---|---|
| `file` | Material configuration file. | none | For configured geometry | `config/materials/material.ini` |

Current material safety limit: `mode = volume_fraction` can be parsed by the material parser, but `MaterialFactory` does not implement the backend conversion yet. Do not use it in runnable material files.

## `[geometry]`

| Key | Meaning | Default | Required | Example |
|---|---|---|---|---|
| `template` | Geometry template name. | `simple_box` | Yes for config-driven run | `simple_box` |
| `config` | Geometry ini file. | none | Yes for `/run/initialize` | `config/geometry/simple_box.ini` |
| `check_overlaps` | Pass overlap flag to placements. | context default | No | `true` |
| `default_world_material` | Fallback world material. | `G4_AIR` | No | `G4_AIR` |

Current geometry safety limits:

- `template = gdml` is placeholder-only. It stores `[gdml]` keys but does not call `G4GDMLParser`; do not use it with `/run/initialize`.
- `shape = trd` and `shape = trapezoid` are runnable `G4Trd` aliases in hierarchical geometry. They require `dx1`, `dx2`, `dy1`, `dy2`, and `dz`; all are Geant4 half-lengths.
- `shape = trap` is runnable through `G4Trap`. It requires `dz`, `theta`, `phi`, `dy1`, `dx1`, `dx2`, `alpha1`, `dy2`, `dx3`, `dx4`, and `alpha2`. Length fields are half-lengths and angle fields support `deg` or `rad`. Invalid `G4Trap` planarity still fails in Geant4 construction.
- `layered_device` now propagates `copyNo`, `metadata.*`, and unknown layer keys into `VolumeNode::userProperties`. `copyNo` is used as the `G4PVPlacement` copy number; metadata is currently only an internal tag and is not written to hit CSV files.
- STL import has no parser or backend in the current executable.

## `[physics]`

| Key | Meaning | Default | Required | Example |
|---|---|---|---|---|
| `reference` | Geant4 reference physics list. Empty means manual mode. | empty/manual | No | `FTFP_BERT_EMZ` |
| `em` | Manual EM option or reference suffix request. | `option4` | No | `option4` |
| `modules` | Manual modules, or extra modules in reference mode for compatibility. | `decay` | No | `decay, ion` |
| `extra_modules` | Additional constructors for reference mode. | empty | No | `optical` |
| `default_cut` | Global production cut. | `1 mm` | No | `1 mm` |
| `biasing` | Enable generic biasing physics hook. | `false` | No | `false` |
| `verbose` | Physics verbosity. | `0` | No | `1` |

## `[physics.microelec]`

| Key | Meaning | Default | Required | Example |
|---|---|---|---|---|
| `enabled` | Register optional MicroElec extension. | `false` | No | `true` |
| `region` | Target region name. | `SV` | No | `SV` |
| `electron_capture` | Enable low-energy e- capture helper. | `false` | No | `true` |
| `electron_capture_threshold` | Capture threshold. | `16.7 eV` | No | `16.7 eV` |

## `[source]`

| Key | Meaning | Default | Required | Example |
|---|---|---|---|---|
| `preset` | Source preset. | GPS default | No | `proton_beam` |
| `particle` | Particle name. | preset/GPS default | No | `proton` |
| `energy` | Mono energy. | preset/GPS default | No | `10 MeV` |
| `position_type` | `point` or `plane`. | preset/GPS default | No | `point` |
| `position` | Point position. | preset/GPS default | No | `0,0,-1 mm` |
| `direction` | Unitless direction vector or axis token. | preset/GPS default | No | `0,0,1` |
| `isotropic` | Use isotropic angular distribution. | `false` | No | `false` |

## `[scoring]`

| Key | Meaning | Default | Required | Example |
|---|---|---|---|---|
| `enabled` | Master scoring switch. | `true` | No | `true` |
| `hits` | Write `hits_tN.csv`. | `true` | No | `true` |
| `event_edep` | Write `event_edep_tN.csv`. | `true` | No | `true` |
| `edep` | Enable `EdepScorer`. | `true` | No | `true` |
| `let` | Enable LET stub scorer. | `false` | No | `false` |
| `dose` | Enable dose stub scorer. | `false` | No | `false` |
| `fluence` | Enable fluence stub scorer. | `false` | No | `false` |
| `auto_create_default_scorers` | Create default scorers at BeginRun. | `true` | No | `true` |

`let`, `dose`, and `fluence` are current stub/no-op scorer surfaces. They are not validated physical LET, dose, or fluence outputs.

## `[scoring.edep]`

| Key | Meaning | Default | Required | Example |
|---|---|---|---|---|
| `raw_histogram` | Write raw edep histogram. | `true` | No | `true` |
| `weighted_histogram` | Write weighted edep histogram. | `true` | No | `true` |
| `bins` | Histogram bins. | `200` | No | `200` |
| `min` | Histogram lower edge. | `0` | No | `0 eV` |
| `max` | Histogram upper edge. | `10` internal energy units unless configured | No | `10 MeV` |

## `[biasing]`

| Key | Meaning | Default | Required | Example |
|---|---|---|---|---|
| `enabled` | Enable biasing manager state and post-build attachment. | `false` | No | `false` |

## `[biasing.xs.<particle>.<process>]`

Recommended process-level XS biasing rule. The section name supplies the particle and Geant4 process name. Process names containing `.` are not supported in section names in this version.

```ini
[biasing.xs.proton.protonInelastic]
factor = 3.0
volumes = Target
only_primary = false
apply_to_secondaries = true
min_weight = 0.02
max_interactions = 8
```

| Key | Meaning | Default | Required | Example |
|---|---|---|---|---|
| `enabled` | Enable this process rule. | `true` | No | `true` |
| `factor` | Cross-section scale for this particle/process. | `1.0` | No | `3.0` |
| `volumes` | Target logical volume names. Empty means global/registry bias volumes. | empty | No | `Target, Shield` |
| `only_primary` | Apply only to primary tracks. | `true` | No | `false` |
| `apply_to_secondaries` | Apply to secondary tracks too. Overrides `only_primary`. | `false` | No | `true` |
| `min_weight` | Skip tracks below this weight. | `0.05` | No | `0.02` |
| `max_interactions` | Max biased interactions per track/process. `-1` means unlimited. | `5` | No | `8` |

## `[biasing.xs]` legacy shorthand

Legacy particle-level shorthand. It is still supported, but it expands as `particles x processes`; all generated process rules share the same parameters. Prefer `[biasing.xs.<particle>.<process>]` for precise per-process control.

Importance biasing, weight-window, splitting, and Russian roulette are not implemented in the current config parser/backend. Current runnable biasing support is process-level XS biasing.

| Key | Meaning | Default | Required | Example |
|---|---|---|---|---|
| `particles` | Comma-separated biased particles. | empty | When biasing enabled | `proton` |
| `processes` | Comma-separated Geant4 process names. | empty | For effective XS biasing | `protonInelastic` |
| `factor` | Cross-section scale. | `1.0` | No | `100` |
| `volumes` | Target logical volume names. | registry bias volumes | No | `Target` |
| `only_primary` | Apply only to primary tracks. | `true` | No | `true` |
| `apply_to_secondaries` | Apply to secondary tracks too. | `false` | No | `false` |
| `min_weight` | Skip tracks below this weight. | `0.05` | No | `0.05` |
| `max_interactions` | Max biased interactions per track/process. `-1` means unlimited. | `5` | No | `5` |
