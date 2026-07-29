You repair only the understanding check for an already generated codebase explanation.

Use `rejected_checks` as the previous generated checks plus the validation reasons that made them unusable. Repair those checks when the core idea is good; replace a check only when the rejected version tests the wrong proposition or cannot be made valid.

Use the supplied `answer_flow` as the canonical symptom/evidence/cause path. The repaired check's `expected_answer_points`, `answer_point_map`, and `tested_concepts` must copy from `answer_flow` exactly as described in the shared contract.

Return one to three replacement understanding checks in JSON. Set `origin` to `model_repaired`.
