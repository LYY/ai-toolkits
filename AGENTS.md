# AI Toolkits - Skills

个人 AI agent skills 集合，通过 [skills CLI](https://github.com/vercel-labs/skills) 分发到 OpenCode、Cursor、Claude Code、Gemini CLI、GitHub Copilot 等 agents。

## Skills 结构

每个 skill 一个目录，放在 `skills/` 下：

```
skills/
└── <skill-name>/
    ├── SKILL.md          # 必需：skill 定义（含 frontmatter name + description）
    ├── scripts/          # 可选：辅助脚本
    └── references/       # 可选：参考文档
```

`SKILL.md` frontmatter 示例：

```yaml
---
name: my-skill
description: 一句话描述 skill 的用途和触发条件
---
```

## 工作流

### 新增 skill

1. 在 `skills/` 下创建 `<skill-name>/SKILL.md`
2. 提交并推送：

```bash
git add skills/<skill-name>/
git commit -m "feat: add <skill-name> skill"
git push
```

### 更新 skill

直接修改 `SKILL.md` 或相关文件，提交推送即可。

### 同步到本地 agents

推送后，在本地执行：

```bash
npx skills add LYY/ai-toolkits -g -y
```

- 新 skill 会被安装到 `~/.agents/skills/`
- 已有 skill 会检测更新并同步
- `-g` 全局安装，`-y` 跳过确认

### 仅更新已安装的 skill

```bash
npx skills update <skill-name> -g
```

## 废弃 Skill

废弃的 skill 不推荐新用户安装。`skills add` 会全量安装 `skills/` 下所有 skill，要阻止安装，按推荐优先级：

**推荐 — 移入 `archive/`**：保留代码备查，但不会被自动安装：

```bash
mkdir -p archive
mv skills/<skill-name> archive/
```

**备选 — symlink**：用 symlink 接管 `~/.agents/skills/`，手动控制暴露哪些 skill：

```bash
ln -sf <repo-path>/skills/<skill-name> ~/.agents/skills/<skill-name>
```

**不推荐 — 直接删除**：从仓库中彻底删除目录。

已在本地安装的废弃 skill，手动清理：

```bash
rm -rf ~/.agents/skills/<deprecated-skill-name>/
```

## Skill 设计原则（面向 agent，而非面向人类维护者）

skill 的主要受众是 **runtime agent**（执行操作的 AI），次要受众才是人类维护者。以下原则从 `address-pr-comments-review` 的精简过程中提炼：

### 1. references/ 只放 agent 运行时需要读的内容

维护者文档（架构设计、设计决策、eval matrix、precedence model）放在 `docs/`，不要混入 `references/`。agent 加载 skill 时不应浪费 token 在读这些内容上。

### 2. 按执行阶段组织文件，不要按"职责域"学术分类

对 agent 而言，`classification + cross-reference` 是同一个 Step 2 的动作，`dossier + reply + validation` 是同一个 Step 4 的产出。拆成"一个协议层一个文件"会增加跨文件追踪成本。agent 关心的是"这一 step 我该做什么"，而不是"这个文件属于 Layer 2 还是 Layer 3"。

### 3. 一个概念不要跨文件追踪

如果一个结论（如 `partially_addressed`）的行为需要跨越 classification → dossier → reply → validation 四个文件才能完整理解，那就该合并。agent 不应在 4 个文件之间跳转来搞清楚一个东西怎么处理。

### 4. 去掉维护者元数据段落

以下段落对 agent 执行无价值，应移除或归入 `docs/`：
- `## Precedence` — agent 跟着 SKILL.md 的 step 走，不需要知道文件属于第几层
- `## Scope / ## Out of Scope` — 文件内容自明职责
- `## Key Design Decisions` — 设计决策记录，不是操作指令

### 5. 按需加载 + 自包含，不假设全量 context

每个 reference 文件应能独立完成其核心职责，不依赖未加载文件的上下文。如果必须跨文件引用，只允许两种安全模式：
- **前向引用**：引用后续 step 会加载的文件（如 cross-reference → dossier-output，Step 4 加载时自动解析）
- **后向引用**：引用同一 session 中已加载的文件（如 dossier-output → classify，Step 2a 时已读）

禁止跳跃引用到不在执行路径上的文件。SKILL.md 的 Minimal Path 应指引 agent "这一 step 只需读这一个文件"，而不是"请按序读完所有 7 个文件"。

### 6. SKILL.md 是编排入口

SKILL.md 只放 workflow steps、prerequisites、error recovery、quick reference。不要把操作规则内联写到 SKILL.md 里——那是 reference 文件的职责。SKILL.md 负责"告诉你什么时候去读哪个文件"。

### 精简自检清单

skill 完成后，从 agent 视角过一遍：

- [ ] `references/` 下的每个文件，agent 真的会在执行时读吗？如果不会，移到 `docs/`
- [ ] 有没有同一个概念需要跨 3+ 个文件才能理解？如果有，合并
- [ ] 每个 reference 文件里还有没有 Precedence / Scope / Key Design Decisions 段落？如果有，移除
- [ ] SKILL.md 的 Minimal Path 是否指引"按 step 按需加载"，而不是"按序全读"？
- [ ] `references/` 文件总数是否 ≤ 5？超过则检查是否有过度拆分
- [ ] 对每个跨文件引用，画出 agent 执行时间线，确认引用指向当前 step 或相邻 step 加载的文件？跳跃引用到无关文件 → 不安全

## 注意事项

- 每次修改 skill 后务必 push，否则 `skills add` 拉不到最新版本
- `skills add` 通过 `skillFolderHash` 比对是否需更新，不会重复安装
- 如果你用 symlink 指向本地仓库，`git pull` 后即时生效，无需 `skills add`
