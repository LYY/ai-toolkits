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
│   ├── dossier-output.md     ← Step 4: dossier/direct-fix brief + reply + 验证（模板、reply policy、7-check gates）
│   └── execution.md          ← 运行时合约：checkout binding、GitHub CLI 前提、artifact paths、handoff、cleanup、artifact lifecycle、Section A commit order、dirty-target blocking
└── scripts/list_comments.py  ← PR 评论采集脚本

docs/address-pr-comments-review/
├── architecture.md           ← 本文件：维护者架构概览
├── executor-neutral-design.md ← 执行器中立设计方案（已批准）
└── eval-matrix.md            ← 40-sample behavioral eval（20 RED + 20 GREEN）
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
- 路由决策：将确认后的结果路由到四种最终结果之一
- 在需要代码工作时生成持久化 artifact（Review Dossier 或 Direct Fix Brief）
- Dossier Accuracy Grill Gate

**完成条件**: 路由已确定，分类完成，（需要时）一个已验证完整性的 artifact 已存在。

### Execution Handoff Module

**拥有的 reference 文件**: [`execution.md`](../../skills/address-pr-comments-review/references/execution.md)

**职责**:
- Checkout 身份验证与绑定
- Artifact lifecycle 管理（pending → in-progress → blocked → verified-complete）
- Section A 强制提交顺序（edit → verify → commit → remote-reachability → reply → read-back）
- Dirty-target blocking（目标文件有未提交修改时阻止执行）
- Scope check、变更应用、验证、可选 commit
- Reply 发送与 POST/read-back 验证
- Cleanup（`--force` + 二次确认）
- Execution summary 生成

**完成条件**: execution summary 记录所有 applied/skipped/blocked 项，artifact 处于 `verified-complete` 状态。

## Workflow Ownership

Step 0 owns current checkout binding. Before PR verification or comment collection, the skill establishes `TARGET_WORKTREE_ROOT` from the current Git root. Multiple linked worktrees are informational by default; they do not force selection when the current root is a valid checkout. Submodule roots, detached HEAD, failed PR detection, and branch/PR head mismatches remain hard stops until the operator resolves the target and PR identity.

After Step 0, local reads and git commands are interpreted relative to `TARGET_WORKTREE_ROOT`. Disposable artifacts are not written into the checkout by default; dossier and Direct Fix Brief files live under `~/.local/state/ai-toolkits/pr-comments/<owner>__<repo>/pr-<N>/` unless the operator provides `artifact_dir=<path>`. Maintainer docs should keep both invariants visible, while runtime command details stay in [`execution.md`](../../skills/address-pr-comments-review/references/execution.md).

### Route Ownership

**Review Analysis Module** 拥有路由分类：
- 基于分类和交互确认，决定四种最终结果之一
- Route selection：Review Dossier、Direct Fix Brief、Reply Only、No Action
- 持久化 artifact（Review Dossier、Direct Fix Brief）的生成与完整性验证

**Execution Handoff Module** 拥有 artifact lifecycle：
- 四种状态转换：pending → in-progress → blocked → verified-complete
- 只有 `verified-complete` 状态允许 cleanup
- `--force` 覆盖需二次确认
- Reply Only 和 No Action 是终端路由，不产生 artifact，不经过 lifecycle

The dossier owns downstream reply-task requirements. Section A items require implementation tasks plus reply tasks. Section B items require reply tasks even when no code changes are needed. The execution contract must preserve those reply tasks instead of treating the artifact as a code-only brief.

The direct-fix route owns simple Section A shortcuts. It is optional, requires explicit user choice, and still preserves reply endpoint, commit SHA, and read-back verification fields. Complex or ambiguous Section A work remains on the dossier path by default.

The reply-only route owns direct sending. When the confirmed outcome has Section B items and no Section A work, the route sends replies directly and reads them back instead of creating a work plan. No artifact is persisted.

No Action is a terminal route: nothing remains actionable. No write operations occur. The completion is recorded but no artifact is written.

Artifact cleanup follows the Execution Handoff lifecycle. Cleanup is only permitted after `verified-complete` state, unless `--force` with two confirmations. `/address-pr-comments-review cleanup` removes the default artifact directory for one PR. `/address-pr-comments-review cleanup-all` scans the default state root. Cleanup never touches repo-local `artifact_dir` outputs unless the operator explicitly names the path.

## 各文件职责边界

| 文件 | 拥有的规则 | 不拥有的规则 |
|------|-----------|-------------|
| `classify.md` | source detection, intent, conclusion taxonomy, edge cases, evidence requirements, section mapping | cross-reference (duplicate/conflict/relation), interaction flow |
| `cross-reference.md` | duplicate/conflict/relation detection, cross-file escalation | individual classification, reply templates |
| `interaction.md` | overview table format, silent consent, 🔴 discussion flow, scaling, zero-actionable fast path, route selection (Review Dossier / Direct Fix Brief / Reply Only / No Action) | comment classification, dossier/brief structure, artifact lifecycle |
| `dossier-output.md` | dossier structure (A/B/C), Direct Fix Brief, dossier accuracy grill gate, reply endpoints, reply policy + gate, 7-check validation, Cross-File Pattern template, downstream reply task requirements, Section A commit order reference | classification rules, interaction flow, current checkout binding |
| `execution.md` | checkout binding, `list_comments.py` usage, GitHub CLI prerequisites, default local-state artifact paths, `artifact_dir` override, handoff format, cleanup commands, artifact lifecycle (pending/in-progress/blocked/verified-complete), Section A mandatory commit order, dirty-target blocking, `--force` + two-confirmation cleanup | reply API commands (owned by dossier-output.md), classification rules (owned by classify.md) |

## Artifact Lifecycle

```
pending ──→ in-progress ──→ verified-complete ──→ cleanup eligible
                │
                └──→ blocked ──→ return to Review Analysis (regenerate with fresh evidence)
```

每个持久化 artifact（Review Dossier、Direct Fix Brief）遵循此单向状态转换。状态说明：

| 状态 | 含义 |
|------|------|
| `pending` | artifact 已生成并通过完整性检查，等待执行 |
| `in-progress` | 第一个授权的变更已应用到 bound checkout |
| `blocked` | 执行无法继续（stale evidence、checkout mismatch、dirty target、验证失败等），artifact 保留等待最终解决或再生 |
| `verified-complete` | 所有变更、验证、reply、read-back 均完成 |

## Eval Matrix

[eval-matrix.md](./eval-matrix.md) 包含 40 个回归场景（20 RED + 20 GREEN，覆盖 4 个行为类别 × 每个类别 5 sessions），用于验证 skill 的行为正确性。新增 executor-neutral routing、artifact lifecycle、Section A commit order、dirty-target blocking、cleanup `--force` 语义覆盖从 Step 0 到下游执行与清理的边界。
