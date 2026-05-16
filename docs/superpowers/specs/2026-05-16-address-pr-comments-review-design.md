# address-pr-comments-review Design

## 概述

`address-pr-comments-review` 是一个**两阶段交互式 skill**，增强 `address-pr-comments` 的自动化流程，
将 PR 评论审查拆分为「分析确认」和「plan 执行」两个独立阶段。

**平台特化**：专为 OpenCode + OhMyOpenCode (Sisyphus) 设计。
Plan 生成依赖 Sisyphus 的 Metis/Momus 审查链和 `start-work` 执行模式，不适用于其他 agent 平台。

- **阶段一**（本 skill）：AI 收集分类评论 → 交互确认 → 生成 Sisyphus plan
- **阶段二**（`start-work`）：用户按 plan 执行开发、测试、inline 回复

与现有 `address-pr-comments`（全自动一次性执行）互补：需要人工把关的 PR 用增强版，快速小修用原版。

## 工作流

```
PR 地址 / 自动检测
    ↓
[1] 收集评论（复用 list_comments.py）
    ↓
[2] AI 分类 + 验证（逐条分析，标记结论）
    ↓
[3] 输出概览表 → 交互讨论（沉默同意 + 争议讨论）
    ↓  讨论完毕
[4] 输出「讨论后最终概览表」→ 用户再次确认
    ↓  确认通过
[5] 生成 plan 草稿 → Metis 审查 → Momus 审查 → 输出终版 plan
    ↓
[6] 用户 /start-work 执行
```

## 各步骤详情

### [1] 收集评论

使用自带的 `list_comments.py`（从 `address-pr-comments` 复制，自包含无外部依赖）：

```bash
python3 ./scripts/list_comments.py --json
```

自动检测当前分支对应 PR；支持 `--pr <N>` 手动指定；支持 `--include-resolved`。

### [2] 分类 + 验证

对每条评论：
- **Source**：AI bot（coderabbit 等）vs Human
- **Intent**：`actionable`（需要处理）vs `informational`（LGTM/👍 等，跳过）
- **Conclusion**：`valid` / `invalid` / `already_fixed` / `out_of_scope` / `needs_clarification`
- **Discussion flag**：`needs_clarification` 的、或 AI 判断高风险的 `valid`，标记为 🔴 需讨论

借用原 skill `references/validation-checklist.md` 的验证流程。

### [3] 交互确认 — 概览表 + 沉默同意

AI 输出结构：

```
## PR #N 评论分析 — 共 X 条，其中 actionable Y 条

### 📋 概览
| # | 来源 | 类型 | 文件 | 摘要 | 结论 | 讨论 |
|---|------|------|------|------|------|------|
| 1 | @human | inline | foo.ts:42 | var → const | ✅ valid | |
| 2 | @bot   | inline | bar.ts:15 | 变量名建议 | ❌ invalid | |
| 3 | @human | inline | baz.ts:8  | 逻辑对吗？ | ⚠️ needs_clarification | 🔴 需讨论 |

### 🔴 需要讨论（N 条）
逐条展开细节...

### 📝 静默同意的（M 条）
表格中无标记的条目，按 AI 结论执行。有异议请指出。
```

**交互规则**：
- 用户沉默 / "继续" / "ok" → 全部同意
- 对某条有异议 → 用户明确指出，展开讨论
- `needs_clarification` 的必须用户给出方向

### [4] 讨论后最终概览表

所有讨论结束后，AI 输出最终确认表，反映所有讨论结果。用户再次确认后进入 plan 生成。

### [5] Plan 生成（Sisyphus 格式）

写入 `.sisyphus/plans/pr-<N>-review.md`。

#### Plan 结构

```markdown
# PR #N Review Plan

## 背景
- PR: <url>
- 分支: <branch>
- 分析时间: <timestamp>
- actionable 评论: X 条 | 待处理: Y 条

## 任务列表

### Task 1: Comment #M — <摘要>
- **开发**: <具体改动描述，含文件路径和行号>
- **测试**: <测试策略>
- **回复**: <inline/review/top_level> → @<author> "<模板>"
- **依赖**: []

### Task 2: ...

## 跳过的评论
- Comment #K: <结论> — <理由>

## 依赖关系
- Task 1~N 互不依赖，可并行执行
```

#### Plan 生成流程

1. AI 生成 plan 草稿
2. 调用 **Metis** 分析：找歧义、遗漏、AI 失败点
3. 调用 **Momus** 审查：检查清晰度、可验证性、完整性
4. 修正后写入最终 `.sisyphus/plans/pr-<N>-review.md`

### [6] start-work 执行

用户用 `start-work` 加载 plan 执行。每个 task：
- 切工作分支
- 实现代码改动
- 运行相关测试
- 用 `gh api` inline 回复评论
- 提交（不 push）

## 与现有 skill 的关系

| 维度 | address-pr-comments | address-pr-comments-review |
|------|---------------------|---------------------------|
| 模式 | 全自动一次性 | 两阶段交互 |
| 确认 | 无 | 逐轮确认 |
| Plan | 无 | Sisyphus plan |
| 适用 | 小 PR、信任度高 | 大 PR、需把关 |
| 复用 | — | 自包含，scripts/list_comments.py 从原 skill 复制 |

## 文件结构

```
skills/address-pr-comments-review/
  SKILL.md          # 核心 skill 定义
  scripts/
    list_comments.py  # 从 address-pr-comments 复制，自包含
  references/
    plan-template.md  # Plan 生成模板
```
