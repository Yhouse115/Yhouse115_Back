# Data Scope

## Initial Area

- 신정1동
- 신정4동

## Priority Data

- Apartments
- Elementary schools
- Daycare centers
- Pediatric clinics
- Parks
- CCTV
- Crosswalks
- Pedestrian signals
- Child protection zones
- Accident-prone areas

## Yangcheon environment serving layer

Raw and source-specific tables remain the ingestion record. The map API reads
the following normalized serving tables instead:

- `source_dataset` records source name, reference date, file provenance, and
  metadata.
- `environment_feature` stores normalized map facilities with PostGIS location,
  source record identity, status, and source-specific JSON attributes.
- `complex_feature_access` stores selected, pre-computed walking-network access
  facts.
- `complex_environment_summary` stores the card-ready nearest facility and
  count facts.

`kreb_apt_complex_basic_20250918_yangcheon` is the apartment master. The
walking outputs originally keyed by `CX-*` must be mapped through
`reb_complex_id` before they are stored or served as a complex ID.

The five card axes are `transport`, `parks_play`, `medical`,
`education_care`, and `convenience`. `safety` is stored as a map-only facility
inventory for future use; it is not a sixth summary card or a currently exposed
environment API axis.

## Storage Policy

Do not commit raw local datasets, private exports, credentials, logs, generated build outputs, or local database files. Small public test fixtures may be added under `tests/resources/` only when tests require them.

