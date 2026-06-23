# CodeRepoQA Benchmark Groups

This corpus mixes two different benchmark intents. They should not be treated as interchangeable when comparing retrieval modes.

## Retrieval-grounded

Use these cases for overlap, ranking, token, and timing comparisons.

Classification rule:
- `verification.json` contains at least one explicit oracle file in `oracle.implementation_files`,
  `oracle.test_or_validation_files`, or `oracle.documentation_files`.
- These cases support deterministic checks such as file overlap, top-k placement, and stable timing/token comparisons.

Cases in this group: `21`

- `microsoft-TypeScript-24625`
- `microsoft-TypeScript-2953`
- `microsoft-TypeScript-35468`
- `microsoft-TypeScript-45713`
- `microsoft-TypeScript-46770`
- `microsoft-TypeScript-52695`
- `pandas-dev-pandas-10068`
- `pandas-dev-pandas-14942`
- `pandas-dev-pandas-16499`
- `pandas-dev-pandas-16764`
- `pandas-dev-pandas-22698`
- `pandas-dev-pandas-22872`
- `pandas-dev-pandas-25183`
- `pandas-dev-pandas-32289`
- `pandas-dev-pandas-35925`
- `pandas-dev-pandas-36617`
- `pandas-dev-pandas-4542`
- `vuejs-vue-10803`
- `vuejs-vue-5884`
- `vuejs-vue-6301`
- `vuejs-vue-9042`

## Explanation-grounded

Use these cases for explanation agreement, leakage checks, and evidence plausibility.

Classification rule:
- `verification.json` intentionally omits oracle file lists and instead defines truth mainly through
  subsystem/responsibility summaries and post-resolution maintainer explanations.
- These cases are poor headline retrieval benchmarks because file overlap is not meaningful or is explicitly marked secondary.

Cases in this group: `3`

- `microsoft-TypeScript-6307`
- `microsoft-TypeScript-8305`
- `pandas-dev-pandas-9219`

## Why The Split Matters

- Retrieval-grounded cases answer: did the retriever reach the right code quickly and cheaply?
- Explanation-grounded cases answer: did the system infer the right explanation without leaking hindsight?
- Do not use explanation-grounded cases as the main evidence for retrieval superiority.
- Do not use retrieval-grounded overlap scores alone to judge explanation quality.

## Current Corpus Totals

- Total cases: `24`
- Retrieval-grounded: `21`
- Explanation-grounded: `3`
