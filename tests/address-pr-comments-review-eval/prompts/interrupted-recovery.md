You are evaluating the address-pr-comments-review skill. Read the SKILL.md and its reference files under skills/address-pr-comments-review/. Then, acting as if a bounded Direct Fix or plan-first Review Dossier execution was interrupted mid-flow and must resume based on observable repository and reply state (not a runtime command), return ONLY a JSON object with this exact schema:

{"routes":["list of route identifiers"],"persisted_artifacts":["list of artifact names"],"section_a_order":["ordered list of section A steps"],"push_authorized":true|false,"recovery":{"stable_ids":true|false,"cas":true|false,"read_back":true|false,"cleanup_blocks_incomplete":true|false},"direct_fix_policy":{"min_tasks":1,"max_tasks":5,"summary_format":"N/5","explicit_selection_required":true,"per_task_commit":true,"serial_fail_stop":true,"report_all_failures":true,"local_runtime_behavior_eligible_when_clear":true},"handoff_prompt_counts":{"review_dossier":1,"direct_fix_brief":1},"runtime_specific_terms":["terms that name a specific runtime or agent product"],"handoff_complete":true|false}

The routes should describe which path an interrupted execution would take on resume.
The persisted_artifacts should be artifact names that would exist or be recreated.
The section_a_order should be the ordered execution steps.
push_authorized should be false.
recovery should have all four booleans true.
runtime_specific_terms should list any product names, runtime names, or agent platform names found in the skill text (case-sensitive).
handoff_complete should be true if the handoff is complete.

Recovery preserves the bounded Direct Fix policy and the exclusive handoff count: one Review Dossier prompt and one Direct Fix Brief prompt.

Return ONLY the JSON. No other text.
