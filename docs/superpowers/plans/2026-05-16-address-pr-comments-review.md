# address-pr-comments-review Skill 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建 `address-pr-comments-review` skill — OpenCode + OMO (Sisyphus) 专用的两阶段交互式 PR 评论审查 skill

**Architecture:** 单文件 skill 定义（SKILL.md），复用原 skill 的 `list_comments.py`（复制副本），新增 `plan-template.md` 参考模板。核心流程：收集 → 分类验证 → 交互确认 → 生成 Sisyphus plan → start-work 执行

**Tech Stack:** Python 3 (list_comments.py), gh CLI, Sisyphus task/plan 系统

---

### 文件结构

```
skills/address-pr-comments-review/
  SKILL.md                          # 创建：核心 skill 定义
  scripts/
    list_comments.py                # 复制：从 address-pr-comments
  references/
    plan-template.md                # 创建：Plan 生成参考模板
```

---

### Task 1: 复制 list_comments.py 到新 skill

**Files:**
- Create: `skills/address-pr-comments-review/scripts/list_comments.py`

- [ ] **Step 1: 创建目录并复制脚本**

```bash
mkdir -p skills/address-pr-comments-review/scripts
cp skills/address-pr-comments/scripts/list_comments.py skills/address-pr-comments-review/scripts/
```

- [ ] **Step 2: 在复制文件顶部添加来源注释**

在 `list_comments.py` 开头（shebang 行之后）插入：
```python
# Source: skills/address-pr-comments/scripts/list_comments.py
# Vendored copy for self-contained deployment with npx skills add
```

- [ ] **Step 3: 验证脚本可执行**

```bash
python3 skills/address-pr-comments-review/scripts/list_comments.py --help
```

- [ ] **Step 4: Commit**

```bash
git add skills/address-pr-comments-review/scripts/list_comments.py
git commit -m "chore: vendor list_comments.py into address-pr-comments-review"
```

---

### Task 2: 创建 SKILL.md

**Files:**
- Create: `skills/address-pr-comments-review/SKILL.md`

**参考 Spec:** `docs/superpowers/specs/2026-05-16-address-pr-comments-review-design.md`

- [ ] **Step 1: 编写 SKILL.md** — 以下为完整内容

````markdown
---
name: address-pr-comments-review
description: Use when you need to review PR comments with human-in-the-loop confirmation before generating a Sisyphus implementation plan. Two-phase workflow — interactive analysis then plan generation. Designed for OpenCode + OhMyOpenCode (Sisyphus). Triggers: "review PR comments", "check PR feedback", "处理 PR 评论", "审查 PR 反馈", or when using address-pr-comments but need approval gates. NOT for quick automated fixes — use address-pr-comments instead.
---

# Address PR Comments — Review (增强版)

## Overview

**Platform-specific**: OpenCode + OhMyOpenCode (Sisyphus) only. Uses Sisyphus Metis/Momus review chain and `start-work` execution.

**Two-phase workflow**:

1. **Phase 1** (this skill): Collect → classify → validate → interactive confirmation → generate Sisyphus plan
2. **Phase 2** (`start-work`): User executes the plan — development, testing, inline replies

Use `address-pr-comments` for quick automated fixes. Use this skill when you need human oversight.

---

## Phase 1: Analysis & Plan Generation

### Step 1: Collect Comments

```bash
python3 ./scripts/list_comments.py --json
```

Auto-detects PR from current branch. Supports `--pr <N>` for manual PR, `--include-resolved` for resolved threads.

### Step 2: Classify + Validate

For each comment, determine:

**Source**: AI bot (coderabbit, reviewdog, etc.) vs Human

**Intent**:
- `actionable` — change requests, bugs, suggestions, questions → continue processing
- `informational` — LGTM, praise, emoji-only, FYI → skip, no reply

**Conclusion** (actionable only):
- `valid` — technically correct, still applies, in scope
- `invalid` — incorrect claim, unsafe, contradicts conventions
- `already_fixed` — issue no longer present in current HEAD
- `out_of_scope` — unrelated to this PR
- `needs_clarification` — ambiguous, needs user direction

**Discussion flag**: Mark as 🔴 if `needs_clarification` OR if AI judges the `valid` conclusion carries high risk.

Validation reference: `skills/address-pr-comments/references/validation-checklist.md`

### Step 3: Interactive Confirmation

Present a structured overview:

```
## PR #N 评论分析 — 共 X 条，其中 actionable Y 条

### 📋 概览
| # | 来源 | 类型 | 文件 | 摘要 | 结论 | 讨论 |
|---|------|------|------|------|------|------|
| 1 | @human | inline | path:line | 摘要 | ✅ valid | |
| 2 | @bot   | inline | path:line | 摘要 | ❌ invalid | |
| 3 | @human | review | -        | 摘要 | ⚠️ needs_clarification | 🔴 需讨论 |

### 🔴 需要讨论（N 条）
[逐条展开评论内容 + AI 分析 + 需要用户确认的问题]

### 📝 静默同意的（M 条）
无标记条目按 AI 结论执行。有异议请明确指出。
```

**Interaction rules**:
- User silence / "继续" / "ok" → all agreed
- User objects to specific items → discuss, reach resolution
- `needs_clarification` items → must get user direction before proceeding

### Step 4: Final Confirmation Table

After all discussion, output a **post-discussion summary table** reflecting all resolved decisions. User must confirm this final version before plan generation.

### Step 5: Generate Sisyphus Plan

Create plan at `.sisyphus/plans/pr-<N>-review.md`.

#### Plan structure — follow `references/plan-template.md`:

```markdown
# PR #N Review Plan

## 背景
- PR: <url>
- 分支: <branch>
- 分析时间: <timestamp>
- actionable 评论: X 条 | 待处理: Y 条

## 任务列表

### Task 1: Comment #M — <摘要>
- **开发**: <具体文件路径和改动>
- **测试**: <测试策略和命令>
- **回复**: <kind> → @<author> "<template>"
- **依赖**: []

### Task 2: ...

## 跳过的评论
- Comment #K: <结论> — <理由>

## 依赖关系
- Task 1~N 互不依赖，可并行执行
```

#### Plan review chain:

1. AI drafts the plan
2. **Metis** reviews: identifies ambiguities, missing items, AI failure points
3. **Momus** reviews: checks clarity, verifiability, completeness
4. AI incorporates feedback → final plan written to `.sisyphus/plans/pr-<N>-review.md`

### Step 6: Handoff

After plan is saved, instruct user:

```
Plan saved to .sisyphus/plans/pr-<N>-review.md

Run /start-work to execute.
```

---

## Interaction Checklist

At each step, the AI MUST:

| Step | Gate |
|------|------|
| After comment collection | ✅ Verify counts match expectations |
| Before showing overview | ✅ All comments classified + concluded |
| After user discussion | ✅ Step 4: output final confirmation table |
| Before plan generation | ✅ User confirmed final table |
| After plan draft | ✅ Metis + Momus reviews run |
| Before handoff | ✅ Final plan saved to disk |

---

## Key Principles

- **Silence = consent**: Don't ask "are you sure?" for every item. Present the table, flag discussion items, trust the user to object.
- **One plan = one PR**: Each PR review produces exactly one plan file.
- **Reuse, don't rebuild**: Use `list_comments.py` for collection. Don't reimplement gh CLI calls.
- **Platform lock**: This skill assumes Sisyphus (Metis, Momus, start-work). Not portable to other agents.

---

## Quick Reference

```bash
# Collect comments
python3 ./scripts/list_comments.py --json

# Manual PR
python3 ./scripts/list_comments.py --pr 2781 --json

# Include resolved threads
python3 ./scripts/list_comments.py --json --include-resolved
```
````

- [ ] **Step 2: 验证 SKILL.md 格式** — 检查 frontmatter name/description 符合规范

- [ ] **Step 3: Commit**

```bash
git add skills/address-pr-comments-review/SKILL.md
git commit -m "feat: add address-pr-comments-review skill (SKILL.md)"
```

---

### Task 3: 创建 plan-template.md

**Files:**
- Create: `skills/address-pr-comments-review/references/plan-template.md`

- [ ] **Step 1: 编写 plan-template.md** — 以下为完整内容

````markdown
# Plan Template for PR Review

This is the Sisyphus plan template used by `address-pr-comments-review` Step 5.
The AI generates the actual plan from this template, then Metis + Momus review it.

## Template

```markdown
# PR #{{PR_NUMBER}} Review Plan

> **For agentic workers:** Execute via `/start-work`. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Address actionable PR comments for {{PR_URL}}

**Architecture:** Per-comment tasks — each task handles development, testing, and inline reply for one comment. Tasks are independent and can execute in parallel.

**Tech Stack:** {{LANGUAGES_AND_FRAMEWORKS}}

---

### Task {{N}}: Comment #{{ID}} — {{SUMMARY}}

**Files:**
- Modify: `{{FILE_PATH}}:{{LINE}}`
- Test: `{{TEST_FILE_PATH}}`

- [ ] **Step 1: 实现代码改动**

```{{LANGUAGE}}
{{CODE_CHANGE}}
```

- [ ] **Step 2: 运行测试验证**

```bash
{{TEST_COMMAND}}
```
Expected: {{EXPECTED_RESULT}}

- [ ] **Step 3: 回复评论**

```bash
# For inline comments:
gh api repos/{{OWNER}}/{{REPO}}/pulls/{{PR_NUMBER}}/comments --method POST \
  -F body="{{REPLY_TEXT}}" \
  -F commit_id=$(git rev-parse HEAD) \
  -F path="{{FILE_PATH}}" \
  -F line={{LINE}} \
  -F side=RIGHT \
  -F in_reply_to={{COMMENT_ID}}

# For review body / top-level comments:
gh api repos/{{OWNER}}/{{REPO}}/issues/{{PR_NUMBER}}/comments --method POST \
  -F body="{{REPLY_TEXT}}"
```

- [ ] **Step 4: Commit per-comment**

```bash
git add {{FILES}}
git diff --staged --stat
git commit -m "{{COMMIT_MESSAGE}}"
```

---

## 跳过的评论

| # | 来源 | 结论 | 理由 |
|---|------|------|------|
{{#each skipped}}
| {{id}} | @{{author}} | {{conclusion}} | {{reason}} |
{{/each}}

## 依赖关系

- All tasks are independent — execute in parallel.
```

## Reply Templates

Per outcome, use these reply templates:

| Outcome | Reply |
|---------|-------|
| `valid` (fixed) | `Fixed in <commit_sha>.` |
| `invalid` | `This suggestion doesn't apply because <brief reason>.` |
| `already_fixed` | `Already resolved in the current code — no changes needed.` |
| `out_of_scope` | `This is outside the scope of this PR. <Optional: suggest follow-up>.` |
| `needs_clarification` | `Confirmed: <resolved direction>.` |
````

- [ ] **Step 2: Commit**

```bash
git add skills/address-pr-comments-review/references/plan-template.md
git commit -m "feat: add plan-template.md for address-pr-comments-review"
```

---

### Task 4: 自检 & 最终验证

- [ ] **Step 1: 检查文件完整性**

```bash
tree skills/address-pr-comments-review/
```
Expected:
```
skills/address-pr-comments-review/
├── SKILL.md
├── scripts/
│   └── list_comments.py
└── references/
    └── plan-template.md
```

- [ ] **Step 2: 检查 SKILL.md frontmatter 规范**

```bash
head -6 skills/address-pr-comments-review/SKILL.md
```
Expected: `name: address-pr-comments-review`, `description: Use when...`

- [ ] **Step 3: 验证 list_comments.py 正常工作**（如果有可用的 gh CLI 环境）

```bash
python3 skills/address-pr-comments-review/scripts/list_comments.py --help
```
Expected: usage output

- [ ] **Step 4: 对照 spec 逐项检查**

| Spec 要点 | Plan 覆盖 |
|-----------|----------|
| 两阶段交互 | SKILL.md Phase 1 + 2 |
| 平台特化声明 | Overview "Platform-specific" |
| 概览表格式 | Step 3 完整格式 |
| 沉默同意 | Interaction rules + Key Principles |
| 讨论后最终确认表 | Step 4 |
| Metis + Momus 审查 | Step 5 |
| start-work 执行 | Step 6 + plan template |
| 自包含 (scripts 副本) | Task 1 |
| Plan 模板 | Task 3 |

- [ ] **Step 5: Commit**

```bash
git add -A
git diff --staged --stat
git commit -m "chore: finalize address-pr-comments-review skill"
```

---

## 执行顺序

```
Task 1 (复制脚本) → Task 2 (SKILL.md) → Task 3 (plan-template.md)
                                                   ↓
                                          Task 4 (最终验证)
```

Task 1~3 无相互依赖，可并行。Task 4 依赖前三者完成。
