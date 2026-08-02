# AI Toolkits

个人 AI agent skills 集合，跨平台共享，通过 [skills CLI](https://github.com/vercel-labs/skills) 分发。

## 安装

```bash
npx skills add LYY/ai-toolkits -g -y
```

## Skills

| Skill | 描述 |
|-------|------|
| [address-pr-comments-review](./skills/address-pr-comments-review/) | 交互式 PR review 处理：绑定 checkout、验证 PR、分类评论并确认处理路线，支持 Review Dossier、受限 Direct Fix、直接回复和状态恢复 |
| [financial-systems-testing](./skills/financial-systems-testing/) | 面向 agent 的金融语义测试，覆盖交易、支付、钱包、账本、风险/授信、结算、对账和参考数据；强调项目来源的不变量，并将通用测试实践路由到对应 skill |
| [GitHub CLI](./skills/github-cli/) | GitHub CLI（`gh`）面向 agent 的运行时指引，遇到 GitHub URL、issues、pull requests、Actions、releases 时优先用 `gh` 读取和操作，并遵循先读后写的安全流程 |
| [lightpanda](./skills/lightpanda/) | Lightpanda 轻量级 headless browser 指引，面向 agent 的 MCP 浏览、`fetch` 页面提取、Playwright/Puppeteer/chromedp 的 CDP 自动化，以及安装、Docker、flag 差异与 Chromium fallback 判断 |
| [omo-formal-plan-dual-review](./skills/omo-formal-plan-dual-review/) | [OMO（oh-my-openagent）](https://github.com/code-yeongyu/oh-my-openagent) 正式计划双审：仅在明确请求 Momus + Oracle 双审时，冻结同一计划版本并独立审查，仅最小修复计划，直到两者无条件批准同一 digest |
| [OpenSSL](./skills/openssl/) | OpenSSL 面向 agent 的运行时指引，聚焦密钥、CSR、证书检查、TLS 校验与常见格式转换，并强调证书/私钥安全检查 |

## 开发

- [AGENTS.md](./AGENTS.md) — skill 开发规范与设计原则
- [docs/](./docs/) — 维护者文档（架构说明、eval matrix）
