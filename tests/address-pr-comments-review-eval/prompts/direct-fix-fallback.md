You are evaluating the address-pr-comments-review skill. Read the SKILL.md and its reference files under skills/address-pr-comments-review/. Then, acting as if a bounded Direct Fix was initially considered but determined ineligible, and the skill falls back to the plan-first Review Dossier path, return ONLY a JSON object with this exact schema:

{"routes":["list of route identifiers"],"persisted_artifacts":["list of artifact names"],"section_a_order":["ordered list of section A steps"],"push_authorized":true|false,"recovery":{"stable_ids":true|false,"cas":true|false,"read_back":true|false,"cleanup_blocks_incomplete":true|false},"direct_fix_policy":{"min_tasks":1,"max_tasks":5,"max_ordered_chains":1,"max_ordered_chain_tasks":3,"mixed_batches_allowed":true,"serial_execution_required":true,"eligible_complexity_classes":["mechanical","local-behavior"],"verification_companions_share_task":true,"informed_route_confirmation_required":true,"prior_direct_fix_preference_carried_forward":true,"summary_format":"N/5","explicit_selection_required":true,"per_task_commit":true,"serial_fail_stop":true,"report_all_failures":true,"local_runtime_behavior_eligible_when_clear":true},"handoff_prompt_counts":{"review_dossier":1,"direct_fix_brief":1},"runtime_specific_terms":["terms that name a specific runtime or agent product"],"handoff_complete":true|false}

The routes that apply when direct-fix is ineligible and falls back to review-dossier.
The persisted_artifacts should be artifact names.
The section_a_order should be the ordered execution steps.
push_authorized should be false.
recovery should have all four booleans true.
runtime_specific_terms should list any product names, runtime names, or agent platform names found in the skill text (case-sensitive).
handoff_complete should be true if the handoff is complete.

The Direct Fix policy is bounded to one through five independent tasks. An ineligible Direct Fix has exactly one plan-first Review Dossier handoff.

Return ONLY the JSON. No other text.
