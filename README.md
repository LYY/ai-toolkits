# AI Toolkits

个人 AI agent skills 集合，跨平台共享，通过 [skills CLI](https://github.com/vercel-labs/skills) 分发。

## 安装

```bash
npx skills add LYY/ai-toolkits -g -y
```

## Skills

| Skill | 描述 |
|-------|------|
| ~~address-pr-comments~~ | ⚠️ **已废弃** — 不再维护，历史快照移至 [`archive/`](./archive/) 保留。不会随 `skills add` 自动安装 |
| [address-pr-comments-review](./skills/address-pr-comments-review/) | 交互式 PR review 处理，先绑定当前 checkout，再验证 PR，分类确认后生成 `.omo` dossier 交给 Prometheus 出 plan，最后由 `/start-work` 执行。内置去重、冲突检测、Scope Guardrails、失败回复等 |
| [GitHub CLI](./skills/github-cli/) | GitHub CLI（`gh`）面向 agent 的运行时指引，遇到 GitHub URL、issues、pull requests、Actions、releases 时优先用 `gh` 读取和操作，并遵循先读后写的安全流程 |
| [lightpanda](./skills/lightpanda/) | Lightpanda 轻量级 headless browser 指引，面向 agent 的 MCP 浏览、`fetch` 页面提取、Playwright/Puppeteer/chromedp 的 CDP 自动化，以及安装、Docker、flag 差异与 Chromium fallback 判断 |
| [OpenSSL](./skills/openssl/) | OpenSSL 面向 agent 的运行时指引，聚焦密钥、CSR、证书检查、TLS 校验与常见格式转换，并强调证书/私钥安全检查 |

## 特性

- **混合 review 支持**: 同时处理 human reviewer 和 AI bot（CodeRabbit、Copilot 等）的评论
- **已有回复检测**: 自动识别已回复的评论，跳过重复处理
- **跨仓库支持**: `--repo owner/name` 支持在任意目录下操作远程 PR
- **worktree-aware checkout 绑定**: 默认使用当前 Git root，只有 submodule、detached HEAD、PR 分支不匹配等风险场景才停下确认；后续本地读取、git 命令和 dossier 路径都绑定同一个目标根目录
- **`.omo` dossier handoff**: 将分类结果、Section A/B reply task 和执行约束写入目标 checkout 下的 `.omo` dossier，供后续 plan 和 `/start-work` 接手
- **去重与冲突检测**: 多个 reviewer 对同一行代码的评论自动合并，冲突建议标记讨论
- **Scope Guardrails**: dossier 内置防 scope creep 约束，禁止计划执行时顺手重构
- **异步流程支持**: `needs_clarification` 评论支持 reviewer 回复后重跑 skill，自动跳过已处理项
- **失败恢复**: `/start-work` 中途失败可重新生成 dossier，仅处理剩余未完成项
- **面向 agent 设计**: 按执行阶段组织 reference，按需加载，不做学术分层

## 开发

- [AGENTS.md](./AGENTS.md) — skill 开发规范与设计原则
- [docs/](./docs/) — 维护者文档（架构说明、eval matrix）
