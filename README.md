# PowerSystemEconomics

This repository is structured around a Julia-based economic dispatch study of how renewable energy bidding could change mainland Korea SMP.

Current project direction:

- `Pre-revision ED` is the primary baseline and should be validated against actual 2024-2025 mainland SMP before expanding the counterfactual analysis.
- `Post-revision ED` should stay narrowly scoped to the incremental rule change: renewable bidding plus price-setting eligibility.
- Data ingestion, preprocessing, model construction, calibration, and outputs should remain separated so the workflow stays reproducible.

Recommended repository layout:

- `docs/project-design/`: planning documents, methodology notes, and report-formulation materials.
- `docs/data-spec/`: data dictionaries and source specifications.
- `data/raw/`: raw downloaded source files.
- `data/processed/`: cleaned and model-ready datasets.
- `src/`: Julia source files such as `load_data.jl`, `preprocess.jl`, and the ED model builders.
- `outputs/figures/`: generated charts for the report and presentation.
- `outputs/tables/`: generated result tables and calibration summaries.

Suggested next implementation files:

- `src/types.jl`
- `src/load_data.jl`
- `src/preprocess.jl`
- `src/build_basic_ed.jl`
- `src/build_pre_ed.jl`
- `src/build_post_ed.jl`
- `src/calibrate.jl`
- `src/scenarios.jl`
- `src/run_all.jl`

Current data-acquisition references:

- `docs/data-spec/api_source_catalog.md`
- `docs/data-spec/api_collection_plan.md`
- `config/data_sources.template.toml`
- `.env.example`
