from __future__ import annotations

import pathlib
import re
import unittest
from typing import TypeVar


_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_DOSSIER_OUTPUT = pathlib.Path(
    "skills/address-pr-comments-review/references/dossier-output.md"
)
_INTERACTION = pathlib.Path(
    "skills/address-pr-comments-review/references/interaction.md"
)
_EXECUTION = pathlib.Path("skills/address-pr-comments-review/references/execution.md")

_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")
_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_TASK_RE = re.compile(r"^### Task [1-9][0-9]*\b.*$", re.MULTILINE)
_REQUIRED_TASK_FIELDS = (
    "Target file",
    "Evidence",
    "Verification",
    "Commit message",
    "Reply targets",
    "Read-back",
)
_AnyStr = TypeVar("_AnyStr", str, bytes)


def extract_markdown_section(markdown: str, heading: str) -> str:
    headings: list[tuple[int, str, int, int]] = []
    active_fence: tuple[str, int] | None = None
    offset = 0
    for line in markdown.splitlines(keepends=True):
        fence_match = _FENCE_RE.match(line)
        if active_fence is not None:
            if (
                fence_match is not None
                and fence_match.group(1)[0] == active_fence[0]
                and len(fence_match.group(1)) >= active_fence[1]
            ):
                active_fence = None
        elif fence_match is not None:
            marker = fence_match.group(1)
            active_fence = (marker[0], len(marker))
        else:
            heading_match = _HEADING_RE.match(line.rstrip("\r\n"))
            if heading_match is not None:
                headings.append(
                    (
                        len(heading_match.group(1)),
                        heading_match.group(2).strip(),
                        offset,
                        offset + heading_match.end(),
                    )
                )
        offset += len(line)

    matches = [candidate for candidate in headings if candidate[1] == heading]
    if len(matches) != 1:
        raise AssertionError(
            f"expected one Markdown heading {heading!r}, found {len(matches)}"
        )

    level, _, start, content_start = matches[0]
    end = len(markdown)
    for candidate in headings:
        candidate_level, _, candidate_start, _ = candidate
        if candidate_start > start and candidate_level <= level:
            end = candidate_start
            break
    return markdown[content_start:end].strip()


def read_runtime_section(relative_path: pathlib.Path, heading: str) -> str:
    path = (_REPO_ROOT / relative_path).resolve()
    if path.parent != (_REPO_ROOT / relative_path.parent).resolve():
        raise AssertionError(f"runtime source escaped repository root: {path}")
    return extract_markdown_section(path.read_text(encoding="utf-8"), heading)


def markdown_prompt_count(section: str) -> int:
    return len(re.findall(r"^```markdown[ \t]*$", section, re.MULTILINE))


def extract_markdown_fixture(section: str) -> str:
    fixtures: list[str] = re.findall(
        r"^```markdown[ \t]*\r?\n(.*?)^```[ \t]*$",
        section,
        re.MULTILINE | re.DOTALL,
    )
    if len(fixtures) != 1:
        raise AssertionError(f"expected one Markdown fixture, found {len(fixtures)}")
    return fixtures[0]


def validate_direct_fix_brief_fixture(brief: str) -> list[str]:
    task_matches = list(_TASK_RE.finditer(brief))
    errors: list[str] = []
    if not 1 <= len(task_matches) <= 5:
        errors.append(f"Section A task count must be 1-5, got {len(task_matches)}")

    for index, task_match in enumerate(task_matches):
        end = (
            task_matches[index + 1].start()
            if index + 1 < len(task_matches)
            else len(brief)
        )
        task = brief[task_match.start() : end]
        for field in _REQUIRED_TASK_FIELDS:
            if not re.search(rf"^- \*\*{re.escape(field)}\*\*:", task, re.MULTILINE):
                errors.append(f"Task {index + 1} missing {field}")
    return errors


def _complete_task(number: int) -> str:
    return f"""### Task {number}: focused change
- **Target file**: path/to/file-{number}.md
- **Evidence**: current source
- **Verification**: python3 -m unittest
- **Commit message**: fix task {number}
- **Reply targets**: comment-{number}
- **Read-back**: GET comment-{number}
"""


def _reply_only_task(number: int) -> str:
    return f"""### Reply-Only Task {number}: reply without code change
- **Source**: @reviewer-{number} | inline | path/to/file.md:{number}
- **Reply targets**: comment-{number}, reviewer-{number}, inline, endpoint
- **Reply kind**: `invalid`
- **Reply body**: explanation-{number}
- **Pre-Reply Gate**: must pass for this target before posting
- **Read-back**: GET comment-{number}
"""


class RuntimeContractTestCase(unittest.TestCase):
    def assertContractRegex(
        self,
        text: _AnyStr,
        expected_regex: _AnyStr | re.Pattern[_AnyStr],
        msg: object | None = None,
    ) -> None:
        pattern = (
            re.compile(expected_regex)
            if isinstance(expected_regex, (str, bytes))
            else expected_regex
        )
        if pattern.search(text) is None:
            self.fail(msg or f"required contract pattern missing: {pattern.pattern}")

    def assertContractNotRegex(
        self,
        text: _AnyStr,
        unexpected_regex: _AnyStr | re.Pattern[_AnyStr],
        msg: object | None = None,
    ) -> None:
        pattern = (
            re.compile(unexpected_regex)
            if isinstance(unexpected_regex, (str, bytes))
            else unexpected_regex
        )
        if pattern.search(text) is not None:
            self.fail(msg or f"forbidden contract pattern present: {pattern.pattern}")

    def assertTextIn(self, member: str, container: str) -> None:
        if member not in container:
            self.fail(f"required contract text missing: {member}")

    def assertTextNotIn(self, member: str, container: str) -> None:
        if member in container:
            self.fail(f"forbidden contract text present: {member}")


class TestMarkdownSectionHelpers(unittest.TestCase):
    def test_section_extraction_stops_at_peer_heading(self) -> None:
        markdown = (
            "# Root\n## Owner\nkept\n### Child\nalso kept\n## Sibling\nexcluded\n"
        )

        section = extract_markdown_section(markdown, "Owner")

        self.assertIn("also kept", section)
        self.assertNotIn("excluded", section)

    def test_section_extraction_ignores_headings_inside_fences(self) -> None:
        markdown = "## Owner\n```markdown\n# Fixture\n## Nested fixture\n```\nkept\n## Sibling\n"

        section = extract_markdown_section(markdown, "Owner")

        self.assertIn("# Fixture", section)
        self.assertIn("kept", section)

    def test_runtime_sections_load_from_current_repository_root(self) -> None:
        sections = (
            read_runtime_section(_DOSSIER_OUTPUT, "Direct Fix Brief"),
            read_runtime_section(
                _INTERACTION, "Post-Confirmation Routing (Decision Gate)"
            ),
            read_runtime_section(_EXECUTION, "Dossier Handoff"),
            read_runtime_section(_EXECUTION, "Direct Fix Brief Handoff"),
        )

        self.assertTrue(all(sections))

    def test_old_single_task_and_dual_handoff_fixtures_are_rejected(self) -> None:
        old_brief = "# Direct Fix Brief\n## Comment\n- Comment ID: 1\n"
        old_handoff = """```markdown
execute directly
```
```markdown
generate a plan
```
"""

        self.assertIn(
            "Section A task count must be 1-5, got 0",
            validate_direct_fix_brief_fixture(old_brief),
        )
        self.assertNotEqual(markdown_prompt_count(old_handoff), 1)

    def test_six_task_fixture_is_rejected_by_hard_bound(self) -> None:
        fixture = "\n".join(_complete_task(number) for number in range(1, 7))

        errors = validate_direct_fix_brief_fixture(fixture)

        self.assertIn("Section A task count must be 1-5, got 6", errors)

    def test_incomplete_task_fixture_is_rejected(self) -> None:
        fixture = _complete_task(1).replace("- **Read-back**: GET comment-1\n", "")

        errors = validate_direct_fix_brief_fixture(fixture)

        self.assertIn("Task 1 missing Read-back", errors)


class TestDirectFixEligibilityContract(RuntimeContractTestCase):
    def direct_fix(self) -> str:
        return read_runtime_section(_DOSSIER_OUTPUT, "Direct Fix Brief")

    def test_direct_fix_allows_one_through_five_section_a_tasks(self) -> None:
        self.assertContractRegex(
            self.direct_fix(), r"(?i)\b(?:1\s*(?:-|through|to)\s*5|one through five)\b"
        )

    def test_direct_fix_rejects_task_counts_above_five(self) -> None:
        section = self.direct_fix()
        self.assertContractRegex(
            section, r"(?i)(?:more than five|above five|six or more|>\s*5)"
        )
        self.assertContractRegex(section, r"(?i)review dossier")

    def test_direct_fix_removes_old_single_task_override(self) -> None:
        self.assertTextNotIn("exactly one task", self.direct_fix().lower())

    def test_each_task_touches_one_clearly_named_file(self) -> None:
        self.assertContractRegex(
            self.direct_fix(), r"(?i)each task touches one clearly named file"
        )

    def test_each_task_change_is_mechanically_derivable(self) -> None:
        self.assertContractRegex(
            self.direct_fix(),
            r"(?i)each task is a local, mechanically derivable",
        )

    def test_each_task_change_is_low_risk(self) -> None:
        self.assertContractRegex(
            self.direct_fix(),
            r"(?i)each task is a local,[^\n]*low-risk change",
        )

    def test_each_task_requires_exact_target_file(self) -> None:
        self.assertContractRegex(
            self.direct_fix(),
            r"(?i)each task has an exact target file, exact change",
        )

    def test_each_task_is_independent(self) -> None:
        self.assertContractRegex(self.direct_fix(), r"(?i)independent")

    def test_shared_modification_is_forbidden(self) -> None:
        self.assertContractRegex(self.direct_fix(), r"(?i)shared modification")

    def test_task_dependencies_are_forbidden(self) -> None:
        self.assertContractRegex(
            self.direct_fix(),
            r"(?i)\bno\b[^\n]*\bdependenc",
        )

    def test_each_task_requires_complete_execution_and_reply_data(self) -> None:
        section = self.direct_fix().lower()
        for field in (
            "evidence",
            "verification",
            "commit message",
            "reply",
            "read-back",
        ):
            with self.subTest(field=field):
                self.assertTextIn(field, section)

    def test_unresolved_duplicate_ambiguity_is_forbidden(self) -> None:
        self.assertContractRegex(
            self.direct_fix(), r"(?i)unresolved duplicate ambiguity"
        )

    def test_conflict_is_forbidden(self) -> None:
        self.assertContractRegex(self.direct_fix(), r"(?i)\bconflict\b")

    def test_cross_file_escalation_is_forbidden(self) -> None:
        self.assertContractRegex(self.direct_fix(), r"(?i)cross-file escalation")

    def test_cross_module_state_is_forbidden(self) -> None:
        self.assertContractRegex(self.direct_fix(), r"(?i)cross-module state")

    def test_api_change_is_forbidden(self) -> None:
        self.assertContractRegex(self.direct_fix(), r"(?i)\bapi(?: changes?)?\b")

    def test_authorization_change_is_forbidden(self) -> None:
        self.assertContractRegex(self.direct_fix(), r"(?i)authorization(?: changes?)?")

    def test_data_change_is_forbidden(self) -> None:
        self.assertContractRegex(self.direct_fix(), r"(?i)data changes?")

    def test_unclear_verification_is_forbidden(self) -> None:
        self.assertContractRegex(self.direct_fix(), r"(?i)unclear verification")

    def test_clear_local_runtime_behavior_fix_remains_eligible(self) -> None:
        section = self.direct_fix()
        self.assertContractRegex(
            section, r"(?i)local runtime behavior fixes? (?:remain|are) eligible"
        )
        self.assertContractRegex(
            section, r"(?i)file type alone does not (?:decide|determine) eligibility"
        )

    def test_summary_reports_section_a_task_count_as_n_over_five(self) -> None:
        self.assertTextIn("Section A tasks: N/5", self.direct_fix())

    def test_summary_reports_all_eligibility_checks_passed(self) -> None:
        self.assertContractRegex(
            self.direct_fix(), r"All eligibility checks passed:\s*yes\|no"
        )

    def test_section_b_is_outside_n_over_five_with_unlimited_gated_replies(
        self,
    ) -> None:
        direct_fix = self.direct_fix()
        template = extract_markdown_fixture(direct_fix)
        section_b = extract_markdown_section(template, "Section B: Reply Only")
        fixture = "\n".join(
            [_complete_task(number) for number in range(1, 6)]
            + [_reply_only_task(number) for number in range(1, 8)]
        )

        self.assertContractRegex(
            direct_fix,
            r"(?i)section B reply-only entries remain a separate inventory",
        )
        self.assertContractRegex(
            direct_fix,
            r"(?i)outside section A and outside `N/5`.*never consume the five-task limit",
        )
        self.assertContractRegex(section_b, r"(?i)may have unlimited reply targets")
        self.assertTextIn("Pre-Reply Gate", section_b)
        self.assertTextIn("Read-back", section_b)
        for code_change_field in (
            "Target file",
            "Exact change",
            "Verification",
            "Commit message",
            "Commit SHA",
        ):
            with self.subTest(code_change_field=code_change_field):
                self.assertContractNotRegex(
                    section_b,
                    re.compile(
                        rf"^- \*\*{re.escape(code_change_field)}\*\*:",
                        re.MULTILINE,
                    ),
                )
        self.assertEqual(validate_direct_fix_brief_fixture(fixture), [])

    def test_fallback_names_every_failed_eligibility_condition(self) -> None:
        section = self.direct_fix()
        self.assertContractRegex(
            section, r"(?i)(?:every|all) fail(?:ed|ing) (?:eligibility )?condition"
        )
        self.assertContractRegex(section, r"(?i)review dossier")


class TestDirectFixExecutionContract(RuntimeContractTestCase):
    def direct_fix(self) -> str:
        return read_runtime_section(_DOSSIER_OUTPUT, "Direct Fix Brief")

    def test_tasks_execute_serially_in_full_sequence(self) -> None:
        normalized = self.direct_fix().lower().replace("→", "->")
        self.assertTextIn("serial", normalized)
        self.assertContractRegex(
            normalized,
            r"edit\s*->\s*verify\s*->\s*commit\s*->\s*push\s*->\s*remote-reachability\s*->\s*reply\s*->\s*read-back",
        )

    def test_each_task_requires_its_own_distinct_commit_sha(self) -> None:
        self.assertContractRegex(
            self.direct_fix(), r"(?i)(?:own|distinct) (?:task-specific )?commit sha"
        )

    def test_any_execution_failure_stops_the_batch(self) -> None:
        self.assertContractRegex(
            self.direct_fix(),
            r"(?i)(?:any|first) .*failure.*stops? (?:the whole )?batch",
        )

    def test_batch_failure_preserves_completed_task_evidence(self) -> None:
        self.assertContractRegex(
            self.direct_fix(),
            r"(?i)(?:completed task )?evidence (?:remains|is preserved)",
        )

    def test_batch_failure_leaves_later_tasks_unresolved(self) -> None:
        self.assertContractRegex(
            self.direct_fix(),
            r"(?i)(?:later|remaining) tasks? (?:remain|are left) unresolved",
        )


class TestRouteSelectionContract(RuntimeContractTestCase):
    def routing(self) -> str:
        return read_runtime_section(
            _INTERACTION, "Post-Confirmation Routing (Decision Gate)"
        )

    def test_direct_fix_requires_explicit_selection_after_final_table(self) -> None:
        self.assertContractRegex(
            self.routing(),
            r"(?i)explicitly (?:select|choose) direct fix after (?:seeing )?(?:the )?final (?:classification )?table",
        )

    def test_generic_proceed_does_not_select_direct_fix(self) -> None:
        self.assertContractRegex(
            self.routing(),
            r"(?i)(?:generic consent such as )?`proceed` does not select (?:this route|direct fix)",
        )

    def test_explicit_direct_fix_selection_needs_no_second_plan_approval(self) -> None:
        self.assertContractRegex(self.routing(), r"(?i)no second plan[- ]approval")


class TestExclusiveHandoffContract(RuntimeContractTestCase):
    def test_dossier_has_exactly_one_plan_first_prompt(self) -> None:
        section = read_runtime_section(_EXECUTION, "Dossier Handoff")

        self.assertEqual(markdown_prompt_count(section), 1)
        self.assertContractRegex(
            section, r"(?i)(?:plan first|generate an execution plan)"
        )
        self.assertContractRegex(
            section, r"(?i)(?:wait|stop) for explicit (?:user )?approval before editing"
        )

    def test_direct_fix_has_exactly_one_direct_execution_prompt(self) -> None:
        section = read_runtime_section(_EXECUTION, "Direct Fix Brief Handoff")

        self.assertEqual(markdown_prompt_count(section), 1)
        self.assertContractRegex(section, r"(?i)direct execution prompt")
        self.assertContractRegex(section, r"(?i)(?:bounded|1\s*(?:-|through|to)\s*5)")
        self.assertContractRegex(section, r"(?i)serial")
        self.assertContractNotRegex(
            section, r"(?i)generate an execution plan|plan approval"
        )


if __name__ == "__main__":
    _ = unittest.main()
