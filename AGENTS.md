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
ln -sf ~/program/github/LYY/ai-toolkits/skills/<skill-name> ~/.agents/skills/<skill-name>
```

**不推荐 — 直接删除**：从仓库中彻底删除目录。

已在本地安装的废弃 skill，手动清理：

```bash
rm -rf ~/.agents/skills/<deprecated-skill-name>/
```

## 注意事项

- 每次修改 skill 后务必 push，否则 `skills add` 拉不到最新版本
- `skills add` 通过 `skillFolderHash` 比对是否需更新，不会重复安装
- 如果你用 symlink 指向本地仓库，`git pull` 后即时生效，无需 `skills add`
