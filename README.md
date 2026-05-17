# AI Toolkits

个人 AI agent skills 集合，跨平台共享，通过 [skills CLI](https://github.com/vercel-labs/skills) 分发。

## 安装

```bash
npx skills add LYY/ai-toolkits -g -y
```

## Skills

| Skill | 描述 |
|-------|------|
| [address-pr-comments](./skills/address-pr-comments/) | 自动处理 GitHub PR review comments — 收集、分类、验证、修复、回复。全自动模式，适合单人快速处理 |
| [address-pr-comments-review](./skills/address-pr-comments-review/) | 交互式 PR review 处理 — 分类确认 → 生成 dossier → Prometheus 交互出 plan → `/start-work` 执行。内置去重、冲突检测、Scope Guardrails、失败恢复 |

## 特性

- **混合 review 支持**: 同时处理 human reviewer 和 AI bot（CodeRabbit、Copilot 等）的评论
- **已有回复检测**: 自动识别已回复的评论（`has_replies`），跳过重复处理
- **跨仓库支持**: `--repo owner/name` 参数支持在任意目录下操作远程 PR
- **去重与冲突检测** (review 模式): 多个 reviewer 对同一行代码的评论自动合并，冲突建议标记讨论
- **Scope Guardrails** (review 模式): dossier 内置防 scope creep 约束，禁止计划执行时顺手重构
- **异步流程支持**: `needs_clarification` 评论支持 reviewer 回复后重跑 skill，自动跳过已处理项
- **失败恢复** (review 模式): `/start-work` 中途失败可重新生成 dossier，仅处理剩余未完成项

## 开发

参见 [AGENTS.md](./AGENTS.md)。
