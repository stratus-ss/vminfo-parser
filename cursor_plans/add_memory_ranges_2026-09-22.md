# Plan: Add Memory Range Breakdown Report

## OBJECTIVE

Add a new `--get-memory-ranges` CLI report that buckets VMs by allocated memory
(GiB) into predefined power-of-2 tiers (0–4, 5–8, 9–16, 17–32, 33–64, 65–128,
129–256, 257+), dynamically trims unused upper tiers based on the dataset's max
memory value, drops empty middle tiers, and presents counts in the terminal.
The report supports `--sort-by-env` (all/both/prod/non-prod), `--minimum-count`
filtering, and `--generate-graphs` with horizontal/grouped-vertical charts that
match the existing disk-space report behavior.

```
project_name: add_memory_ranges
```

Token budget: ~55K tokens (plan + 10 files: `vminfo_parser/analyzer.py` 865
lines, `vminfo_parser/visualizer.py` 455 lines, `vminfo_parser/__main__.py`
277 lines, `vminfo_parser/config.py` 323 lines,
`agent_planning/openspec/specs/vm-reporting-cli/spec.md`,
`tests/unit/test_analyzer.py`, `tests/unit/test_main.py`,
`tests/unit/test_visualizer.py`, `tests/unit/conftest.py`, `README.md`)

## DECISION RECORDS

### DR-1: Bucket Strategy — Predefined + Trimmed
- **Decision:** Follow the same hybrid pattern as disk-space ranges:
  predefined tiers dynamically trimmed to the data max, with empty middle tiers
  dropped from output.
- **Rationale:** Consistent with the existing codebase, comparable across
  datasets, and easy for infra teams to interpret.
- **Assumptions:** VM memory data is normalized to GiB integers before
  analysis via `VMData._normalize_to_GiB()`.
- **Dependencies:** none

### DR-2: Memory Tier Boundaries
- **Decision:** Use eight tiers with a small-VM bucket and a capped top tier:
  `(0,4), (5,8), (9,16), (17,32), (33,64), (65,128), (129,256), (257,max)`
- **Rationale:** These boundaries match common VM sizing conventions while
  keeping the labels round and non-fractional.
- **Assumptions:** Fractional GiB values should not survive normalization.
- **Dependencies:** none

### DR-3: Environment Split Support
- **Decision:** Support `--sort-by-env` (`all`, `both`, `prod`, `non-prod`)
  following the same report-shape pattern as disk-space ranges.
- **Rationale:** Consistent report behavior across the tool.
- **Assumptions:** `create_environment_filtered_dataframe()` remains the
  canonical environment categorization path.
- **Dependencies:** none

### DR-4: Graph Type
- **Decision:** Use a horizontal bar chart for `all` and a grouped vertical bar
  chart for split-environment output, matching the existing disk-space report.
- **Rationale:** Visual consistency with current range-based reports.
- **Assumptions:** matplotlib `Axes.barh()` and `DataFrame.plot(kind="bar")`
  remain stable APIs.
- **Dependencies:** DR-3

### DR-5: CLI Flag Naming
- **Decision:** `--get-memory-ranges`
- **Rationale:** Parallels `--get-disk-space-ranges`.
- **Assumptions:** none
- **Dependencies:** none

## PROJECT CONTEXT

- **Language:** Python 3.11+
- **Key libraries:** pandas, matplotlib, pytest
- **Pipeline:** CLI parses args → `Config` → `VMData.from_file()` → `Analyzer`
  computes report data → `CLIOutput` prints tables → `Visualizer` renders
  optional charts
- **Repository root:** `/home/sovens/git_projects/vminfo-parser`
- **Memory column:** `vmMemory` in `COLUMN_HEADERS` maps to `"VM MEM (GB)"`
  (VERSION_1) or `"Memory"` (VERSION_2/3). `VMData._normalize_to_GiB()`
  already converts MiB inputs to integer GiB.
- **OpenSpec:** This codebase already has a CLI behavior spec at
  `agent_planning/openspec/specs/vm-reporting-cli/spec.md`. Read it before
  Task 1 and archive spec deltas in the final task.

### Library Context (context7-queried)

| Library | context7 ID | Key patterns confirmed |
|---------|-------------|------------------------|
| pandas | `/websites/pandas_pydata` | `groupby(...).size().unstack(fill_value=0)` for environment splits, `value_counts()` for single-dimension counts, `pd.to_numeric(..., errors="coerce")` for defensive numeric conversion, `sort_values()` for explicit ordering |
| matplotlib | `/websites/matplotlib_stable` | `Axes.barh()` for horizontal bar charts, `DataFrame.plot(kind="bar", stacked=False)` for grouped vertical bars, `ticker.ScalarFormatter()` for integer-like axis labels |

### Shared Patterns (DRY Audit)

| Pattern | Defined in | Tasks that use it |
|---------|------------|-------------------|
| Environment filtering | `vminfo_parser/vmdata.py:create_environment_filtered_dataframe()` | Task 3 |
| Dynamic range trimming | `vminfo_parser/analyzer.py:generate_dynamic_ranges()` | Task 3 |
| Range assignment loop | `vminfo_parser/analyzer.py:get_disk_space()` | Task 3 |
| Range sorting helper pattern | `vminfo_parser/analyzer.py:sort_by_disk_space_range()` | Task 3 |
| `@plotter` decorator and `_GRAPH_METHOD_NAMES` | `vminfo_parser/visualizer.py` | Task 4 |
| Generic range table rendering | `vminfo_parser/clioutput.py:print_formatted_disk_space()` | Task 5 |
| Report orchestration pattern | `vminfo_parser/__main__.py:get_disk_space_ranges()` | Task 5 |
| Parametrized report registration | `tests/const.py:MAIN_FUNCTION_CALLS` | Task 5 |
| Analyzer test helper pattern | `tests/unit/test_analyzer.py:TestGranularOsCounts._configure()` | Task 6 |

### Test Value Allowlist

| Test name | Bug detected | Minimal mutant | Contract type |
|-----------|--------------|----------------|---------------|
| `test_generate_memory_ranges_all_tiers` | Highest tier omitted when max > 256 | Hard-code fewer tier tuples | public |
| `test_generate_memory_ranges_caps_at_max` | Final tier exceeds data max | Remove upper-bound capping | public |
| `test_calculate_memory_ranges_drops_empty` | Empty buckets appear in output | Remove the non-empty range filter | public |
| `test_get_memory_ranges_assigns_labels` | VMs map to wrong labels | Remove or alter the range-label assignment loop | public |
| `test_get_memory_ranges_count_filter_collapses_other` | `--minimum-count` is ignored | Remove the below-threshold collapse logic | public |
| `test_get_memory_ranges_env_both` | Environment split output is wrong | Remove the `groupby(...).unstack()` path | public |
| `test_get_memory_ranges_sorted_ascending` | Output order is not by memory range | Remove sort-key ordering | public |
| `test_get_memory_ranges_all_env_uses_horizontal_chart` | Main helper routes `all` env to wrong chart method | Swap horizontal/vertical branch | public |
| `test_get_memory_ranges_split_env_uses_vertical_chart` | Main helper routes split env to wrong chart method | Remove non-`all` visualizer branch | public |
| `test_get_memory_ranges_no_graphs` | Visualizer is used when graphing is disabled | Remove the `if visualizer` guard | public |
| `test_visualize_memory_ranges_horizontal` | Horizontal graph method does not render a valid figure | Return before plotting or omit `barh()` | public |
| `test_plotter_saves_memory_ranges` | Report slug mapping is missing or wrong | Remove `_GRAPH_METHOD_NAMES` entry | public |

## KEY FILES REFERENCE

| File | Purpose |
|------|---------|
| `vminfo_parser/config.py` | CLI flags and config validation |
| `vminfo_parser/analyzer.py` | Report aggregation logic and disk-space range template |
| `vminfo_parser/visualizer.py` | Graph rendering, `@plotter`, and PNG naming |
| `vminfo_parser/__main__.py` | Report orchestration and `run_enabled_reports()` |
| `vminfo_parser/clioutput.py` | Terminal table rendering reused for range reports |
| `vminfo_parser/vmdata.py` | Data normalization and environment categorization |
| `tests/const.py` | Parametrized main-function registration and argparse expectations |
| `tests/unit/conftest.py` | Shared mock config defaults |
| `tests/unit/test_analyzer.py` | Analyzer behavior tests |
| `tests/unit/test_main.py` | CLI orchestration tests |
| `tests/unit/test_visualizer.py` | Visualizer tests |
| `README.md` | User-facing CLI documentation |
| `agent_planning/openspec/specs/vm-reporting-cli/spec.md` | Existing living CLI behavior contract |

## STOP RULES

- Stop after the 10 tasks below. Do not add side quests.
- Stop after implementing the requested memory-range report. Do not refactor
  unrelated disk, OS, density, NIC, or overcommit code.
- Stop after one clean test run per task unless the run fails.
- Do not add new third-party dependencies.

---

## TASKS

### Task 1: Add OpenSpec delta for memory ranges CLI

**INTENT:** Extend the existing CLI behavior contract before code changes so the
new flag and its expected behavior are captured in the spec workflow.

**STRUCTURE:**
- Create or update OpenSpec change set:
  `agent_planning/openspec/changes/add-memory-ranges-cli-report/`
- Required files in that change set:
  - `proposal.md`
  - `tasks.md`
  - `specs/vm-reporting-cli/spec.md`
- Add scenarios for:
  - `--get-memory-ranges` flag visibility
  - predefined memory tiers with trimmed upper bound
  - empty middle buckets being omitted
  - `--sort-by-env both` split output
  - missing `--prod-env-labels` error path when split output is requested
  - graph filename `get-memory-ranges.png`

**CONTEXT:**
- Existing living spec:
  `agent_planning/openspec/specs/vm-reporting-cli/spec.md`
- This is a public CLI interface change in a spec-covered codebase, so the
  delta spec must exist before implementation and be archived in the final task.

**CONSTRAINTS:**
- Modify only `agent_planning/openspec/changes/add-memory-ranges-cli-report/`
- Keep scenarios in GIVEN/WHEN/THEN format
- Do not modify the live spec in `agent_planning/openspec/specs/` directly in
  this task; only the change-set delta belongs here

**DON'T:**
- Don't edit Python source files in this task
- Don't invent CLI behaviors that the plan does not implement
- Don't skip the error-path scenario for missing prod labels

**VERIFICATION:**
```text
⚠️ UNTESTED OPENSpec proposal: /opsx:propose add memory ranges CLI report
PASS: change set exists at agent_planning/openspec/changes/add-memory-ranges-cli-report/
FAIL: no change set or missing delta spec files

⚠️ UNTESTED SPEC CHECK: rg 'get-memory-ranges|prod-env-labels|Memory Range|get-memory-ranges.png' agent_planning/openspec/changes/add-memory-ranges-cli-report
PASS: all requested behaviors are represented in the delta spec
FAIL: one or more behaviors are missing

DEVLOG: Update agent_planning/execution/add_memory_ranges/devlogs/add_memory_ranges_2026-09-22.md
```

---

### Task 2: Add `--get-memory-ranges` CLI flag

**INTENT:** Register the new additive report flag so argparse and `Config`
expose it to the report runner.

**STRUCTURE:**
- **`vminfo_parser/config.py`**
  - Add `--get-memory-ranges` as `action="store_true"`, `default=False`
  - Help text:
    `"Break down VMs by allocated memory into predefined GiB ranges. Works with --minimum-count, --sort-by-env, and --generate-graphs."`
  - Place the argument immediately after `--get-disk-space-ranges` so the two
    range-report flags stay adjacent

**CONTEXT:**
- Mirror the structure of `--get-disk-space-ranges` in the same file
- DR-5 fixed the flag name as `--get-memory-ranges`

**CONSTRAINTS:**
- Modify only `vminfo_parser/config.py`
- Do not add new validation rules in `_validate()` for this flag
- Complexity ≤15 per function

**DON'T:**
- Don't modify any other files in this task
- Don't add side behavior beyond registering the flag
- Don't use abbreviated identifiers (`cat`, `cfg`, `msg`, `fname`, `idx`,
  `res`, `tmp`)
- Don't produce functions exceeding 15 cyclomatic complexity
- Don't add a function whose body is a single dict/attribute lookup unless it
  earns its hop (CQ4.1)
- Don't leave helpers with zero callers

**VERIFICATION:**
```text
CONTEXT7 CHECK:
  N/A — argparse is stdlib and this task introduces no external library API usage.
PASS: no new library uncertainty introduced

⚠️ UNTESTED BUILD: python -c "from vminfo_parser.config import Config; parser_config = Config.from_args('--file', '/dev/null', '--get-memory-ranges'); assert parser_config.get_memory_ranges is True"
PASS: import succeeds and attribute is True
FAIL: ImportError, AttributeError, or assertion failure

⚠️ UNTESTED COMPLEXITY CHECK: agent_planning/scripts/quality_gate.sh vminfo_parser/config.py
PASS: exits 0
FAIL: exits non-zero

⚠️ UNTESTED MAINTAINABILITY CHECK: agent_planning/scripts/readability_lint.py vminfo_parser/config.py
PASS: exits 0; no packed one-liners introduced
FAIL: exits non-zero

⚠️ UNTESTED NAMING CHECK: agent_planning/scripts/readability_lint.py vminfo_parser/config.py
PASS: exits 0
FAIL: exits non-zero

⚠️ UNTESTED DRY CHECK: rg 'get_memory_ranges' vminfo_parser/config.py
PASS: exactly one new config flag registration
FAIL: duplicated flag registration or dead helpers found

CODE REVIEW:
  agent_planning/scripts/secret_scan.sh vminfo_parser/config.py
  PASS: exits 0
  FAIL: exits 1 — fix before marking done
  Verify against EXECUTION_PROTOCOL.md Section 9 checklist before marking done.

DEVLOG: Update devlog with exact command output.
```

---

### Task 3: Add memory range logic to analyzer

**INTENT:** Implement the bucketing, label assignment, filtering, and
range-ordering logic while keeping each method small enough to satisfy the
complexity budget.

**STRUCTURE:**
- **`vminfo_parser/analyzer.py`** — add these methods to `Analyzer`:

  1. `generate_memory_ranges(self, max_memory: int) -> list[tuple[int, int]]`
     - Define exact base tiers:
       `(0, 4), (5, 8), (9, 16), (17, 32), (33, 64), (65, 128), (129, 256), (257, max_memory)`
     - Iterate in order
     - Stop when `lower > max_memory`
     - If `upper > max_memory`, cap that tuple to `(lower, max_memory)`
     - Return trimmed ranges in ascending order

  2. `calculate_memory_ranges(self, dataframe: pd.DataFrame | None = None) -> list[tuple[int, int]]`
     - Default to `self.vm_data.df` when `dataframe` is `None`
     - Resolve `memory_heading = self.vm_data.column_headers["vmMemory"]`
     - Clean string values by removing commas and whitespace, then convert with
       `pd.to_numeric(..., errors="coerce")`
     - If the dataframe is empty or the cleaned memory column contains no valid
       numeric values, return `[]`
     - Compute `max_memory = int(dataframe[memory_heading].max())`
     - Call `self.generate_memory_ranges(max_memory)`
     - Keep only ranges that contain at least one VM using exact inclusive
       bounds (`>= lower` and `<= upper`) with no epsilon

  3. `_collapse_memory_range_counts(self, counts: pd.DataFrame) -> pd.DataFrame`
     - Return `counts` unchanged when `self.config.count_filter` is `None`
     - For `environment_filter == "both"`:
       - add temporary `total` column = row sum
       - collect rows where `total < self.config.count_filter`
       - collapse to `Other` only when more than one row is below threshold
       - drop the temporary `total` column before returning
     - For `environment_filter == "all"`:
       - use the `Count` column for thresholding
       - collapse more than one below-threshold row to `Other`
     - For `prod` / `non-prod`:
       - use the single environment column for thresholding
       - collapse more than one below-threshold row to `Other`

  4. `sort_by_memory_range(self, dataframe: pd.DataFrame) -> pd.DataFrame`
     - Resolve `environment_heading = self.vm_data.column_headers["environment"]`
     - Build counts by `self.config.environment_filter`:
       - `all`: `dataframe["Memory Range"].value_counts().to_frame("Count")`
       - `both`: `dataframe.groupby(["Memory Range", environment_heading]).size().unstack(fill_value=0)`
       - `prod` / `non-prod`: filter to that environment first, then the same
         `groupby(...).unstack(fill_value=0)` pattern
     - Pass the counts through `_collapse_memory_range_counts()`
     - Add `sort_key` from the upper bound in the index label
     - Sort ascending by `sort_key`
     - Drop `sort_key`

  5. `get_memory_ranges(self) -> pd.DataFrame`
     - Call `self.vm_data.create_environment_filtered_dataframe(
       self.config.environments, env_filter=self.config.environment_filter)`
     - If the filtered dataframe is empty, return `pd.DataFrame()`
     - Clean the memory column with the same `pd.to_numeric` path used by
       `calculate_memory_ranges()`
     - Call `self.calculate_memory_ranges(dataframe=dataframe)`
     - If no ranges are returned, return `pd.DataFrame()`
     - For each `(lower, upper)` range, assign
       `f"{lower}-{upper} GiB"` into a new `Memory Range` column using exact
       inclusive bounds
     - Return `self.sort_by_memory_range(dataframe)`

**CONTEXT:**
- `generate_dynamic_ranges()` and `calculate_disk_space_ranges()` are the
  templates for dynamic trimming and bucket filtering
- `sort_by_disk_space_range()` is the template for environment-dependent
  grouping and explicit range sorting
- **Divergence from `calculate_disk_space_ranges()`:** disk space uses an
  `epsilon` around range edges; memory does **not**. Memory is normalized to
  integer GiB, so exact inclusive bounds are safer and prevent adjacent empty
  buckets from being falsely marked as populated
- DR-1 fixes the predefined+trimmed strategy; DR-2 fixes exact boundaries;
  DR-3 requires environment-split support
- context7 pandas confirmed: `groupby(...).size().unstack(fill_value=0)`,
  `value_counts()`, `pd.to_numeric(..., errors="coerce")`, and explicit
  `sort_values()` are the appropriate patterns

**CONSTRAINTS:**
- Modify only `vminfo_parser/analyzer.py`
- Do not modify existing disk-space, OS-count, density, NIC, or overcommit
  methods
- Do not add new imports
- Complexity ≤15 per function
- DR-2 boundaries are exact — do not deviate
- Keep `get_memory_ranges()` thin; do not absorb sorting and count-filter logic
  into one large method

**DON'T:**
- Don't copy-paste the full body of `sort_by_disk_space_range()`
- Don't add TB conversion logic for memory
- Don't use epsilon-based boundary tests for memory buckets
- Don't add a per-OS memory breakdown
- Don't create speculative wrappers or zero-caller helpers
- Don't use abbreviated identifiers (`cat`, `cfg`, `msg`, `fname`, `idx`,
  `res`, `tmp`)
- Don't produce functions exceeding 15 cyclomatic complexity
- Don't use nested comprehensions or nested ternaries

**VERIFICATION:**
```text
CONTEXT7 CHECK:
  Confirm pandas groupby/unstack/value_counts/to_numeric patterns still match the plan.
PASS: no API-DRIFT
FAIL: docs require a different pattern

⚠️ UNTESTED BUILD: python -c "from vminfo_parser.analyzer import Analyzer; print('OK')"
PASS: imports succeed
FAIL: ImportError or SyntaxError

⚠️ UNTESTED COMPLEXITY CHECK: agent_planning/scripts/quality_gate.sh vminfo_parser/analyzer.py
PASS: exits 0
FAIL: exits non-zero

⚠️ UNTESTED MAINTAINABILITY CHECK: agent_planning/scripts/readability_lint.py vminfo_parser/analyzer.py
PASS: exits 0; human read finds no packed one-liners
FAIL: exits non-zero

⚠️ UNTESTED NAMING CHECK: agent_planning/scripts/readability_lint.py vminfo_parser/analyzer.py
PASS: exits 0
FAIL: exits non-zero

⚠️ UNTESTED DRY CHECK: rg 'get_memory_ranges|generate_memory_ranges|calculate_memory_ranges|sort_by_memory_range|Memory Range' vminfo_parser/
PASS: one analyzer path per concern; no duplicated mini-wrappers
FAIL: duplicated logic or dead helpers found

CODE REVIEW:
  agent_planning/scripts/secret_scan.sh vminfo_parser/analyzer.py
  PASS: exits 0
  FAIL: exits 1 — fix before marking done
  Verify against EXECUTION_PROTOCOL.md Section 9 checklist before marking done.

DEVLOG: Update devlog with exact command output.
```

---

### Task 4: Add memory range visualization

**INTENT:** Add chart methods that mirror the current disk-space report
patterns so users get consistent graph behavior.

**STRUCTURE:**
- **`vminfo_parser/visualizer.py`**
  - Add to `_GRAPH_METHOD_NAMES`:
    - `"visualize_memory_ranges_horizontal": "get-memory-ranges"`
    - `"visualize_memory_ranges_vertical": "get-memory-ranges"`
  - Add `visualize_memory_ranges_horizontal(self, dataframe: pd.DataFrame) -> None`
    - Decorate with `@plotter`
    - Follow the exact data-shape handling pattern from
      `visualize_disk_space_horizontal()`:
      - copy dataframe
      - if it has multiple columns, sum across axis 1 to get one count per range
    - Plot one horizontal bar per memory-range label
    - Set:
      - title: `"VM Memory Allocation Breakdown"`
      - x label: `"Number of VMs"`
      - y label: `"Memory Range"`
      - x-axis formatter: `ticker.ScalarFormatter()`
  - Add `visualize_memory_ranges_vertical(self, dataframe: pd.DataFrame) -> None`
    - Decorate with `@plotter`
    - Use `dataframe.plot(kind="bar", stacked=False, figsize=(12, 8), rot=45)`
    - Set:
      - title: `"VM Memory Ranges by Environment"`
      - x label: `"Memory Range"`
      - y label: `"Number of VMs"`

**CONTEXT:**
- `visualize_disk_space_horizontal()` and `visualize_disk_space_vertical()` are
  the direct templates for these methods
- DR-4 fixed the expected graph shapes: horizontal for `all`, grouped vertical
  for split-environment output
- context7 matplotlib confirmed `Axes.barh()` and grouped `plot(kind="bar")`
  are the correct primitives here

**CONSTRAINTS:**
- Modify only `vminfo_parser/visualizer.py`
- Do not add new imports
- Do not modify existing visualization methods
- Complexity ≤15 per function

**DON'T:**
- Don't modify analyzer or main orchestration in this task
- Don't add stacked bars, pie charts, or alternate chart modes
- Don't use nested comprehensions or dense one-liners
- Don't use abbreviated identifiers
- Don't produce functions exceeding 15 cyclomatic complexity
- Don't add helpers with zero callers

**VERIFICATION:**
```text
CONTEXT7 CHECK:
  Confirm barh and grouped bar patterns still match matplotlib docs.
PASS: no API-DRIFT
FAIL: docs require a different plotting primitive

⚠️ UNTESTED BUILD: python -c "from vminfo_parser.visualizer import Visualizer; print('OK')"
PASS: imports succeed
FAIL: ImportError or SyntaxError

⚠️ UNTESTED COMPLEXITY CHECK: agent_planning/scripts/quality_gate.sh vminfo_parser/visualizer.py
PASS: exits 0
FAIL: exits non-zero

⚠️ UNTESTED MAINTAINABILITY CHECK: agent_planning/scripts/readability_lint.py vminfo_parser/visualizer.py
PASS: exits 0; human read finds no packed one-liners
FAIL: exits non-zero

⚠️ UNTESTED NAMING CHECK: agent_planning/scripts/readability_lint.py vminfo_parser/visualizer.py
PASS: exits 0
FAIL: exits non-zero

⚠️ UNTESTED DRY CHECK: rg 'visualize_memory_ranges|get-memory-ranges' vminfo_parser/
PASS: two visualization methods and two report-slug mappings, no dead helpers
FAIL: duplicated plotting logic or dead helpers found

CODE REVIEW:
  agent_planning/scripts/secret_scan.sh vminfo_parser/visualizer.py
  PASS: exits 0
  FAIL: exits 1 — fix before marking done
  Verify against EXECUTION_PROTOCOL.md Section 9 checklist before marking done.

DEVLOG: Update devlog with exact command output.
```

---

### Task 5: Wire the report into CLI execution and shared test constants

**INTENT:** Connect the new analyzer and visualizer methods to the existing
report runner and register the flag in shared test defaults.

**STRUCTURE:**
- **`vminfo_parser/__main__.py`**
  - Add:
    `get_memory_ranges(config: Config, analyzer: Analyzer, cli_output: CLIOutput, visualizer: Visualizer | None) -> None`
  - Behavior:
    - call `memory_range_dataframe = analyzer.get_memory_ranges()`
    - if the dataframe is not empty:
      - call `cli_output.print_formatted_disk_space(memory_range_dataframe)`
      - if `visualizer` is present:
        - `environment_filter == "all"` → `visualizer.visualize_memory_ranges_horizontal(memory_range_dataframe)`
        - otherwise → `visualizer.visualize_memory_ranges_vertical(memory_range_dataframe)`
  - Register the report in `run_enabled_reports()` immediately after the
    `get_disk_space_ranges` block

- **`tests/const.py`**
  - Add to `MAIN_FUNCTION_CALLS`:
    - `"get_memory_ranges": ["config", "analyzer", "cli_output", "visualizer"]`
  - Add to `EXPECTED_ARGPARSE_TO_YAML`:
    - `"get_memory_ranges": False`

- **`tests/unit/conftest.py`**
  - Add `("get_memory_ranges", False)` to the mock config default set

**CONTEXT:**
- `get_disk_space_ranges()` is the direct orchestration template
- `print_formatted_disk_space()` is reusable despite its name because it already
  formats range-indexed DataFrames generically
- `test_main_funcs` and `test_main_funcs_no_graphs` in `tests/unit/test_main.py`
  already rely on `MAIN_FUNCTION_CALLS`, so the test-constants update is part
  of the wiring task rather than a test-only concern

**CONSTRAINTS:**
- Modify only `vminfo_parser/__main__.py`, `tests/const.py`, and
  `tests/unit/conftest.py`
- Do not add new imports to `__main__.py`
- Do not modify unrelated report functions
- Complexity ≤15 per function

**DON'T:**
- Don't modify `CLIOutput`
- Don't change `run_enabled_reports()` ordering beyond inserting the new report
- Don't create speculative helper wrappers
- Don't use abbreviated identifiers
- Don't produce functions exceeding 15 cyclomatic complexity

**VERIFICATION:**
```text
CONTEXT7 CHECK:
  N/A — this task wires existing internal APIs and introduces no new external library usage.
PASS: no new library uncertainty introduced

⚠️ UNTESTED BUILD: python -c "from vminfo_parser.__main__ import get_memory_ranges; print('OK')"
PASS: import succeeds
FAIL: ImportError or SyntaxError

⚠️ UNTESTED TESTS: python -m pytest tests/unit/test_main.py -x -v
PASS: existing main tests pass, including parametrized registration coverage
FAIL: any test fails

⚠️ UNTESTED COMPLEXITY CHECK: agent_planning/scripts/quality_gate.sh vminfo_parser/__main__.py tests/const.py tests/unit/conftest.py
PASS: exits 0
FAIL: exits non-zero

⚠️ UNTESTED MAINTAINABILITY CHECK: agent_planning/scripts/readability_lint.py vminfo_parser/__main__.py tests/const.py tests/unit/conftest.py
PASS: exits 0; human read finds no packed one-liners
FAIL: exits non-zero

⚠️ UNTESTED NAMING CHECK: agent_planning/scripts/readability_lint.py vminfo_parser/__main__.py
PASS: exits 0
FAIL: exits non-zero

⚠️ UNTESTED DRY CHECK: rg 'get_memory_ranges' vminfo_parser/ tests/
PASS: exactly one analyzer entrypoint, one main helper, and expected test registrations
FAIL: duplicated orchestration or dead wrappers found

CODE REVIEW:
  agent_planning/scripts/secret_scan.sh vminfo_parser/__main__.py tests/const.py tests/unit/conftest.py
  PASS: exits 0
  FAIL: exits 1 — fix before marking done
  Verify against EXECUTION_PROTOCOL.md Section 9 checklist before marking done.

DEVLOG: Update devlog with exact command output.
```

---

### Task 6: Add analyzer unit tests for memory ranges

**INTENT:** Add the allowlisted analyzer tests that validate tier generation,
empty-bucket suppression, ordering, environment splits, and count filtering.

**STRUCTURE:**
- **`tests/unit/test_analyzer.py`**
  - Add class `TestMemoryRanges`
  - Add helper `_configure(self, analyzer: Analyzer, rows: dict[str, list[object]], environment_filter: str = "all", count_filter: int | None = None) -> Analyzer`
    - set `analyzer.vm_data.create_environment_filtered_dataframe.return_value = pd.DataFrame(rows)`
    - set `analyzer.vm_data.column_headers = {"vmMemory": "Memory", "environment": "Environment"}`
    - set `analyzer.config.environment_filter = environment_filter`
    - set `analyzer.config.count_filter = count_filter`
    - return `analyzer`
  - Add exact tests:
    - `test_generate_memory_ranges_all_tiers`
    - `test_generate_memory_ranges_caps_at_max`
    - `test_calculate_memory_ranges_drops_empty`
    - `test_get_memory_ranges_assigns_labels`
    - `test_get_memory_ranges_count_filter_collapses_other`
    - `test_get_memory_ranges_env_both`
    - `test_get_memory_ranges_sorted_ascending`
  - Exact row shapes:
    - `test_calculate_memory_ranges_drops_empty` uses `Memory: [2, 2, 32, 32]`
    - `test_get_memory_ranges_assigns_labels` uses
      `Memory: [2, 8, 16, 64]` and `Environment: ["prod"] * 4`
    - `test_get_memory_ranges_count_filter_collapses_other` uses a controlled
      mix where two or more ranges fall below threshold and should collapse to
      `Other`
    - `test_get_memory_ranges_env_both` uses already categorized environment
      values `["prod", "non-prod", "prod"]` because the mocked return value
      bypasses `_categorize_environment()`
    - `test_get_memory_ranges_sorted_ascending` asserts an exact ordered index
      list for a controlled input, not just first-vs-last

**CONSTRAINTS:**
- Modify only `tests/unit/test_analyzer.py`
- Use the existing `analyzer` fixture and `NonCallableMagicMock` pattern
- Every test must match the Test Value allowlist above

**DON'T:**
- Don't write any test not named in this task's STRUCTURE / allowlist
- Don't add parameterized expansions or mirror tests for private helpers
- Don't assert incidental formatting
- Don't use abbreviated identifiers
- Don't produce functions exceeding 15 cyclomatic complexity

**STOP RULES:**
- Stop after implementing the 7 allowlisted tests
- If a missing important case is discovered, stop and amend the plan instead of
  freelancing more tests

**VERIFICATION:**
```text
CONTEXT7 CHECK:
  N/A — tests exercise planned internal behavior and introduce no new external library usage.
PASS: no new library uncertainty introduced

⚠️ UNTESTED TESTS: python -m pytest tests/unit/test_analyzer.py::TestMemoryRanges -x -v
PASS: all allowlisted analyzer tests pass
FAIL: any test fails

⚠️ UNTESTED COMPLEXITY CHECK: agent_planning/scripts/quality_gate.sh tests/unit/test_analyzer.py
PASS: exits 0
FAIL: exits non-zero

⚠️ UNTESTED MAINTAINABILITY CHECK: agent_planning/scripts/readability_lint.py tests/unit/test_analyzer.py
PASS: exits 0; human read finds no mock-theater or packed assertions
FAIL: exits non-zero

⚠️ UNTESTED NAMING CHECK: agent_planning/scripts/readability_lint.py tests/unit/test_analyzer.py
PASS: exits 0
FAIL: exits non-zero

⚠️ UNTESTED DRY CHECK: rg 'TestMemoryRanges|get_memory_ranges' tests/unit/test_analyzer.py
PASS: exactly the allowlisted tests exist; no stray helpers or duplicate cases
FAIL: unplanned tests or duplicate patterns found

CODE REVIEW:
  agent_planning/scripts/secret_scan.sh tests/unit/test_analyzer.py
  PASS: exits 0
  FAIL: exits 1 — fix before marking done
  Verify against EXECUTION_PROTOCOL.md Section 9 checklist before marking done.

CQ11 CONFORMANCE:
  verify written tests match the allowlist exactly; delete any strays immediately

DEVLOG: Update devlog. Record the final allowlist.
```

---

### Task 7: Add main-helper and visualizer unit tests

**INTENT:** Add the allowlisted tests that cover the orchestration branches and
the user-visible report slug for saved graphs.

**STRUCTURE:**
- **`tests/unit/test_main.py`** — add:
  - `test_get_memory_ranges_all_env_uses_horizontal_chart`
    - mock analyzer / cli_output / visualizer / config
    - set `config.environment_filter = "all"`
    - set `analyzer.get_memory_ranges.return_value.empty = False`
    - assert horizontal visualizer method called and vertical method not called
  - `test_get_memory_ranges_split_env_uses_vertical_chart`
    - same setup, but set `config.environment_filter = "both"`
    - assert vertical visualizer method called and horizontal method not called
  - `test_get_memory_ranges_no_graphs`
    - pass `visualizer=None`
    - assert CLI output still runs and no visualizer access occurs

- **`tests/unit/test_visualizer.py`** — add:
  - fixture `memory_range_dataframe`:
    `pd.DataFrame({"Count": [100, 500, 300, 50]}, index=pd.Index(["0-4 GiB", "5-8 GiB", "9-16 GiB", "17-32 GiB"], name="Memory Range"))`
  - `test_visualize_memory_ranges_horizontal`
    - call `visualizer.visualize_memory_ranges_horizontal(memory_range_dataframe)`
    - assert a `Figure` is returned in test mode
    - assert the title contains `VM Memory Allocation Breakdown`
    - assert the figure has one axes object with rendered patches
  - `test_plotter_saves_memory_ranges`
    - `monkeypatch` test mode off
    - create `Visualizer(Config(get_memory_ranges=True, graph_output_dir=tmp_path))`
    - call `visualize_memory_ranges_horizontal(memory_range_dataframe)`
    - assert `tmp_path / "get-memory-ranges.png"` exists

**CONSTRAINTS:**
- Modify only `tests/unit/test_main.py` and `tests/unit/test_visualizer.py`
- Follow existing test style already used in these files
- Keep assertions focused on public behavior and deterministic figure metadata

**DON'T:**
- Don't write any test not named in this task's STRUCTURE / allowlist
- Don't add extra figure-baseline files or new snapshot directories
- Don't modify unrelated existing tests
- Don't use abbreviated identifiers
- Don't produce functions exceeding 15 cyclomatic complexity

**STOP RULES:**
- Stop after implementing the 5 allowlisted tests
- If the figure-level assertions prove unstable, stop and amend the plan rather
  than adding broad snapshot coverage

**VERIFICATION:**
```text
CONTEXT7 CHECK:
  N/A — tests cover internal orchestration and existing plotting APIs already validated in prior tasks.
PASS: no new library uncertainty introduced

⚠️ UNTESTED TESTS: python -m pytest tests/unit/test_main.py tests/unit/test_visualizer.py -x -v
PASS: all allowlisted tests pass
FAIL: any test fails

⚠️ UNTESTED COMPLEXITY CHECK: agent_planning/scripts/quality_gate.sh tests/unit/test_main.py tests/unit/test_visualizer.py
PASS: exits 0
FAIL: exits non-zero

⚠️ UNTESTED MAINTAINABILITY CHECK: agent_planning/scripts/readability_lint.py tests/unit/test_main.py tests/unit/test_visualizer.py
PASS: exits 0; human read finds no brittle mock-theater beyond the minimum needed for wiring
FAIL: exits non-zero

⚠️ UNTESTED NAMING CHECK: agent_planning/scripts/readability_lint.py tests/unit/test_main.py tests/unit/test_visualizer.py
PASS: exits 0
FAIL: exits non-zero

⚠️ UNTESTED DRY CHECK: rg 'get_memory_ranges|memory_range_dataframe|get-memory-ranges.png' tests/unit
PASS: exactly the allowlisted tests and one figure fixture exist
FAIL: duplicated test helpers or stray tests found

CODE REVIEW:
  agent_planning/scripts/secret_scan.sh tests/unit/test_main.py tests/unit/test_visualizer.py
  PASS: exits 0
  FAIL: exits 1 — fix before marking done
  Verify against EXECUTION_PROTOCOL.md Section 9 checklist before marking done.

CQ11 CONFORMANCE:
  verify written tests match the allowlist exactly; delete any strays immediately

DEVLOG: Update devlog. Record the final allowlist.
```

---

### Task 8: Functional CLI validation

**INTENT:** Exercise the new public CLI entrypoint through the real shell
interface, covering one happy path and one error path.

**STRUCTURE:**
1. Create a minimal fixture CSV at:
   `agent_planning/execution/add_memory_ranges/artifacts/functional_cli/memory_ranges_fixture.csv`
2. Use these exact rows in the fixture:
   - `VM OS,Environment,VM MEM (GB),VM Provisioned (GB),VM CPU`
   - `Ubuntu Linux,Prod,2,100,1`
   - `Ubuntu Linux,Dev,8,100,1`
   - `Red Hat Enterprise Linux,Prod,32,100,2`
   - `Microsoft Windows Server,Prod,64,100,2`
   - `Microsoft Windows Server,Dev,64,100,2`
   - `Oracle Linux,Dev,300,100,4`
3. Happy path command:
   - run the CLI with
     `--get-memory-ranges --sort-by-env both --prod-env-labels Prod --generate-graphs`
     and write graphs to
     `agent_planning/execution/add_memory_ranges/artifacts/functional_cli/graphs/`
4. Error path command:
   - run the CLI with `--get-memory-ranges --sort-by-env both` and omit
     `--prod-env-labels`

**CONTEXT:**
- This task satisfies software addendum §S5: dedicated functional testing for a
  production-facing CLI entrypoint
- The fixture intentionally exercises:
  - small VM tier (`0-4 GiB`)
  - boundary-adjacent tier (`5-8 GiB`)
  - mid-size tier (`17-32 GiB`)
  - repeated tier counts (`33-64 GiB`)
  - capped top tier (`257-300 GiB`)

**CONSTRAINTS:**
- Modify only runtime artifacts under
  `agent_planning/execution/add_memory_ranges/artifacts/functional_cli/`
- Do not change source files in this task
- Use the exact fixture rows above

**DON'T:**
- Don't use the Python API directly; invoke the CLI via `python -m vminfo_parser`
- Don't broaden the fixture beyond the six rows listed above
- Don't create temporary files outside the execution artifacts tree

**VERIFICATION:**
```text
⚠️ UNTESTED HAPPY PATH:
python -m vminfo_parser \
  --file agent_planning/execution/add_memory_ranges/artifacts/functional_cli/memory_ranges_fixture.csv \
  --get-memory-ranges \
  --sort-by-env both \
  --prod-env-labels Prod \
  --generate-graphs \
  --graph-output-dir agent_planning/execution/add_memory_ranges/artifacts/functional_cli/graphs
PASS: stdout includes 'Memory Range', 'prod', 'non-prod', and the PNG file agent_planning/execution/add_memory_ranges/artifacts/functional_cli/graphs/get-memory-ranges.png exists
FAIL: non-zero exit code, missing expected labels, or missing PNG

⚠️ UNTESTED ERROR PATH:
python -m vminfo_parser \
  --file agent_planning/execution/add_memory_ranges/artifacts/functional_cli/memory_ranges_fixture.csv \
  --get-memory-ranges \
  --sort-by-env both
PASS: exits non-zero and reports that production environment labels were not provided
FAIL: exits 0 or omits the validation error

DEVLOG: Copy the exact command output into the devlog. Do NOT paraphrase or abbreviate with '...'.
```

---

### Task 9: Code Review — Full Quality Gate

**INTENT:** Perform the mandatory penultimate review of all implementation and
test work before documentation/spec archival.

**STRUCTURE:**
1. **Secret scan:** `agent_planning/scripts/secret_scan.sh vminfo_parser/ tests/`
2. **Complexity gate:** `agent_planning/scripts/quality_gate.sh vminfo_parser/analyzer.py vminfo_parser/visualizer.py vminfo_parser/__main__.py vminfo_parser/config.py tests/unit/test_analyzer.py tests/unit/test_main.py tests/unit/test_visualizer.py`
3. **Readability lint:** `agent_planning/scripts/readability_lint.py vminfo_parser/analyzer.py vminfo_parser/visualizer.py vminfo_parser/__main__.py tests/unit/test_analyzer.py tests/unit/test_main.py tests/unit/test_visualizer.py`
4. **Full test suite:** `python -m pytest tests/ -x -v`
5. **Functional evidence check:** confirm Task 8 happy-path and error-path outputs are copied into the devlog
6. **Security & Operations review:** hardcoded secrets, error handling, idempotency, orphaned artifacts
7. **Complexity review (CQ2):** every new function ≤15 cyclomatic complexity
8. **Maintainability review (CQ3):** no nested comprehensions, no packed one-liners, no >2 chained calls without assignment
9. **Naming review (CQ12):** read every new identifier aloud; rename lazy abbreviations
10. **DRY review (CQ4):** `rg 'get_memory_ranges|generate_memory_ranges|calculate_memory_ranges|sort_by_memory_range|visualize_memory_ranges|Memory Range' vminfo_parser/ tests/`
11. **Fragility review (CQ5):** empty dataframe behavior, all-NaN memory behavior, environment split assumptions, graph-output path handling
12. **Context7 review (CQ1):** confirm pandas/matplotlib usage still matches current docs
13. **Test Value review (CQ11):** confirm the written tests equal the allowlist exactly

REQUIRED OUTPUT:
```
| # | File | Line | Rule | Finding | Status |
|---|------|------|------|---------|--------|
```
Summary: total findings and PASS/FAIL/ADVISORY counts.

**CONSTRAINTS:**
- Review these exact files:
  - `vminfo_parser/config.py`
  - `vminfo_parser/analyzer.py`
  - `vminfo_parser/visualizer.py`
  - `vminfo_parser/__main__.py`
  - `tests/const.py`
  - `tests/unit/conftest.py`
  - `tests/unit/test_analyzer.py`
  - `tests/unit/test_main.py`
  - `tests/unit/test_visualizer.py`
- Do not skip any review category above

**STOP RULES:**
- Model Switch Pause: All implementation tasks complete. Ready for the Code Review task.
  Ask the user whether to switch models before running review.

**DON'T:**
- Don't add features or refactor outside the task scope
- Don't weaken assertions or change production code to force a green suite

**VERIFICATION:**
```text
All 13 review steps completed.
Findings table produced.
All FAIL findings resolved before proceeding to Task 10.

DEVLOG: Update devlog with the findings table and exact command output.
```

---

### Task 10: Doc Update and OpenSpec Archive

**INTENT:** Update user-facing documentation and persist the new CLI behavior
into the living spec.

**STRUCTURE:**
1. **Documentation update**
   - Update `README.md` to document `--get-memory-ranges`
   - Search `AGENTS.md`, `agent_planning/AGENTS.md`, and `docs/` for stale CLI
     references; update only files that actually mention related flags or usage
2. **OpenSpec archive**
   - Run `/opsx:archive`
   - Verify the new memory-range scenarios land in
     `agent_planning/openspec/specs/vm-reporting-cli/spec.md`

**CONTEXT:**
```bash
⚠️ UNTESTED DOC DISCOVERY: rg -l 'get-disk-space-ranges|get-granular-os-counts|minimum-count|sort-by-env' README.md AGENTS.md agent_planning/AGENTS.md docs/ 2>/dev/null
```
- Use the search results to identify stale docs
- The final archive step is mandatory because this is a spec-covered codebase

**CONSTRAINTS:**
- Modify only documentation files surfaced by the discovery search and the live
  OpenSpec file updated by `/opsx:archive`
- Do not modify Python source files in this task
- Match existing documentation style

**DON'T:**
- Don't create new documentation files unless the discovery search finds no
  existing home for the flag documentation
- Don't leave the OpenSpec change set unarchived
- Don't restructure docs beyond the sections that need flag updates

**VERIFICATION:**
```text
⚠️ UNTESTED DOC CHECK: rg 'get-memory-ranges' README.md AGENTS.md agent_planning/AGENTS.md docs/ 2>/dev/null
PASS: the new flag is documented in the relevant user-facing docs
FAIL: no documentation match found

⚠️ UNTESTED SPEC ARCHIVE CHECK: rg 'get-memory-ranges|Memory Range' agent_planning/openspec/specs/vm-reporting-cli/spec.md
PASS: the live spec contains the archived memory-range scenarios
FAIL: the live spec was not updated

DEVLOG: Finalize devlog — replace Remaining Tasks with Result / Conclusion / Next Steps.
```
