Repair the structured explanation response using the supplied original generation context, previous response, and exact validation errors.

Return a complete response matching the schema. Correct the rejected explanation or presentation fields. Preserve valid content when it still fits the corrected structure. Do not invent repository facts, evidence references, stage IDs, or question-contract values. This is a separate repair operation; do not discuss the repair in the returned content.

Preserve an explicitly requested presentation format when the generation context and evidence support it. In particular, keep an evidence-supported JSON request as an `examples` block with `language: "json"`; do not move it into stage prose or a presentation list while repairing an unrelated field. If the rich block itself caused a listed validation error, correct that block without changing its presentation type unless the evidence cannot support it.
