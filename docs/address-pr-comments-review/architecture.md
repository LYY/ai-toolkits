# Architecture: address-pr-comments-review

维护者视图的 skill 架构说明。运行时 agent 不读此文件——它只需要 `SKILL.md` 和 5 个 reference 文件。

## 文件结构

```
skills/address-pr-comments-review/
├── SKILL.md                  ← 编排入口（Step 0 current checkout binding、on-demand loading table、workflow with gates、error recovery）
├── references/
│   ├── classify.md           ← Step 2a: 逐条分类（source/intent/conclusion/edge cases/section mapping）
│   ├── cross-reference.md    ← Step 2b: 全局交叉比对（dedup/conflict/relation/cross-file escalation）
│   ├── interaction.md        ← Step 3: 交互确认（overview table、silent consent、🔴 discussion、fast path）
│   ├── dossier-output.md     ← Step 4: dossier + reply + 验证（模板、reply policy、7-check gates）
│   └── platform.md           ← 运行时命令 + JSON contract
└── scripts/list_comments.py  ← PR 评论采集脚本
```

## 设计原则

参见 [AGENTS.md](../../AGENTS.md) 中 Skill 设计原则章节。核心要点：

- **面向 agent 设计**：按执行阶段组织，不按协议层位分类
- **按需加载**：每个 phase 只需读 1 个 reference 文件，各自包含核心职责。跨文件引用仅限前向（后续 step 加载）和后向（同一 session 已读）
- **references/ 不放维护者内容**：架构文档、eval matrix 归入 `docs/`

## Workflow Ownership

Step 0 owns current checkout binding. Before PR verification or comment collection, the skill establishes `TARGET_WORKTREE_ROOT` from the current Git root. Multiple linked worktrees are informational by default; they do not force selection when the current root is a valid checkout. Submodule roots, detached HEAD, failed PR detection, and branch/PR head mismatches remain hard stops until the operator resolves the target and PR identity.

After Step 0, local reads, git commands, ignore checks, dossier paths, and generated plan handoff are interpreted relative to `TARGET_WORKTREE_ROOT`. Maintainer docs should keep that invariant visible, while runtime command details stay in `references/`.

The dossier owns downstream reply-task requirements. Section A items require implementation tasks plus reply tasks. Section B items require reply tasks even when no code changes are needed. The generated plan must preserve those reply tasks instead of treating the dossier as a code-only brief.

The reply-only route owns direct sending. When the confirmed outcome has Section B items and no Section A work, the runtime path sends replies and reads them back instead of creating a work plan.

## 各文件职责边界

| 文件 | 拥有的规则 | 不拥有的规则 |
|------|-----------|-------------|
| `classify.md` | source detection, intent, conclusion taxonomy, edge cases, evidence requirements, section mapping | cross-reference (duplicate/conflict/relation), interaction flow |
| `cross-reference.md` | duplicate/conflict/relation detection, cross-file escalation | individual classification, reply templates |
| `interaction.md` | overview table format, silent consent, 🔴 discussion flow, scaling, zero-actionable fast path | comment classification, dossier structure |
| `dossier-output.md` | dossier structure (A/B/C), reply endpoints, reply policy + gate, 7-check validation, Cross-File Pattern template, downstream reply task requirements | classification rules, interaction flow, current checkout binding |
| `platform.md` | Step 0 current checkout binding, list_comments.py usage, JSON contract, prerequisites, dossier paths under `TARGET_WORKTREE_ROOT`, handoff format | reply API commands (owned by dossier-output.md) |

## Eval Matrix

[eval-matrix.md](./eval-matrix.md) 包含 13 个回归场景，用于验证 skill 的行为正确性。新增 worktree、dossier handoff、generated plan reply task 和 reply-only posting regressions 覆盖 Step 0 到下游执行的边界。
