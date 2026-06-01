---
name: lightpanda
description: >-
  Use when a task needs a lightweight headless browser for web scraping, agent
  browsing via MCP, or CDP automation with Playwright/Puppeteer.
---

# Lightpanda

## Overview

Lightpanda is a lightweight headless browser built for agent and automation workflows. Prefer it when you need rendered page content or browser interaction without paying the full Chrome/Chromium cost.

## Use When

- you need markdown or semantic extraction from JavaScript-rendered pages
- you want an MCP-native browser for agent workflows
- you need a low-overhead CDP target for Playwright or Puppeteer
- you want fast startup or many short-lived browser processes

## Common Workflows

### Interface Choice

| Interface | Use it for | Command |
|-----------|------------|---------|
| **MCP** | Default choice for agent browsing, clicking, filling, and page reads | `lightpanda mcp --obey-robots` |
| **fetch** | One-shot extraction when you only need page output | `lightpanda fetch --dump markdown --wait-until networkidle <URL>` |
| **CDP** | Playwright/Puppeteer automation or lower-level browser control | `lightpanda serve --host 127.0.0.1 --port 9222 --timeout 0 --obey-robots` |

## Quick Reference

```bash
# Verify installation
lightpanda version

# Start MCP server for agent workflows
lightpanda mcp --obey-robots

# Extract readable content from a page
lightpanda fetch --dump markdown --wait-until networkidle https://example.com

# Extract semantic structure for reasoning or element targeting
lightpanda fetch --dump semantic_tree_text --wait-until networkidle https://example.com

# Start a CDP endpoint for Playwright/Puppeteer
lightpanda serve --host 127.0.0.1 --port 9222 --timeout 0 --obey-robots
```

### MCP Workflow

1. Navigate with `goto`.
2. Immediately verify with a read call such as `markdown`, `semantic_tree`, `links`, or `interactiveElements`.
3. Use `click`, `fill`, `scroll`, `waitForSelector`, or `evaluate` only after the page state is confirmed.
4. Re-read page content after each meaningful interaction instead of assuming the page changed as expected.

## Safety Checks

- Verify page state with a read operation after `goto` and after important interactions.
- Prefer `fetch` when the task is extraction-only; do not introduce CDP complexity unless interaction is required.
- Use `--timeout 0` for long-lived CDP sessions that must stay open during agent-driven work.

## Gotchas

- **`goto` is not proof of success.** It reports navigation success even when the destination later fails to resolve or load. Always follow it with `markdown`, `semantic_tree`, `links`, or another read operation to confirm the page really loaded.
- **Google commonly blocks Lightpanda.** Prefer direct URLs or non-Google search engines such as DuckDuckGo.
- **CDP support is lighter than full Chrome.** Some sites and advanced flows will still need Chromium-based automation.
- **Long-running CDP sessions can disconnect if you keep the default timeout.** Use `--timeout 0` when a session must stay open for agent-driven interaction.
- **Parallel CDP work is better done with multiple processes.** If one session becomes a bottleneck, start another Lightpanda process on a different port.

## Recovery & Fallbacks

- If MCP is unavailable or unstable, switch to `fetch` for one-shot extraction.
- If `fetch` is insufficient because the page needs clicks, forms, or scripted interaction, switch to CDP.
- If a site still fails under Lightpanda, fall back to a Chromium-based browser instead of forcing compatibility.
- Verify outcomes with read operations; do not repeat navigation or interaction blindly when you are unsure whether a previous step succeeded.
