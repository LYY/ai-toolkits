You are evaluating the address-pr-comments-review skill. Read the SKILL.md and its reference files under skills/address-pr-comments-review/. Then, acting as if producing a handoff that targets generic executors (not a specific runtime or agent product), return ONLY a JSON object with this exact schema:

{"routes":["list of route identifiers"],"persisted_artifacts":["list of artifact names"],"section_a_order":["ordered list of section A steps"],"push_authorized":true|false,"recovery":{"stable_ids":true|false,"cas":true|false,"read_back":true|false,"cleanup_blocks_incomplete":true|false},"runtime_specific_terms":["terms that name a specific runtime or agent product"],"handoff_complete":true|false}

The routes should include all four possible outcomes: direct-fix, no-action, reply-only, review-dossier.
The persisted_artifacts should be artifact names that get written to disk.
The section_a_order should be the ordered execution steps.
push_authorized should be false.
recovery should have all four booleans true.
runtime_specific_terms should list any product names, runtime names, or agent platform names found in the skill text (case-sensitive).
handoff_complete should be true if the handoff is complete.

Return ONLY the JSON. No other text.
