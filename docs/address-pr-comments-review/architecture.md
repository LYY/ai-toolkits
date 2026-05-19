# Architecture: address-pr-comments-review

维护者视图的 skill 架构说明。运行时 agent 不读此文件——它只需要 `SKILL.md` 和 5 个 reference 文件。

## 文件结构

```
skills/address-pr-comments-review/
├── SKILL.md                  ← 编排入口（on-demand loading table、workflow with gates、error recovery）
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

## 各文件职责边界

| 文件 | 拥有的规则 | 不拥有的规则 |
|------|-----------|-------------|
| `classify.md` | source detection, intent, conclusion taxonomy, edge cases, evidence requirements, section mapping | cross-reference (duplicate/conflict/relation), interaction flow |
| `cross-reference.md` | duplicate/conflict/relation detection, cross-file escalation | individual classification, reply templates |
| `interaction.md` | overview table format, silent consent, 🔴 discussion flow, scaling, zero-actionable fast path | comment classification, dossier structure |
| `dossier-output.md` | dossier structure (A/B/C), reply endpoints, reply policy + gate, 7-check validation, Cross-File Pattern template | classification rules, interaction flow |
| `platform.md` | list_comments.py usage, JSON contract, prerequisites, dossier paths, handoff format | reply API commands (owned by dossier-output.md) |

## Eval Matrix

[eval-matrix.md](./eval-matrix.md) 包含 7 个回归场景，用于验证 skill 的行为正确性。
