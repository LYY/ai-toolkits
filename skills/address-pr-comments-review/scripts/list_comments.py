#!/usr/bin/env python3
# Active copy for address-pr-comments-review.
# The archived address-pr-comments skill is no longer maintained.
#
# Script-to-skill contract: this script outputs JSON with fields
# consumed by the skill: kind, id, author, is_ai, created_at, url, body,
# excerpt, ai_prompts, has_replies, thread_resolved, thread_outdated,
# path, line (path/line are inline-only). The JSON contract is documented in references/platform.md.
"""
Collect and normalize GitHub PR feedback via gh CLI.

Usage:
  python3 scripts/list_comments.py
  python3 scripts/list_comments.py --pr 2781
  python3 scripts/list_comments.py --json
  python3 scripts/list_comments.py --include-resolved
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from typing import Any


AI_LOGIN_HINTS = (
    "bot",
    "ai",
    "coderabbit",
    "copilot",
    "reviewdog",
    "sonarqube",
    "deepsource",
    "codecov",
    "dependabot",
    "renovate",
)

REVIEW_THREADS_QUERY = """
query($owner:String!, $repo:String!, $number:Int!, $cursor:String) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      reviewThreads(first:100, after:$cursor) {
        nodes {
          id
          isResolved
          isOutdated
          comments(first:100) {
            nodes {
              databaseId
              author {
                login
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""


def run_gh(args: list[str]) -> str:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"gh {' '.join(args)} failed")
    return proc.stdout


def ensure_gh() -> None:
    if shutil.which("gh") is None:
        raise RuntimeError("gh CLI is not installed or not in PATH")
    _ = run_gh(["--version"])


def resolve_pr_number(pr: int | None, repo: str | None = None) -> int:
    if pr:
        return pr
    args = ["pr", "view", "--json", "number"]
    if repo:
        args.extend(["--repo", repo])
    data = json.loads(run_gh(args))
    return int(data["number"])


def parse_repo_from_pr_url(url: str) -> tuple[str, str]:
    match = re.search(r"github\.com/([^/]+)/([^/]+)/pull/\d+", url)
    if not match:
        raise RuntimeError(f"Could not parse owner/repo from PR URL: {url}")
    return match.group(1), match.group(2)


def is_ai_reviewer(login: str) -> bool:
    lowered = (login or "").lower()
    return any(hint in lowered for hint in AI_LOGIN_HINTS)


def body_excerpt(body: str, limit: int = 220) -> str:
    text = " ".join((body or "").split())
    return text[:limit]


def extract_ai_prompts(body: str) -> list[str]:
    if not body:
        return []

    prompts: list[str] = []

    # Common CodeRabbit section pattern.
    heading_re = re.compile(
        r"(?is)prompt for ai agents.*?```+\n(.*?)```+",
    )
    prompts.extend(m.group(1).strip() for m in heading_re.finditer(body))

    # Common generated instruction line pattern.
    instruction_re = re.compile(r"(?m)^In @.+$")
    prompts.extend(m.group(0).strip() for m in instruction_re.finditer(body))

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for prompt in prompts:
        if prompt and prompt not in seen:
            seen.add(prompt)
            unique.append(prompt)
    return unique


def normalize_top_level(
    comments: list[dict[str, Any]],
    reply_map: dict[int, bool] | None = None,
) -> list[dict[str, Any]]:
    if reply_map is None:
        reply_map = {}
    normalized = []
    for comment in comments:
        login = comment.get("author", {}).get("login", "")
        body = comment.get("body", "")
        comment_id = comment.get("id")
        normalized.append(
            {
                "kind": "top_level",
                "id": comment_id,
                "author": login,
                "is_ai": is_ai_reviewer(login),
                "created_at": comment.get("createdAt"),
                "url": comment.get("url"),
                "body": body,
                "excerpt": body_excerpt(body),
                "ai_prompts": extract_ai_prompts(body),
                "has_replies": bool(
                    reply_map.get(comment_id) if comment_id is not None else False
                ),
            }
        )
    return normalized


def normalize_reviews(
    reviews: list[dict[str, Any]],
    reply_map: dict[int, bool] | None = None,
) -> list[dict[str, Any]]:
    if reply_map is None:
        reply_map = {}
    normalized = []
    for review in reviews:
        login = review.get("author", {}).get("login", "")
        body = review.get("body", "") or ""
        review_id = review.get("id")
        normalized.append(
            {
                "kind": "review",
                "id": review_id,
                "author": login,
                "is_ai": is_ai_reviewer(login),
                "state": review.get("state"),
                "submitted_at": review.get("submittedAt"),
                "body": body,
                "excerpt": body_excerpt(body),
                "ai_prompts": extract_ai_prompts(body),
                "has_replies": bool(
                    reply_map.get(review_id) if review_id is not None else False
                ),
            }
        )
    return normalized


def collect_review_thread_status(
    owner: str, repo: str, pr: int
) -> dict[int, dict[str, Any]]:
    by_comment_id: dict[int, dict[str, Any]] = {}
    cursor: str | None = None

    while True:
        args = [
            "api",
            "graphql",
            "-f",
            f"owner={owner}",
            "-f",
            f"repo={repo}",
            "-F",
            f"number={pr}",
            "-f",
            f"query={REVIEW_THREADS_QUERY}",
        ]
        if cursor:
            args.extend(["-f", f"cursor={cursor}"])

        response = json.loads(run_gh(args))
        review_threads = (
            response.get("data", {})
            .get("repository", {})
            .get("pullRequest", {})
            .get("reviewThreads", {})
        )

        for thread in review_threads.get("nodes", []):
            thread_comments = thread.get("comments", {}).get("nodes", [])
            total_comments = len(thread_comments)
            # A thread has replies if it has > 1 comment AND at least
            # one comment is from a non-AI (presumably human) author.
            human_reply_count = sum(
                1
                for c in thread_comments
                if not is_ai_reviewer((c.get("author") or {}).get("login", ""))
            )
            has_replies = total_comments > 1 and human_reply_count >= 1

            status = {
                "thread_id": thread.get("id"),
                "thread_resolved": bool(thread.get("isResolved")),
                "thread_outdated": bool(thread.get("isOutdated")),
                "has_replies": has_replies,
            }
            for comment in thread_comments:
                database_id = comment.get("databaseId")
                if database_id is not None:
                    by_comment_id[int(database_id)] = status

        page_info = review_threads.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not cursor:
            break

    return by_comment_id


def normalize_inline(
    comments: list[dict[str, Any]],
    review_thread_status: dict[int, dict[str, Any]],
    include_resolved: bool,
) -> list[dict[str, Any]]:
    normalized = []
    for comment in comments:
        comment_id = comment.get("id")
        thread_status = (
            review_thread_status.get(int(comment_id))
            if comment_id is not None
            else None
        )
        if (
            not include_resolved
            and thread_status is not None
            and thread_status.get("thread_resolved")
        ):
            continue
        login = comment.get("user", {}).get("login", "")
        body = comment.get("body", "") or ""
        normalized.append(
            {
                "kind": "inline",
                "id": comment_id,
                "author": login,
                "is_ai": is_ai_reviewer(login),
                "created_at": comment.get("created_at"),
                "url": comment.get("html_url"),
                "path": comment.get("path"),
                "line": comment.get("line"),
                "thread_id": (
                    thread_status.get("thread_id") if thread_status else None
                ),
                "thread_resolved": (
                    thread_status.get("thread_resolved")
                    if thread_status is not None
                    else None
                ),
                "thread_outdated": (
                    thread_status.get("thread_outdated")
                    if thread_status is not None
                    else None
                ),
                "has_replies": (
                    thread_status.get("has_replies")
                    if thread_status is not None
                    else False
                ),
                "body": body,
                "excerpt": body_excerpt(body),
                "ai_prompts": extract_ai_prompts(body),
            }
        )
    return normalized


def build_reply_map(owner: str, repo: str, pr: int) -> dict[int, bool]:
    """Build a mapping of comment/review ID → has_replies.

    Fetches all issue comments and reviews from the PR, then uses a
    time-based heuristic: any subsequent comment/review by a different
    non-bot author is considered a reply.
    """
    reply_map: dict[int, bool] = {}

    try:
        raw_issue_comments = json.loads(
            run_gh(
                [
                    "api",
                    f"repos/{owner}/{repo}/issues/{pr}/comments",
                    "--paginate",
                    "--jq",
                    "[.[] | {id: .node_id, created_at: .created_at, author: .user.login}]",
                ]
            )
        )
    except RuntimeError:
        raw_issue_comments = []

    try:
        raw_reviews = json.loads(
            run_gh(
                [
                    "api",
                    f"repos/{owner}/{repo}/pulls/{pr}/reviews",
                    "--paginate",
                    "--jq",
                    "[.[] | {id: .node_id, submitted_at: .submitted_at, author: .user.login, state: .state}]",
                ]
            )
        )
    except RuntimeError:
        raw_reviews = []

    # Collect all "events" (comments + reviews) sorted by time.
    events: list[dict[str, Any]] = []
    for c in raw_issue_comments:
        if c.get("created_at"):
            events.append(
                {
                    "kind": "issue_comment",
                    "id": c["id"],
                    "time": c["created_at"],
                    "author": c.get("author", ""),
                }
            )
    for r in raw_reviews:
        if r.get("submitted_at"):
            events.append(
                {
                    "kind": "review",
                    "id": r["id"],
                    "time": r["submitted_at"],
                    "author": r.get("author", ""),
                    "state": r.get("state", ""),
                }
            )

    events.sort(key=lambda e: e["time"])

    # For each event, scan later events for potential replies.
    # A reply must: be later in time, have a different non-AI author,
    # and (for reviews) be a COMMENT (not APPROVE/CHANGES_REQUESTED).
    for i, event in enumerate(events):
        target_id = event["id"]
        for later in events[i + 1 :]:
            if later["author"] == event["author"]:
                continue
            if is_ai_reviewer(later["author"]):
                continue
            if later["kind"] == "review" and later.get("state") != "COMMENTED":
                continue
            reply_map[target_id] = True
            break

    return reply_map


def collect(
    pr: int, include_resolved: bool = False, repo: str | None = None
) -> dict[str, Any]:
    gh_pr_args = [
        "pr",
        "view",
        str(pr),
        "--json",
        "number,title,url,comments,reviews",
    ]
    if repo:
        gh_pr_args.extend(["--repo", repo])
    pr_view = json.loads(run_gh(gh_pr_args))
    owner, repo = parse_repo_from_pr_url(pr_view["url"])
    inline = json.loads(
        run_gh(["api", f"repos/{owner}/{repo}/pulls/{pr}/comments", "--paginate"])
    )
    review_thread_status = collect_review_thread_status(owner, repo, pr)
    reply_map = build_reply_map(owner, repo, pr)

    top_level = normalize_top_level(pr_view.get("comments", []), reply_map)
    reviews = normalize_reviews(pr_view.get("reviews", []), reply_map)
    inline_comments = normalize_inline(
        inline,
        review_thread_status=review_thread_status,
        include_resolved=include_resolved,
    )

    all_items = [*top_level, *reviews, *inline_comments]
    ai_count = sum(1 for item in all_items if item["is_ai"])
    human_count = len(all_items) - ai_count

    def safe_comment_id(inline_comment: dict[str, Any]) -> int | None:
        id_value = inline_comment.get("id")
        if id_value is None:
            return None
        try:
            return int(id_value)
        except (TypeError, ValueError):
            return None

    resolved_inline_total = sum(
        1
        for inline_comment in inline
        if (
            (comment_id := safe_comment_id(inline_comment)) is not None
            and review_thread_status.get(comment_id, {}).get("thread_resolved") is True
        )
    )
    outdated_inline_total = sum(
        1
        for inline_comment in inline
        if (
            (comment_id := safe_comment_id(inline_comment)) is not None
            and review_thread_status.get(comment_id, {}).get("thread_outdated") is True
        )
    )

    return {
        "pr": {
            "number": pr_view["number"],
            "title": pr_view["title"],
            "url": pr_view["url"],
        },
        "counts": {
            "top_level": len(top_level),
            "reviews": len(reviews),
            "inline": len(inline_comments),
            "inline_total": len(inline),
            "inline_resolved": resolved_inline_total,
            "inline_outdated": outdated_inline_total,
            "inline_filtered_out": len(inline) - len(inline_comments),
            "total_items": len(all_items),
            "ai_items": ai_count,
            "human_items": human_count,
        },
        "filters": {
            "include_resolved_inline": include_resolved,
        },
        "items": all_items,
    }


def print_text_report(payload: dict[str, Any]) -> None:
    pr = payload["pr"]
    counts = payload["counts"]
    print(f"PR #{pr['number']}: {pr['title']}")
    print(pr["url"])
    print(
        "Counts: "
        f"top-level={counts['top_level']}, "
        f"reviews={counts['reviews']}, "
        f"inline={counts['inline']}, "
        f"inline-total={counts['inline_total']}, "
        f"inline-outdated={counts['inline_outdated']}, "
        f"inline-filtered-out={counts['inline_filtered_out']}, "
        f"ai={counts['ai_items']}, "
        f"human={counts['human_items']}"
    )
    print("")

    for idx, item in enumerate(payload["items"], start=1):
        marker = "AI" if item["is_ai"] else "Human"
        replied = " ↩" if item.get("has_replies") else ""
        location = ""
        if item.get("path"):
            location = f" | {item['path']}:{item.get('line') or ''}"
        print(
            f"{idx}. [{item['kind']}]{replied} {marker} @{item['author']}{location}\n"
            f"   {item.get('excerpt', '')}\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="List and normalize PR comments")
    parser.add_argument("--pr", type=int, default=None, help="PR number")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of text",
    )
    parser.add_argument(
        "--include-resolved",
        action="store_true",
        help="Include resolved inline review threads (default: unresolved only)",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Repository in owner/repo format (required when not running from repo dir)",
    )
    args = parser.parse_args()

    try:
        ensure_gh()
        pr = resolve_pr_number(args.pr, repo=args.repo)
        payload = collect(pr, include_resolved=args.include_resolved, repo=args.repo)
    except Exception as exc:  # CLI utility: return readable failure
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print_text_report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
