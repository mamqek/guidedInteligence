# Corrected Retrieval Pipeline

## Version Summary

This is the corrected owner-first, snippet-grounded retrieval pipeline.

Compared with V2, it tightens the core evidence rule: a file can be a likely owner, but it is not grounded evidence until the pipeline finds the decisive snippet inside it. Support expansion and final explanation quality are therefore downstream of owner-file snippet grounding.

## Purpose

This pipeline is meant to match the actual evidence-finding method more closely.

The core idea is simple:

- identify the code that most likely owns the behavior
- get to the decisive snippet inside that code as early as possible
- widen only if that snippet is not enough

This is narrower than a full redesign. It is mainly a correction to the current retrieval order and evidence standards.

## Main Principle

The system should optimize for:

- **finding the decisive implementation snippet**

not for:

- distributing attention evenly across many roles before decisive evidence exists

In practice, a good retrieval run usually has:

- one primary owner file
- one decisive snippet inside that file
- a small number of supporting snippets around it

## Evidence Model

### Strong evidence

- directly implements the behavior
- directly checks or rejects the behavior
- directly emits the relevant diagnostic
- directly parses the relevant syntax

### Medium evidence

- sits immediately adjacent to the decisive logic
- defines the data structure or representation used by the decisive logic
- constrains the decisive logic indirectly

### Weak evidence

- conceptually related but not behavior-deciding
- file-level owner with no grounded snippet yet

### Noise

- generally related to the domain but not actually useful for the issue
- tests, harness, docs, baselines, generated files used too early

## Corrected Pipeline

### Step 0. Deterministic prompt distillation

Input:

- raw issue prompt
- examples in the issue

Output:

- short problem summary
- grounded prompt entities
- grounded lexical evidence
- explicit file/symbol hints if they exist

Rules:

- deterministic only
- no invented anchors
- no role fanout yet

Purpose:

- reduce prompt noise and preserve only grounded retrieval material

### Step 1. Compact repo grounding

Input:

- prompt summary
- grounded prompt entities
- compact repo sketch

Output:

- representative implementation files
- top directories
- compact repo vocabulary
- any directly confirmed repo hints

Rules:

- deterministic
- compact only

Purpose:

- keep later retrieval repo-grounded without spending large token budget

### Step 2. Owner hypothesis

Input:

- prompt summary
- prompt lexical evidence
- repo sketch

Output:

- ranked owner candidates
- one primary owner file
- optionally one alternate owner file

Rules:

- prefer implementation files first
- tests/docs/harness are supporting only unless implementation is missing
- file-level owner is only a routing result, not accepted evidence

Purpose:

- answer the main retrieval question early:
  - where does this behavior most likely live?

### Step 3. Mandatory in-file snippet targeting

Input:

- primary owner file
- optional alternate owner file
- prompt summary
- grounded lexical evidence

Output:

- snippet candidates inside the owner file
- one best snippet
- optional backup snippet

Rules:

- this step is mandatory
- snippet search must start inside the winning file
- global snippet recovery is allowed only after serious in-file attempt fails
- a file-level owner cannot satisfy the role by itself

Purpose:

- convert file ownership into real evidence

This is the most important correction.

### Step 4. Decisive snippet check

Input:

- best snippet
- owner file
- prompt summary

Output:

- `decisive = true|false`
- missing aspects list
- whether supporting evidence is needed

Rules:

- the question is not “is this file related?”
- the question is:
  - does this snippet actually explain the behavior the issue is asking about?

Purpose:

- prevent the pipeline from moving on while the main evidence is still broad or generic

If the answer is `false`:

- retry in-file targeting
- or switch to the alternate owner file
- but do not widen to many supporting roles yet

### Step 5. Local support expansion

Input:

- decisive or nearly decisive owner snippet
- missing aspects list

Output:

- targeted supporting retrieval only for real gaps

Rules:

- widen only to close specific gaps
- retrieve the minimum supporting layer needed

Examples:

- if representation is unclear, retrieve the type/AST declaration snippet
- if parsing is unclear, retrieve the parser snippet
- if diagnostics are unclear, retrieve the diagnostic snippet

Purpose:

- support the main explanation without losing focus on the owner logic

### Step 6. Deferred broad support

These sources should remain deferred until needed:

- tests
- docs
- config
- broad harness files
- generalized behavior/output paths that are not clearly tied to the issue

Rules:

- they should not be used to create false completeness
- they should not consume major LLM budget before owner evidence is grounded

### Step 7. Explanation generation

Input:

- decisive owner snippet
- supporting snippets
- explicit uncertainty list

Output:

- explanation markdown

Rules:

- explanation must inherit evidence quality
- it should not smooth over missing decisive evidence
- if owner evidence is weak, explanation must say so directly

## LLM Budget Policy

### Good early LLM usage

- compact issue planning
- sharpening owner-targeted lexical queries when deterministic retrieval is ambiguous
- assessing whether a grounded snippet actually answers the issue

### Bad early LLM usage

- broad role fanout before owner grounding
- repeated helper-query generation for many low-priority roles
- explanation polishing before decisive evidence exists
- treating weak file-level candidates as if they were already informative

## Explicit Pipeline Rules

These rules should be explicit and unconditional.

### Rule 1. File-level winners are not evidence

If retrieval returns:

- `checker.ts:FILE`

that means:

- the file is a likely owner

It does **not** mean:

- the issue is now explained

### Rule 2. In-file targeting comes before global recovery

If a winning owner file exists:

- search inside that file first

Only after failure:

- broaden to global snippet recovery

### Rule 3. The pipeline should not widen while the owner snippet is still weak

If the main owner snippet is generic, off-target, or missing:

- do not spend large budget on diagnostics/tests/docs
- fix owner grounding first

### Rule 4. Supporting evidence must support something specific

Every supporting retrieval step should answer:

- what precise gap in the owner explanation is this closing?

If there is no clear gap, that retrieval step is probably unnecessary.

## What This Fixes in the Current System

This corrected pipeline directly addresses the confirmed current failure mode:

- `validation_checking` can drift into `checker.ts:FILE`
- snippet convergence inside `checker.ts` is too weak or too late
- the pipeline still spends LLM budget on broad structured retrieval
- final explanation is generated from partial grounding

The corrected behavior should be:

1. identify `checker.ts` as likely owner
2. force snippet targeting inside `checker.ts`
3. verify whether the resulting checker snippet actually explains abstract-class enforcement
4. only then widen to parser/types/diagnostics if needed

## Minimal Default Shape

For most issues, the default retrieval shape should be:

1. Distill prompt
2. Sketch repo
3. Pick owner file
4. Find decisive snippet in owner
5. Verify snippet sufficiency
6. Add only the support needed
7. Generate explanation

That is much closer to the actual evidence-finding method than a broad role-symmetric pipeline.

## Practical Rule for Immediate Adoption

For the current system, one immediate rule should hold:

- if a role has accepted file owner `X:FILE`, snippet refinement must run inside `X` before that role can be treated as grounded

This is the simplest high-confidence correction.
