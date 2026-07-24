# Architecture: address-pr-comments-review

维护者视图的 skill 架构说明。运行时 agent 不读此文件——它只需要 `SKILL.md` 和 reference 文件。

## 文件结构

```
skills/address-pr-comments-review/
├── SKILL.md                  ← 编排入口（Step 0 current checkout binding、on-demand loading table、workflow with gates、error recovery）
├── references/
│   ├── classify.md           ← Step 2a: 逐条分类（source/intent/conclusion/edge cases/section mapping）
│   ├── cross-reference.md    ← Step 2b: 全局交叉比对（dedup/conflict/relation/cross-file escalation）
│   ├── interaction.md        ← Step 3: 交互确认（overview table、silent consent、🔴 discussion、route selection）
│   ├── dossier-output.md     ← Step 4: dossier/direct-fix brief + reply + 验证（模板、bounded Direct Fix、exclusive handoff、7-check gates）
│   └── execution.md          ← 运行时合约：checkout binding、GitHub CLI 前提、artifact paths、handoff、cleanup、artifact lifecycle、Section A commit order、dirty-target blocking
└── scripts/list_comments.py  ← PR 评论采集脚本

docs/address-pr-comments-review/
├── architecture.md           ← 本文件：维护者架构概览
├── executor-neutral-design.md ← 执行器中立设计方案（已批准）
└── eval-matrix.md            ← 40-sample behavioral eval（20 RED + 20 GREEN）与 Direct Fix topology cases
```

## 设计原则

参见 [AGENTS.md](../../AGENTS.md) 中 Skill 设计原则章节。核心要点：

- **面向 agent 设计**：按执行阶段组织，不按协议层位分类
- **按需加载**：每个 phase 只需读 1 个 reference 文件，各自包含核心职责。跨文件引用仅限前向（后续 step 加载）和后向（同一 session 已读）
- **references/ 不放维护者内容**：架构文档、eval matrix 归入 `docs/`

## 模块划分

两个模块通过已批准的 artifact 接口（Markdown）耦合：

### Review Analysis Module

**拥有的 reference 文件**: `classify.md`、`cross-reference.md`、`interaction.md`、`dossier-output.md`

**职责**:
- Step 0: current checkout binding（详见 [`execution.md`](../../skills/address-pr-comments-review/references/execution.md)）
- 评论采集（`scripts/list_comments.py`）
- Evidence Ledger 构建
- 逐条分类与交叉比对
- 路由决策：将确认后的结果路由到 Review Dossier、Direct Fix Brief、Reply Only 或 No Action
- 在需要代码工作时生成持久化 artifact（Review Dossier 或 Direct Fix Brief）
- Dossier Accuracy Grill Gate

**完成条件**: 路由已确定，分类完成，（需要时）一个已验证完整性的 artifact 已存在，并且其适用 handoff 已唯一确定。

### Execution Handoff Module

**拥有的 reference 文件**: [`execution.md`](../../skills/address-pr-comments-review/references/execution.md)

**职责**:
- Checkout 身份验证与绑定
- Artifact lifecycle 管理（pending/in-progress → blocked；validated recovery 后 blocked → in-progress；verified-complete terminal）
- Section A 强制提交顺序（每个任务 edit → verify → commit → push → remote-reachability → reply → read-back）
- Dirty-target blocking（目标文件有未提交修改时阻止执行）
- Scope check、变更应用、验证、Section A commit、push 与 remote reachability
- Reply 发送与 POST/read-back 验证
- Cleanup（`--force` + 二次确认）
- Execution summary 生成

**完成条件**: execution summary 记录所有 applied/skipped/blocked 项；每个 Section A task 均已完成 edit → verify → commit → push → remote-reachability → reply → read-back，并记录 distinct modification SHA；artifact 处于 `verified-complete` 状态。

## Workflow Ownership

Step 0 owns current checkout binding. Before PR verification or comment collection, the skill establishes `TARGET_WORKTREE_ROOT` from the current Git root. Multiple linked worktrees are informational by default; they do not force selection when the current root is a valid checkout. Submodule roots, detached HEAD, failed PR detection, and branch/PR head mismatches remain hard stops until the operator resolves the target and PR identity.

After Step 0, local reads and git commands are interpreted relative to `TARGET_WORKTREE_ROOT`. Disposable artifacts are not written into the checkout by default; dossier and Direct Fix Brief files live under `~/.local/state/ai-toolkits/pr-comments/<owner>__<repo>/pr-<N>/` unless the operator provides `artifact_dir=<path>`. Maintainer docs should keep both invariants visible, while runtime command details stay in [`execution.md`](../../skills/address-pr-comments-review/references/execution.md).

### Route Ownership

**Review Analysis Module** 拥有路由分类：
- 基于分类和交互确认，决定四种最终结果之一
- Route selection：Review Dossier、Direct Fix Brief、Reply Only、No Action
- 持久化 artifact（Review Dossier、Direct Fix Brief）的生成与完整性验证

**Execution Handoff Module** 拥有 artifact lifecycle：
- 合法状态转换：pending → in-progress → verified-complete；pending/in-progress → blocked；blocked → in-progress 仅允许 validated recovery
- 只有 `verified-complete` 状态允许 cleanup
- `--force` 覆盖需二次确认
- Reply Only 和 No Action 是终端路由，不产生 artifact，不经过 lifecycle

### Canonical Reply Routes

每个 reply target 都必须保留 `source_comment_id`、`root_comment_id`、`comment_kind`、`reply_mode`、`endpoint` 和 `read_back_endpoint`。路由只由 source/root/kind/mode 决定，不按作者或子评论 ID 选择 endpoint。

| Maintained scenario | Route | POST endpoint | POST payload | Route-specific read-back |
|---|---|---|---|---|
| inline root 101, `source_comment_id=101`, `root_comment_id=101` | `threaded_inline` | `repos/{owner}/{repo}/pulls/{pr}/comments/101/replies` | exactly `{body}` | PR review comments, authenticated actor, full body, target PR, `in_reply_to_id=101` |
| inline child 202, `source_comment_id=202`, `root_comment_id=101` | `sibling_inline` | `repos/{owner}/{repo}/pulls/{pr}/comments/101/replies` | exactly `{body}` | PR review comments, authenticated actor, full body, target PR, `in_reply_to_id=101` |
| review-level 303, `comment_kind=review`, null root | `timeline` | `repos/{owner}/{repo}/issues/{pr}/comments` | exactly `{body}` | PR issue comments, authenticated actor, full body, target PR |
| top-level 404, `comment_kind=top_level`, null root | `timeline` | `repos/{owner}/{repo}/issues/{pr}/comments` | exactly `{body}` | PR issue comments, authenticated actor, full body, target PR |

Threaded payload rejects `commit_id`, `path`, `line`, `side`, and `in_reply_to`. `fixed` and `partially_addressed` replies keep the full task-specific 40-character commit SHA in rendered body text, never in threaded POST metadata. Missing or inconsistent route data, timeout, malformed response, zero exact read-back matches, and multiple exact matches fail closed. Uncertain writes are read back before deciding whether any POST remains, and this workflow never retries by sending a second POST.

The dossier owns downstream reply-task requirements. Section A items require implementation tasks plus reply tasks. Section B items require reply tasks even when no code changes are needed. The execution contract must preserve those reply tasks instead of treating the artifact as a code-only brief.

The direct-fix route owns bounded Section A shortcuts. It permits one through five tasks only when each task is `mechanical` or `local-behavior`, has one deduplicated root concern, one behavioral outcome, and one production implementation locus, carries a complete typed complexity certificate, and meets the topology limits: total Section A hard cap `5`, ordered-chain count cap `1`, ordered-chain hard cap `3`, with all remaining nodes as independent singletons. Implementation and direct test/spec/fixture companions stay in one task; file count or file type alone does not decide eligibility. The final classification table must disclose the recommended route, batch shape, caps, complexity classes, implementation and verification paths, serial execution, fallback reason inventory, and no second plan approval. A prior Direct Fix preference remains pending rather than authorization and is carried forward and restated; affirmative final-table confirmation then authorizes Direct Fix once. Without that pending preference, generic `proceed` confirms classification only and requires explicit Direct Fix selection after disclosure. Any table content, topology, or scope update invalidates prior confirmation. Each task gets canonical route fields, one distinct task-specific commit SHA, and full reply/read-back requirements. Failure handling follows the [Direct Fix Failure Scope Matrix](../../skills/address-pr-comments-review/references/dossier-output.md#direct-fix-failure-scope-matrix). Clear local runtime behavior fixes remain eligible when unambiguous. Complex, blocked, or ambiguous Section A work remains on the dossier path by default.

### Direct Fix Failure Scope

The runtime matrix is authoritative; this section summarizes its maintainer-facing consequences. A terminal task-local failure at a proven safe checkpoint marks the current task `blocked`, marks transitive dependents `blocked` with the failed prerequisite ID, and lets independent ready tasks continue in deterministic serial order. The artifact becomes `blocked` only after the scheduler is exhausted and required blocked work remains. For example, if `task-1` fails safely, dependent `task-2` is blocked, independent singleton `task-3` continues, and the final artifact is blocked after no more ready work remains.

An unsafe checkpoint, global checkout/certificate/topology/order failure, or unreconciled external write blocks the artifact immediately. No later task side effect is allowed; unrelated not-started tasks remain deterministically `pending`. An uncertain POST or read-back result is reconciled through the canonical route-specific read-back exactly once. Exactly one match reconciles the write; zero, multiple, malformed, or incomplete matches keep the artifact blocked and never authorize another POST.

The reply-only route owns direct sending. When the confirmed outcome has Section B items and no Section A work, the route selects the canonical endpoint from each target's source/root/kind/mode fields, sends a body-only reply, and performs route-specific read-back instead of creating a work plan. A timeout or malformed POST result still requires read-back; zero or multiple exact matches remain blocked, with no second POST. No artifact is persisted.

No Action is a terminal route: nothing remains actionable. No write operations occur. The completion is recorded but no artifact is written.

Artifact cleanup follows the Execution Handoff lifecycle. Cleanup is only permitted after `verified-complete` state, unless `--force` with two confirmations. `/address-pr-comments-review cleanup` removes the default artifact directory for one PR. `/address-pr-comments-review cleanup-all` scans the default state root. Cleanup never touches repo-local `artifact_dir` outputs unless the operator explicitly names the path.

## 各文件职责边界

| 文件 | 拥有的规则 | 不拥有的规则 |
|------|-----------|-------------|
| `classify.md` | source detection, intent, conclusion taxonomy, edge cases, evidence requirements, section mapping | cross-reference (duplicate/conflict/relation), interaction flow |
| `cross-reference.md` | duplicate/conflict/relation detection, cross-file escalation | individual classification, reply templates |
| `interaction.md` | overview table format, informed final-table route disclosure and consent matrix, 🔴 discussion flow, scaling, zero-actionable fast path, route selection (Review Dossier / Direct Fix Brief / Reply Only / No Action) | comment classification, dossier/brief structure, artifact lifecycle |
| `dossier-output.md` | dossier structure (A/B/C), Direct Fix Brief eligibility certificate and topology summary, canonical reply target fields, deterministic endpoints, body-only payload, route-specific read-back, fail-closed reconciliation, reply policy + gate, 7-check validation, Cross-File Pattern template, downstream reply task requirements, Section A commit order reference | classification rules, interaction flow, current checkout binding |
| `execution.md` | checkout binding, `list_comments.py` usage, GitHub CLI prerequisites, default local-state artifact paths, `artifact_dir` override, handoff format, cleanup commands, artifact lifecycle (pending/in-progress/blocked/verified-complete), Section A mandatory commit order, dirty-target blocking, `--force` + two-confirmation cleanup | reply API commands (owned by dossier-output.md), classification rules (owned by classify.md) |

## Artifact Lifecycle

```
pending ──→ in-progress ──→ verified-complete ──→ cleanup eligible
   │              │
   └──────────────→ blocked ──→ in-progress (validated recovery only)
```

每个持久化 artifact（Review Dossier、Direct Fix Brief）遵循 canonical state machine。`blocked` 不是自动继续：只有重新验证当前 Context、task-start checkpoint（HEAD、scope、hashes、preimages）、未协调外部写入，并在 Direct Fix 中执行 `lease-recover` 的 canonical read-back 后，才能回到 `in-progress`。恢复只从首个 dependency-ready pending task 继续；无法证明安全时保持 `blocked`，也可基于新证据再生 artifact。

| 状态 | 含义 |
|------|------|
| `pending` | artifact 已生成并通过完整性检查，等待执行 |
| `in-progress` | 第一个授权的变更已应用到 bound checkout |
| `blocked` | Direct Fix 在 scheduler 耗尽后仍有依赖阻断，或任一路由触发全局、不安全检查点、未协调写入等立即停止边界；artifact 保留等待 validated recovery 或基于新证据再生 |
| `verified-complete` | 所有 Section A 变更均已 commit、push、确认 remote-reachable、reply、read-back，并记录 distinct modification SHA；Section B 仅完成 reply/read-back |

## Eval Matrix

[eval-matrix.md](./eval-matrix.md) 定义维护者可回归审查的场景，并由 40 个样本（20 RED + 20 GREEN，覆盖 4 个行为类别 × 每个类别 5 sessions）验证 skill 行为。矩阵包含 PR #1431 implementation-plus-verification companion、合法 mixed topology，以及非法 complexity/topology cases；executor-neutral routing、artifact lifecycle、Section A commit order、dirty-target blocking、cleanup `--force` 语义覆盖从 Step 0 到下游执行与清理的边界。
