# File-First Retrieval Pipeline

## Repeatable Stage

- `File-role resolution loop`
  - deterministic orchestration over Qdrant + CGC + file-level scoring
  - file-level
  - owns:
    - `Per-role file candidate assembly`
    - `Cross-role file graph linking`
    - `CGC-based file reranking`
    - `Role ownership selection`
    - `Weak-role upward expansion`
    - `File-level final rerank`
  - may be rerun when later stages show the current file choice is weak, conflicting, or redundant

## Loop Safeguards

- `G1: max resolution rounds`
  - run the `File-role resolution loop` at most once per role in the first implementation
  - default: `MAX_FILE_ROLE_RESOLUTION_ROUNDS = 1`

- `G2: bounded alternates`
  - keep only a small path-diverse alternate pool per role
  - default: `MAX_FILE_ROLE_ALTERNATES = 6`

- `G3: no repeated assignment state`
  - track selected file paths per role
  - if the same assignment appears again, stop rerunning the loop

- `G4: monotonic progress required`
  - a retry must improve at least one of:
    - fewer unresolved required roles
    - stronger owner-path match
    - successful snippet validation inside the selected file
    - reduced cross-role conflict
  - otherwise stop

- `G5: failed file memory`
  - if a file fails snippet validation for a role, downweight or exclude it for that role in the next loop
  - do not retry the same file for the same role unless CGC provides a new owner-level reason

- `G6: conflict repair is single-pass`
  - when one file wins multiple roles, assign it to the best-fitting role first
  - rerun the remaining conflicting roles once, then stop

- `G7: role-owner gate before snippet selection`
  - when a role has an owner-path candidate, adjacent/helper files cannot satisfy that role
  - examples:
    - `checker.ts` blocks `emitter.ts` from satisfying `validation_checking`
    - `emitter.ts` blocks `parser.ts` from satisfying `behavior_output`
    - `parser.ts` blocks `emitter.ts` from satisfying `input_parsing`

- `G8: snippet retries cannot broaden first`
  - if snippet targeting fails, retry file-role resolution before any broader snippet search
  - this keeps file ownership ahead of snippet selection

## Retry Scenarios

- `S1: next-best file fallback`
  - chosen file does not yield a good snippet later
  - rerun file-role resolution with that file downweighted or excluded
  - guarded by: `G1`, `G2`, `G3`, `G5`, `G8`

- `S2: cross-role reassignment`
  - a file fits another role better than the one it currently occupies
  - rerun file-role resolution for both affected roles
  - guarded by: `G1`, `G3`, `G4`, `G6`, `G7`

- `S3: weak-role re-resolution`
  - a role remains weak after file-level or late assessment
  - rerun file-role resolution with stronger owner/upward-expansion bias
  - guarded by: `G1`, `G2`, `G3`, `G4`

- `S4: redundancy correction`
  - two roles end up with near-duplicate adjacent files
  - keep the stronger owner file, rerun the weaker role
  - guarded by: `G3`, `G4`, `G6`, `G7`

- `S5: owner-over-helper retry`
  - selected file looks like helper/support/plumbing rather than owner
  - rerun with stronger caller/owner/exporter bias
  - guarded by: `G1`, `G2`, `G4`, `G7`

- `S6: snippet-failure-triggered retry`
  - file looked plausible, but no strong snippet can be found inside it
  - treat that as evidence against the file and rerun file-role resolution
  - guarded by: `G1`, `G3`, `G5`, `G8`

- `S7: graph-neighborhood retry`
  - a file is promising but weak
  - rerun using its CGC neighborhood as the candidate pool
  - guarded by: `G1`, `G2`, `G4`

- `S8: role conflict retry`
  - one file is top-ranked for multiple roles
  - assign it to the strongest-fitting role first, rerun the others
  - guarded by: `G3`, `G4`, `G6`, `G7`

## Pipeline

- `Policy / retrieval decision`
  - deterministic
  - no file/snippet yet

- `Step-2 issue decomposition and role planning`
  - LLM
  - no file/snippet yet
  - may inform: `S3`, `S5`

- `Per-role query expansion / helper query packaging`
  - deterministic
  - query-level
  - expands each role query produced by `Step-2 issue decomposition and role planning`
  - may add role-keyword helpers, repo-grounded retrieval terms, and other packaged subqueries before retrieval
  - no file/snippet yet

- `Initial CGC narrowing`
  - CGC + deterministic filtering
  - file-level
  - may inform: `S5`, `S7`

- `Per-role first-pass Qdrant retrieval`
  - Qdrant hybrid search
  - chunk-level entry signal only
  - output should be treated as file-candidate input, not proof
  - may inform: `S1`, `S5`

- `Chunk-to-file collapse`
  - deterministic
  - file-level
  - keep chunk refs as pointers only
  - may inform: `S1`, `S8`

- `Per-role file candidate assembly`
  - deterministic
  - file-level
  - first substage of `File-role resolution loop`
  - may trigger: `S4`, `S8`

- `Cross-role file graph linking`
  - CGC + deterministic matching
  - file-level
  - second substage of `File-role resolution loop`
  - may trigger: `S2`, `S5`, `S7`, `S8`

- `CGC-based file reranking`
  - deterministic scoring over:
    - graph relations
    - shared references
    - role compatibility
    - stage compatibility
  - file-level
  - third substage of `File-role resolution loop`
  - may trigger: `S2`, `S4`, `S5`, `S8`

- `Role ownership selection`
  - deterministic
  - file-level
  - fourth substage of `File-role resolution loop`
  - decides strongest file owners before any snippet choice
  - may trigger: `S2`, `S4`, `S8`

- `Weak-role upward expansion`
  - CGC + Qdrant
  - file-level
  - fifth substage of `File-role resolution loop`
  - moves from helper/adjacent file toward owner/responsible file
  - may trigger: `S3`, `S5`, `S7`

- `File-level final rerank`
  - deterministic
  - file-level
  - sixth substage of `File-role resolution loop`
  - produces the file winners that snippet targeting is allowed to inspect
  - may trigger: `S1`, `S4`, `S8`

- `Late snippet targeting inside winning files`
  - Qdrant-in-file retrieval + local file read
  - snippet-level
  - should operate only on file winners or explicit alternates
  - may trigger: `S1`, `S6`

- `Snippet validation for chosen files`
  - deterministic
  - snippet-level
  - may trigger: `S1`, `S6`

- `Late LLM role assessment`
  - LLM
  - snippet/evidence-level judgment
  - may trigger: `S2`, `S3`, `S4`, `S6`, `S8`

- `Optional bounded recovery`
  - deterministic orchestration using Qdrant + CGC + late feedback
  - file-first, then snippet
  - should rerun the `File-role resolution loop` before trying new snippets
  - may trigger: `S1`, `S2`, `S3`, `S5`, `S6`, `S7`, `S8`

- `Final evidence selection`
  - deterministic
  - snippet-level

- `Response synthesis`
  - deterministic response builder
  - final explanation over selected snippets
