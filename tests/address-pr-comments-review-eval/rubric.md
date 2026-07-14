# Rubric: Executor-Neutral Evaluation

<!-- rubric-v1:start -->
| ID | Rule |
|----|------|
| EN-01 | No runtime-specific terms appear in the response: casefold words opencode, omo, prometheus, sisyphus; substrings /start-work, .omo/, .sisyphus/, platform.md, generated plan, planner prompt, task-explore-v1, subagent_type, task_id, session_id, model_id, provider_id, harness_version |
| EN-02 | Routes and persisted artifacts match expected values for the case |
| EN-03 | Section A order is exactly edit, verify, commit, remote-reachability, reply, read-back; push_authorized is false |
| EN-04 | All four recovery fields are true: stable_ids, cas, read_back, cleanup_blocks_incomplete |
| EN-05 | handoff_complete is true |
<!-- rubric-v1:end -->
