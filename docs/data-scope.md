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

`apartment_complex` is the map-serving apartment master. Its `CX-*`
`complex_id` is retained in walking outputs and API responses. The
`kreb_apt_complex_basic_20250918_yangcheon` table remains a raw/reference
source and is not used as the environment API identifier.

The nationwide `kreb_apt_complex_basic_20250918` import is intentionally not
retained in the hosted database. The product scope is Yangcheon; its geocoded
KREB subset is sufficient for reference and the nationwide source can be
re-imported from the original dataset if a later expansion requires it.

The five card axes are `transport`, `parks_play`, `medical`,
`education_care`, and `convenience`. `safety` is stored as a map-only facility
inventory for future use; it is not a sixth summary card or a currently exposed
environment API axis.

## Storage Policy

Do not commit raw local datasets, private exports, credentials, logs, generated build outputs, or local database files. Small public test fixtures may be added under `tests/resources/` only when tests require them.

