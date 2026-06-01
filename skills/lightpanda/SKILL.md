---
name: lightpanda
description: >-
  Use when a task needs a lightweight headless browser for web scraping, agent
  browsing via MCP, JavaScript-rendered page extraction, or CDP automation with
  Playwright, Puppeteer, or chromedp.
---

# Lightpanda

## Overview

Lightpanda is a lightweight headless browser built for agent and automation workflows. Prefer it when you need JavaScript-rendered page content, browser interaction, or CDP automation without paying the full Chrome/Chromium cost.

Use the highest-level interface that solves the task: MCP for agent browsing, `fetch` for one-shot extraction, CDP through Playwright/Puppeteer/chromedp for scripted automation, and Chromium only when Lightpanda's partial browser support is not enough.

## Use When

- you need markdown or semantic extraction from JavaScript-rendered pages
- you want an MCP-native browser for agent workflows
- you need a low-overhead CDP target for Playwright or Puppeteer
- you want fast startup or many short-lived browser processes

## Install & Verify

Prefer the package manager available in the environment. Verify the installed binary before using it.

```bash
# macOS
brew install lightpanda-io/browser/lightpanda

# Official installer
curl -fsSL https://pkg.lightpanda.io/install.sh | bash

# Docker CDP server, bound to localhost
docker run -d --name lightpanda -p 127.0.0.1:9222:9222 lightpanda/browser:nightly

# Verify installed binary
lightpanda version
lightpanda help
```

Set `LIGHTPANDA_DISABLE_TELEMETRY=true` when the environment requires telemetry opt-out. Windows has no native binary; use WSL2 or Docker.

## Common Workflows

### Interface Choice

| Interface | Use it for | Command |
|-----------|------------|---------|
| **MCP** | Default choice for agent browsing, clicking, filling, and page reads | `lightpanda mcp --obey-robots` |
| **fetch** | One-shot extraction when you only need page output | `lightpanda fetch --dump markdown --wait-until networkidle <URL>` |
| **CDP** | Playwright/Puppeteer/chromedp automation | `lightpanda serve --host 127.0.0.1 --port 9222 --timeout 0 --obey-robots` |
| **Chromium fallback** | Screenshots, PDF, visual testing, unsupported Web APIs, or broken Lightpanda flows | Use the platform browser automation skill/tool instead |

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

# Other useful dump modes: html, semantic_tree
lightpanda fetch --dump html --wait-until domcontentloaded https://example.com

# Start a CDP endpoint for Playwright/Puppeteer
lightpanda serve --host 127.0.0.1 --port 9222 --timeout 0 --obey-robots
```

### MCP Workflow

1. Navigate with `goto`.
2. Immediately verify with a read call such as `markdown`, `semantic_tree`, `links`, or `interactiveElements`.
3. Use `click`, `fill`, `scroll`, `waitForSelector`, or `evaluate` only after the page state is confirmed.
4. Re-read page content after each meaningful interaction instead of assuming the page changed as expected.

Native MCP transport is stdio. If an HTTP/SSE MCP endpoint is required, bridge it with a gateway such as `supergateway` instead of assuming Lightpanda serves HTTP MCP directly.

### CDP Workflow

1. Start one Lightpanda CDP process per independent automation lane.
2. Connect through Playwright or Puppeteer first; use lower-level CDP only when those libraries cannot express the action.
3. Always close pages/contexts in the client script, then stop the Lightpanda process when the task ends.

```javascript
import { chromium } from 'playwright-core';

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const context = browser.contexts()[0] ?? await browser.newContext();
const page = await context.newPage();

await page.goto('https://example.com', { waitUntil: 'networkidle' });
const title = await page.title();
const text = await page.locator('body').innerText();

console.log({ title, preview: text.slice(0, 200) });
await page.close();
await browser.close();
```

```javascript
import puppeteer from 'puppeteer-core';

const browser = await puppeteer.connect({
  browserWSEndpoint: 'ws://127.0.0.1:9222',
});
const page = await browser.newPage();

await page.goto('https://example.com', { waitUntil: 'networkidle0' });
const text = await page.evaluate(() => document.body.innerText);

console.log(text.slice(0, 200));
await page.close();
await browser.close();
```

## Safety Checks

- Verify page state with a read operation after `goto` and after important interactions.
- Prefer `fetch` when the task is extraction-only; do not introduce CDP complexity unless interaction is required.
- Use `--timeout 0` for long-lived CDP sessions that must stay open during agent-driven work.
- Bind CDP to `127.0.0.1` unless remote access is explicitly required.
- Use `--obey-robots` for web scraping and browsing unless the user explicitly provides permission to ignore robots rules.
- Run `lightpanda help` or `lightpanda <command> --help` before scripting uncommon flags.

## Gotchas

- **`goto` is not proof of success.** It reports navigation success even when the destination later fails to resolve or load. Always follow it with `markdown`, `semantic_tree`, `links`, or another read operation to confirm the page really loaded.
- **Official docs have mixed flag spellings.** Prefer current hyphenated flags such as `--obey-robots`, `--log-level`, `--log-format`, `--with-frames`, and `--insecure-disable-tls-host-verification`; if a command fails, check `lightpanda <command> --help` because older examples may use underscores.
- **Google commonly blocks Lightpanda.** Prefer direct URLs or non-Google search engines such as DuckDuckGo.
- **CDP support is lighter than full Chrome.** Some sites and advanced flows will still need Chromium-based automation.
- **Lightpanda is not for visual fidelity.** Use Chrome/Chromium for pixel-perfect screenshots, PDF generation, visual regression, and rendering-specific tests.
- **Long-running CDP sessions can disconnect if you keep the default timeout.** Use `--timeout 0` when a session must stay open for agent-driven interaction.
- **Parallel CDP work is better done with multiple processes.** If one session becomes a bottleneck, start another Lightpanda process on a different port.
- **Linux nightly builds are glibc-based.** Alpine/musl containers may need Docker image usage or a compatible base image.

## Recovery & Fallbacks

- If MCP is unavailable or unstable but the task is read-only, switch to `fetch`.
- If `fetch` is insufficient because the page needs clicks, forms, login, or scripted interaction, switch to CDP through Playwright/Puppeteer.
- If CDP cannot express the needed behavior, Web APIs are missing, or page output remains empty/incorrect after verified waits, fall back to a Chromium-based browser instead of forcing compatibility.
- Verify outcomes with read operations; do not repeat navigation or interaction blindly when you are unsure whether a previous step succeeded.
