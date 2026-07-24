# Rubric: Executor-Neutral Evaluation

<!-- rubric-v1:start -->
| ID | Rule |
|----|------|
| EN-01 | No runtime-specific terms appear in the response: casefold words opencode, omo, prometheus, sisyphus; substrings /start-work, .omo/, .sisyphus/, platform.md, generated plan, planner prompt, task-explore-v1, subagent_type, task_id, session_id, model_id, provider_id, harness_version |
| EN-02 | Routes and persisted artifacts match expected values for the case |
| EN-03 | Section A order is exactly edit, verify, commit, remote-reachability, reply, read-back; push_authorized is false |
| EN-04 | All four recovery fields are true: stable_ids, cas, read_back, cleanup_blocks_incomplete |
| EN-05 | handoff_complete is true |
| EN-06 | direct_fix_policy exactly matches min_tasks=1, max_tasks=5, max_ordered_chains=1, max_ordered_chain_tasks=3, mixed_batches_allowed=true, serial_execution_required=true, eligible_complexity_classes=["mechanical", "local-behavior"], verification_companions_share_task=true, informed_route_confirmation_required=true, prior_direct_fix_preference_carried_forward=true, summary_format="N/5", explicit_selection_required=true, per_task_commit=true, serial_fail_stop=false, report_all_failures=true, local_runtime_behavior_eligible_when_clear=true. A terminal safe task-local failure continues only from a proven safe checkpoint: block the current task and transitive dependents; independent ready tasks continue serially in deterministic order. A global, unsafe, or unreconciled external-write failure immediately blocks, leaves unrelated not-started tasks pending, permits no later side effects, and never authorizes another POST. |
| EN-07 | handoff_prompt_counts exactly matches review_dossier=1 and direct_fix_brief=1; Review Dossier is plan-first and Direct Fix Brief is direct execution |
<!-- rubric-v1:end -->
