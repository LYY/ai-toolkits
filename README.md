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
| [address-pr-comments-review](./skills/address-pr-comments-review/) | 交互式 PR review 处理：绑定 checkout、验证 PR、分类评论并确认处理路线，支持 Review Dossier、受限 Direct Fix、直接回复和状态恢复 |
| [financial-systems-testing](./skills/financial-systems-testing/) | 面向 agent 的金融语义测试，覆盖交易、支付、钱包、账本、风险/授信、结算、对账和参考数据；强调项目来源的不变量，并将通用测试实践路由到对应 skill |
| [GitHub CLI](./skills/github-cli/) | GitHub CLI（`gh`）面向 agent 的运行时指引，遇到 GitHub URL、issues、pull requests、Actions、releases 时优先用 `gh` 读取和操作，并遵循先读后写的安全流程 |
| [lightpanda](./skills/lightpanda/) | Lightpanda 轻量级 headless browser 指引，面向 agent 的 MCP 浏览、`fetch` 页面提取、Playwright/Puppeteer/chromedp 的 CDP 自动化，以及安装、Docker、flag 差异与 Chromium fallback 判断 |
| [OpenSSL](./skills/openssl/) | OpenSSL 面向 agent 的运行时指引，聚焦密钥、CSR、证书检查、TLS 校验与常见格式转换，并强调证书/私钥安全检查 |

## 特性

- **混合 review 支持**: 同时处理 human reviewer 和 AI bot（CodeRabbit、Copilot 等）的评论
- **已有回复检测**: 自动识别已回复的评论，跳过重复处理
- **跨仓库支持**: `--repo owner/name` 支持在任意目录下操作远程 PR
- **checkout 绑定**: 默认使用当前 Git root，分支或 PR 不匹配时先停止确认；本地读取和 Git 命令始终绑定同一 checkout
- **受限 Direct Fix**: 仅接受明确的 `locus-change` 或 `verification-only` 模式，使用 typed locus selectors 和唯一的 `expected_paths` 范围；最多 5 个任务，最多一条不超过 3 个节点的有序链，始终串行执行
- **安全回复**: 无代码变更的 inline、review-level 或 top-level 回复使用对应 endpoint，POST body 仅含 `body`，并通过 route-specific read-back 验证
- **失败边界**: Direct Fix 在安全检查点发生 task-local failure 时只阻断当前任务及传递依赖；全局、不安全或未协调外部写入立即停止，避免重复副作用。详见 [Direct Fix Failure Scope Matrix](./skills/address-pr-comments-review/references/dossier-output.md#direct-fix-failure-scope-matrix)
- **cleanup gates**: 删除前预览并确认，支持单 PR 和批量清理
- **accuracy gate**: 写入产物前，只对未决的实现、范围、验证或回复问题做一问一答确认，避免带着歧义交接
- **去重与冲突检测**: 多个 reviewer 对同一行代码的评论自动合并，冲突建议标记讨论
- **Scope Guardrails**: 交接产物内置防 scope creep 约束
- **异步流程支持**: `needs_clarification` 评论支持 reviewer 回复后重跑，自动跳过已处理项
- **status-based resume**: 流程中断后可从剩余未完成项继续
- **面向 agent 设计**: 按执行阶段组织 reference，按需加载

## 开发

- [AGENTS.md](./AGENTS.md) — skill 开发规范与设计原则
- [docs/](./docs/) — 维护者文档（架构说明、eval matrix）
