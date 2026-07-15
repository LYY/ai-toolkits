You are evaluating the address-pr-comments-review skill. Read the SKILL.md and its reference files under skills/address-pr-comments-review/. Then, acting as if generating a plan-first Review Dossier for a PR with complex code change comments, return ONLY a JSON object with this exact schema:

{"routes":["list of route identifiers"],"persisted_artifacts":["list of artifact names"],"section_a_order":["ordered list of section A steps"],"push_authorized":true|false,"recovery":{"stable_ids":true|false,"cas":true|false,"read_back":true|false,"cleanup_blocks_incomplete":true|false},"direct_fix_policy":{"min_tasks":1,"max_tasks":5,"summary_format":"N/5","explicit_selection_required":true,"per_task_commit":true,"serial_fail_stop":true,"report_all_failures":true,"local_runtime_behavior_eligible_when_clear":true},"handoff_prompt_counts":{"review_dossier":1,"direct_fix_brief":1},"runtime_specific_terms":["terms that name a specific runtime or agent product"],"handoff_complete":true|false}

The routes should be identifiers like "review-dossier", "direct-fix", "reply-only", "no-action".
The persisted_artifacts should be artifact names that get written to disk.
The section_a_order should be the ordered execution steps.
push_authorized should be false.
recovery should have all four booleans true.
runtime_specific_terms should list any product names, runtime names, or agent platform names found in the skill text (case-sensitive).
handoff_complete should be true if the handoff is complete.

The Review Dossier handoff is plan-first and exclusive. The Direct Fix policy and handoff prompt counts must match the schema exactly.

Return ONLY the JSON. No other text.
