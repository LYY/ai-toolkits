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
| [address-pr-comments-review](./skills/address-pr-comments-review/) | 交互式 PR review 处理，先绑定当前 checkout，再验证 PR，分类确认后复杂改动生成本地 Markdown dossier，简单低风险改动可生成 Direct Fix Brief 直接执行；OMO/Prometheus 通过可复制 prompt 可选接手。内置去重、冲突检测、Scope Guardrails、回复验证和 artifact cleanup |
| [GitHub CLI](./skills/github-cli/) | GitHub CLI（`gh`）面向 agent 的运行时指引，遇到 GitHub URL、issues、pull requests、Actions、releases 时优先用 `gh` 读取和操作，并遵循先读后写的安全流程 |
| [lightpanda](./skills/lightpanda/) | Lightpanda 轻量级 headless browser 指引，面向 agent 的 MCP 浏览、`fetch` 页面提取、Playwright/Puppeteer/chromedp 的 CDP 自动化，以及安装、Docker、flag 差异与 Chromium fallback 判断 |
| [OpenSSL](./skills/openssl/) | OpenSSL 面向 agent 的运行时指引，聚焦密钥、CSR、证书检查、TLS 校验与常见格式转换，并强调证书/私钥安全检查 |

## 特性

- **混合 review 支持**: 同时处理 human reviewer 和 AI bot（CodeRabbit、Copilot 等）的评论
- **已有回复检测**: 自动识别已回复的评论，跳过重复处理
- **跨仓库支持**: `--repo owner/name` 支持在任意目录下操作远程 PR
- **worktree-aware checkout 绑定**: 默认使用当前 Git root，只有 submodule、detached HEAD、PR 分支不匹配等风险场景才停下确认；后续本地读取和 git 命令都绑定同一个目标根目录
- **本地 Markdown dossier handoff**: 将分类结果、Section A/B reply task 和执行约束写入 `~/.local/state/ai-toolkits/pr-comments/...`，输出 generic executor 与 OMO/Prometheus 可复制 prompt
- **Direct Fix Brief**: 对单文件、低风险、无冲突的简单 Section A 评论，可在明确确认后跳过 Prometheus，保留验证、commit、回复和 read-back 要求直接执行
- **Artifact cleanup**: `/address-pr-comments-review cleanup` 清理当前 PR 默认 artifact，`cleanup-all` 批量清理默认 state root，删除前预览并确认
- **Dossier Accuracy Grill Gate**: 写 dossier 或 Direct Fix Brief 前，只对未决的实现、范围、验证或回复问题做一问一答确认，避免带着歧义交接
- **去重与冲突检测**: 多个 reviewer 对同一行代码的评论自动合并，冲突建议标记讨论
- **Scope Guardrails**: dossier 内置防 scope creep 约束，禁止计划执行时顺手重构
- **异步流程支持**: `needs_clarification` 评论支持 reviewer 回复后重跑 skill，自动跳过已处理项
- **失败恢复**: `/start-work` 中途失败可重新生成 dossier，仅处理剩余未完成项
- **面向 agent 设计**: 按执行阶段组织 reference，按需加载，不做学术分层

## 开发

- [AGENTS.md](./AGENTS.md) — skill 开发规范与设计原则
- [docs/](./docs/) — 维护者文档（架构说明、eval matrix）
