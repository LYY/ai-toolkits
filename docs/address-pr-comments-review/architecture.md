# Architecture: address-pr-comments-review

维护者视图的 skill 架构说明。运行时执行规则以 [`dossier-output.md`](../../skills/address-pr-comments-review/references/dossier-output.md) 为准，本文件只描述模块边界和接口摘要。

## 文件结构

```
skills/address-pr-comments-review/
├── SKILL.md
├── references/
│   ├── classify.md
│   ├── cross-reference.md
│   ├── interaction.md
│   ├── dossier-output.md
│   └── execution.md
└── scripts/list_comments.py

docs/address-pr-comments-review/
├── architecture.md
├── executor-neutral-design.md
└── eval-matrix.md
```

## Ownership

两个模块通过 Markdown artifact 接口连接。Analysis 决定评论含义和路线，Execution 消费已经生成的 artifact。持久化 artifact 只有 Review Dossier 和 Direct Fix Brief，Reply Only 与 No Action 不进入 artifact lifecycle。

### Review Analysis Module

拥有 `classify.md`、`cross-reference.md`、`interaction.md` 和 `dossier-output.md` 中的生成部分。

- 绑定并验证当前 checkout，采集评论，建立 Evidence Ledger。
- 按证据分类，识别 duplicate、conflict、relation 和 cross-file scope。
- 展示 overview 和 final table，取得所需确认。
- 路由到 Review Dossier、Direct Fix Brief、Reply Only 或 No Action。
- 生成并验证一个适用的 Markdown artifact。

完成条件：分类和路线已确定，artifact（如需要）完整且没有 placeholder，handoff 唯一。

### Execution Handoff Module

拥有 [`execution.md`](../../skills/address-pr-comments-review/references/execution.md) 的 checkout、命令、路径、handoff 和 cleanup 规则；`dossier-output.md` 拥有 artifact 的执行合同。

- 校验 Context、Status Block、scope 和外部写入状态。
- 对 Section A 严格执行 `edit -> verify -> commit -> push -> remote-reachability -> reply -> read-back`。
- 对 Section B 和 Reply Only 执行 `reply -> read-back`。
- 维护 `pending`、`in-progress`、`blocked`、`verified-complete` 状态。
- 只有 `verified-complete`，或 `--force` 加两次确认，才允许 cleanup。

完成条件：execution summary 记录 applied、skipped、blocked、verification、commit SHA、reply 和 read-back 证据，artifact 状态正确。

## Artifact Interface

### Direct Fix v2

Direct Fix 是受限的 Section A 快速路线，不是新的运行时协议。完整 schema、canonical policy、fingerprint、字段顺序和失败矩阵只在 [`dossier-output.md` 的 Direct Fix 部分](../../skills/address-pr-comments-review/references/dossier-output.md#direct-fix-brief) 定义。

维护者摘要如下：

- `direct_fix_schema_version` 必须是整数 `2`。有效 mode 只有 `locus-change` 和 `verification-only`。
- `locus-change` 必须有 changed selectors；`verification-only` 必须没有 changed selectors，并且有独立的 expected-result oracle。共享 runner、helper 或 matcher 的变更属于 `verification-infrastructure` locus-change。
- `locus_kind` 与 typed selector 必须配对：`runtime-code`、`declarative-config`、`tooling-automation`、`documentation-contract`、`verification-infrastructure`。
- `expected_paths` 是唯一 scope authority。它必须精确覆盖 changed selectors 指向的路径和 `Verification paths`，不能有重复、遗漏或额外路径。selectors 是完整性证据，不会增加或推导 scope。
- 每个 task 保留直接测试、spec 或 fixture 路径，并与对应变更同一 task。最多 5 个 Section A task，最多一条 2 到 3 节点 ordered chain，其余必须是独立 singleton，执行始终 serial。
- `unresolved-global-scope` 单独产生 `batch.scope`。`resolved-commented-file-only` 本身不阻塞，但仍须通过其他 gates。
- 资格原因使用 `batch.*` 与 `task.*`。路线授权使用 `route.policy-binding`、`route.batch-fingerprint`、`route.authorization`。artifact 完整性使用 `artifact.policy-binding`、`artifact.scope-drift`、`artifact.selector-drift`。三类原因不能互换。
- Canonical blockers 是 architecture、cross-module-state、public-interface、security-or-authorization、schema-or-data、dependency-introduction、concurrency、transaction、retry-or-recovery、deployment-or-release、unclear-verification，共 11 项。

这些摘要不复制 JSON contract。新增或变更规则必须先改 runtime authority，再更新本文件和 [eval matrix](./eval-matrix.md)。

### Reply and State Integrity

Reply target 必须保留 `source_comment_id`、`root_comment_id`、`comment_kind`、`reply_mode`、`endpoint`、`read_back_endpoint`。路由由 source/root/kind/mode 决定，POST body 只有 `body`，读回必须精确匹配 actor、body、PR 和必要的 thread relation。超时、malformed response、零匹配或多匹配都 fail closed，不能用第二次 POST 验证或恢复。

`valid` 和 `partially_addressed` 必须原样保留在 final table、artifact 和 reply posture。`has_replies` 只是 signal，只有 human、substantive、non-self reply 才能得到 `already_replied`。`reject` suggestion 只有在 exact mechanical alternate 已披露、用户确认并通过 fresh preflight 后，才可重新进入 Direct Fix。

## Route and Lifecycle Ownership

`interaction.md` 拥有分类确认、route disclosure 和 consent state。Direct Fix authorization 与 eligibility 分离：generic `proceed` 不单独授权 Direct Fix；无 prior preference 时必须显式选择，已披露并重新陈述的 pending preference 才能由 final confirmation 授权一次。任何 table、topology、scope、policy 或 fingerprint 改变都会使旧确认失效。

`dossier-output.md` 拥有 Direct Fix failure scope matrix。安全检查点的 task-local failure 只阻断当前 task 及传递依赖，独立 ready task 继续；scheduler 耗尽后仍有必需阻断工作时 artifact 才变为 `blocked`。global、unsafe、certificate、topology、order 或 unreconciled external write failure 立即阻断，并禁止后续副作用。

`classify.md` 拥有 conclusion taxonomy，`cross-reference.md` 拥有 duplicate、conflict、relation 和 scope resolution，`execution.md` 拥有 checkout、artifact path、handoff 和 cleanup。各文件只引用其他文件的规则，不复制其 normative contract。

## Eval Coverage

[eval-matrix.md](./eval-matrix.md) 维护当前 17 个 evaluator cases 的路线、artifact 和 exact reason expectations，覆盖 Direct Fix v2 modes、typed loci、scope authority、bindings、state preservation、topology、blockers、security/deployment、alternate reentry 和 recovery。历史评估结果与 evidence 保持不变。
