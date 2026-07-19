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
| [address-pr-comments-review](./skills/address-pr-comments-review/) | 交互式 PR review 处理：绑定 checkout 后验证 PR，分类确认后生成 local artifacts 交接执行，支持 complexity-gated bounded Direct Fix、按 comment kind 路由的 direct reply 和 status-based resume。内置去重、冲突检测、Scope Guardrails、回复验证和 cleanup gates |
| [GitHub CLI](./skills/github-cli/) | GitHub CLI（`gh`）面向 agent 的运行时指引，遇到 GitHub URL、issues、pull requests、Actions、releases 时优先用 `gh` 读取和操作，并遵循先读后写的安全流程 |
| [lightpanda](./skills/lightpanda/) | Lightpanda 轻量级 headless browser 指引，面向 agent 的 MCP 浏览、`fetch` 页面提取、Playwright/Puppeteer/chromedp 的 CDP 自动化，以及安装、Docker、flag 差异与 Chromium fallback 判断 |
| [OpenSSL](./skills/openssl/) | OpenSSL 面向 agent 的运行时指引，聚焦密钥、CSR、证书检查、TLS 校验与常见格式转换，并强调证书/私钥安全检查 |

## 特性

- **混合 review 支持**: 同时处理 human reviewer 和 AI bot（CodeRabbit、Copilot 等）的评论
- **已有回复检测**: 自动识别已回复的评论，跳过重复处理
- **跨仓库支持**: `--repo owner/name` 支持在任意目录下操作远程 PR
- **worktree-aware checkout 绑定**: 默认使用当前 Git root，只有 submodule、detached HEAD、PR 分支不匹配等风险场景才停下确认；后续本地读取和 git 命令都绑定同一个目标根目录
- **generic artifacts**: 分类结果和 reply tasks 写入 local state directory，输出任意 executor 可消费的交接产物；Review Dossier 与 Direct Fix Brief 各自只提供一个适用的 handoff
- **direct reply**: 无代码变更的 inline、review-level 或 top-level 回复按 comment kind 选择 root `/replies` 或 issue timeline endpoint，POST body 仅含 `body`，再按 route-specific read-back 验证；Direct Fix 最多包含 5 个 Section A task，至多一条不超过 3 个节点的有序链，其余必须是独立 singleton，且通过 complexity certificate 和 informed final-table confirmation；实现与直接验证 companion 保持在同一 task 内，执行始终 serial、每 task 独立 commit，失败即停止批次
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
