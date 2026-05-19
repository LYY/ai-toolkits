# Architecture: address-pr-comments-review

维护者视图的 skill 架构说明。运行时 agent 不读此文件——它只需要 `SKILL.md` 和 4 个 reference 文件。

## 文件结构

```
skills/address-pr-comments-review/
├── SKILL.md                  ← 编排入口（workflow steps、prerequisites、error recovery）
├── references/
│   ├── analyze.md            ← Step 2: 分类 + 交叉引用（source/intent/conclusion + dedup/conflict/escalation）
│   ├── interaction.md        ← Step 3: 交互确认（overview table、silent consent、discussion flow）
│   ├── output.md             ← Step 4: dossier + reply + 验证（模板、reply policy、gates）
│   └── platform.md           ← 运行时命令 + JSON contract
└── scripts/list_comments.py  ← PR 评论采集脚本
```

## 设计原则

参见 `AGENTS.md` 中 `## Skill 设计原则` 章节。核心要点：

- **面向 agent 设计**：按执行阶段组织，不按协议层位分类
- **按需加载**：每个 phase 只需读 1 个 reference 文件，各自包含
- **references/ 不放维护者内容**：架构文档、eval matrix 归入 `docs/`

## 各文件职责边界

| 文件 | 拥有的规则 | 不拥有的规则 |
|------|-----------|-------------|
| `analyze.md` | source detection, intent, conclusion taxonomy, evidence requirements, edge cases, section mapping, duplicate/conflict/relation/cross-file detection | interaction flow, reply templates, dossier format |
| `interaction.md` | overview table format, silent consent, 🔴 discussion flow, scaling, confirmation gates | comment classification, dossier structure |
| `output.md` | dossier structure (A/B/C), reply endpoints, reply templates + gate, validation checks, regression scenarios | classification rules, interaction flow |
| `platform.md` | list_comments.py usage, JSON contract, prerequisites, dossier paths, handoff format | reply API commands (owned by output.md) |

## Eval Matrix

`docs/address-pr-comments-review/eval-matrix.md` 包含 7 个回归场景。用于验证 skill 的行为正确性。不是 runtime 文件。
