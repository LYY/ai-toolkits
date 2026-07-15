from __future__ import annotations

import base64
import copy
import importlib.util
import json
import pathlib
import re
import types
import unittest
from collections.abc import Callable
from typing import ClassVar, cast, override

from tests import test_artifact_ops


_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_LIST_COMMENTS = (
    _REPO_ROOT
    / "skills"
    / "address-pr-comments-review"
    / "scripts"
    / "list_comments.py"
)
_DOSSIER_OUTPUT = (
    _REPO_ROOT
    / "skills"
    / "address-pr-comments-review"
    / "references"
    / "dossier-output.md"
)

_REPLY_TARGET_FIELDS = {
    "reply_target_id",
    "source_comment_id",
    "root_comment_id",
    "author",
    "comment_kind",
    "reply_mode",
    "endpoint",
    "read_back_endpoint",
    "source_path",
    "source_line",
    "reply_body_template",
    "reply_kind",
    "requires_commit_sha",
    "duplicate_of",
    "disposition",
    "disposition_reason",
}
_LEGACY_REPLY_TARGET_FIELDS = {"comment_id", "kind", "in_reply_to"}
_COMMENT_KINDS = {"inline", "review", "top_level"}
_REPLY_MODES = {"threaded_inline", "sibling_inline", "timeline"}
_FIXTURE_SHA = "0123456789abcdef0123456789abcdef01234567"
_FORBIDDEN_POST_FIELDS = {"commit_id", "path", "line", "side", "in_reply_to"}
_MakeSourceTemplate = Callable[[str, str, str], str]
_MAKE_SOURCE_TEMPLATE = cast(
    _MakeSourceTemplate,
    cast(object, getattr(test_artifact_ops, "_make_source_template")),
)


def _extract_json_fence(markdown: str, heading: str) -> list[dict[str, object]]:
    if heading not in markdown:
        raise AssertionError(f"missing documented section: {heading}")
    section_start = markdown.index(heading) + len(heading)
    section = markdown[section_start:]
    match = re.search(r"```json\s*(.*?)\s*```", section, re.DOTALL)
    if match is None:
        raise AssertionError(f"missing JSON fixture after {heading}")
    parsed = cast(object, json.loads(match.group(1)))
    targets: list[dict[str, object]]
    if isinstance(parsed, dict):
        targets = [cast(dict[str, object], parsed)]
    elif isinstance(parsed, list):
        targets = []
        for target in cast(list[object], parsed):
            if not isinstance(target, dict):
                raise AssertionError("reply target fixture must be an object array")
            targets.append(cast(dict[str, object], target))
    else:
        raise AssertionError("reply target fixture must be an object array")
    return targets


def _extract_embedded_reply_targets(source: str) -> list[dict[str, object]]:
    match = re.search(
        r"<!-- reply-targets-json:start -->\s*(.*?)\s*<!-- reply-targets-json:end -->",
        source,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("missing embedded reply target fixture")
    parsed = cast(object, json.loads(match.group(1)))
    if not isinstance(parsed, list):
        raise AssertionError("embedded reply targets must be an object array")
    targets: list[dict[str, object]] = []
    for target in cast(list[object], parsed):
        if not isinstance(target, dict):
            raise AssertionError("embedded reply targets must be an object array")
        targets.append(cast(dict[str, object], target))
    return targets


def _expected_route(target: dict[str, object]) -> tuple[str, object, str, str]:
    comment_kind = target.get("comment_kind")
    source_comment_id = target.get("source_comment_id")
    root_comment_id = target.get("root_comment_id")
    if comment_kind == "inline":
        if not isinstance(root_comment_id, int):
            raise ValueError("inline reply target missing numeric root_comment_id")
        mode = (
            "threaded_inline"
            if source_comment_id == root_comment_id
            else "sibling_inline"
        )
        return (
            mode,
            root_comment_id,
            f"repos/{{owner}}/{{repo}}/pulls/{{pr}}/comments/{root_comment_id}/replies",
            "repos/{owner}/{repo}/pulls/{pr}/comments",
        )
    if comment_kind in {"review", "top_level"}:
        if root_comment_id is not None:
            raise ValueError("timeline reply target must have null root_comment_id")
        return (
            "timeline",
            None,
            "repos/{owner}/{repo}/issues/{pr}/comments",
            "repos/{owner}/{repo}/issues/{pr}/comments",
        )
    raise ValueError(f"unknown comment_kind: {comment_kind!r}")


def _validate_reply_target(target: dict[str, object]) -> list[str]:
    errors: list[str] = []
    missing = _REPLY_TARGET_FIELDS - target.keys()
    if missing:
        errors.append(f"missing fields: {sorted(missing)}")
    legacy = _LEGACY_REPLY_TARGET_FIELDS & target.keys()
    if legacy:
        errors.append(f"legacy fields: {sorted(legacy)}")
    if target.get("comment_kind") not in _COMMENT_KINDS:
        errors.append(f"unknown comment_kind: {target.get('comment_kind')!r}")
    if target.get("reply_mode") not in _REPLY_MODES:
        errors.append(f"unknown reply_mode: {target.get('reply_mode')!r}")
    try:
        expected = _expected_route(target)
    except ValueError as error:
        errors.append(str(error))
    else:
        actual_mode = target.get("reply_mode")
        actual_root = target.get("root_comment_id")
        if (actual_mode, actual_root) != expected[:2]:
            actual_identity = (actual_mode, actual_root)
            errors.append(
                f"route identity mismatch: expected {expected[:2]!r}, got {actual_identity!r}"
            )
        for field, actual, expected_endpoint in (
            ("endpoint", target.get("endpoint"), expected[2]),
            (
                "read_back_endpoint",
                target.get("read_back_endpoint"),
                expected[3],
            ),
        ):
            endpoint_pattern = re.escape(expected_endpoint)
            endpoint_pattern = endpoint_pattern.replace(
                re.escape("{owner}"), r"[^/]+"
            ).replace(re.escape("{repo}"), r"[^/]+")
            endpoint_pattern = endpoint_pattern.replace(
                re.escape("{pr}"), r"(?:\{pr\}|\d+)"
            )
            if (
                not isinstance(actual, str)
                or re.fullmatch(endpoint_pattern, actual) is None
            ):
                errors.append(
                    f"{field} mismatch: expected {expected_endpoint!r}, got {actual!r}"
                )
    return errors


def _attempt_post(target: dict[str, object]) -> tuple[str, int]:
    errors = _validate_reply_target(target)
    if errors:
        return f"blocked:{'; '.join(errors)}", 0
    return "eligible", 1


def _as_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AssertionError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _as_object_list(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise AssertionError(f"{label} must be an object array")
    objects: list[dict[str, object]] = []
    for item in cast(list[object], value):
        objects.append(_as_object(item, label))
    return objects


def _validate_post_route(route: dict[str, object]) -> list[str]:
    errors: list[str] = []
    source_comment_id = route.get("source_comment_id")
    root_comment_id = route.get("root_comment_id")
    comment_kind = route.get("comment_kind")
    post = _as_object(route.get("post"), "post")
    payload = _as_object(post.get("payload"), "post payload")

    if set(payload) != {"body"}:
        errors.append(f"payload keys must equal ['body'], got {sorted(payload)}")
    forbidden = _FORBIDDEN_POST_FIELDS & payload.keys()
    if forbidden:
        errors.append(f"forbidden payload fields: {sorted(forbidden)}")

    if comment_kind == "inline":
        expected_endpoint = (
            f"repos/{{owner}}/{{repo}}/pulls/{{pr}}/comments/{root_comment_id}/replies"
        )
        expected_mode = (
            "threaded_inline"
            if source_comment_id == root_comment_id
            else "sibling_inline"
        )
    elif comment_kind in {"review", "top_level"}:
        expected_endpoint = "repos/{owner}/{repo}/issues/{pr}/comments"
        expected_mode = "timeline"
    else:
        return [f"unknown comment_kind: {comment_kind!r}"]

    if route.get("reply_mode") != expected_mode:
        errors.append(
            f"reply_mode must be {expected_mode!r}, got {route.get('reply_mode')!r}"
        )
    if post.get("method") != "POST":
        errors.append(f"post method must be 'POST', got {post.get('method')!r}")
    if post.get("endpoint") != expected_endpoint:
        errors.append(
            f"post endpoint must be {expected_endpoint!r}, got {post.get('endpoint')!r}"
        )
    return errors


def _replay_reconciliation(
    contract: dict[str, object], response_fixture: str, exact_match_count: int
) -> dict[str, object]:
    response_states = _as_object(contract.get("response_states"), "response_states")
    response = _as_object(response_states.get(response_fixture), response_fixture)
    outcomes = _as_object(contract.get("read_back_outcomes"), "read_back_outcomes")
    outcome_key = (
        "one_exact_match"
        if exact_match_count == 1
        else "zero_exact_matches"
        if exact_match_count == 0
        else "multiple_exact_matches"
    )
    outcome = _as_object(outcomes.get(outcome_key), outcome_key)
    return {
        "post_attempts": 1,
        "write_state": response.get("write_state"),
        "next": response.get("next"),
        "reconciled": exact_match_count == 1,
        "final_state": outcome.get("final_state"),
        "second_post_authorized": outcome.get("second_post_authorized"),
    }


def load_list_comments() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "address_pr_comments_review_list_comments",
        _LIST_COMMENTS,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load active collector: {_LIST_COMMENTS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_NormalizeInline = Callable[
    [list[dict[str, object]], dict[int, dict[str, object]], bool],
    list[dict[str, object]],
]
_NORMALIZE_INLINE = cast(
    _NormalizeInline,
    cast(object, getattr(load_list_comments(), "normalize_inline")),
)


class TestNormalizeInlineRootIdentity(unittest.TestCase):
    def test_root_and_child_preserve_source_and_root_identity(self) -> None:
        comments: list[dict[str, object]] = [
            {"id": 101, "in_reply_to_id": None},
            {"id": 202, "in_reply_to_id": 101},
        ]

        normalized = _NORMALIZE_INLINE(comments, {}, False)

        self.assertEqual([item["kind"] for item in normalized], ["inline", "inline"])
        self.assertEqual([item["id"] for item in normalized], [101, 202])
        self.assertEqual([item["root_comment_id"] for item in normalized], [101, 101])

    def test_missing_source_id_does_not_invent_root_identity(self) -> None:
        normalized = _NORMALIZE_INLINE([{}], {}, False)

        self.assertEqual(normalized[0]["kind"], "inline")
        self.assertIsNone(normalized[0]["id"])
        self.assertIsNone(normalized[0]["root_comment_id"])

    def test_invalid_source_id_remains_permissively_normalized(self) -> None:
        normalized = _NORMALIZE_INLINE(
            [{"id": "not-a-github-id"}],
            {},
            False,
        )

        self.assertEqual(normalized[0]["kind"], "inline")
        self.assertEqual(normalized[0]["id"], "not-a-github-id")
        self.assertEqual(normalized[0]["root_comment_id"], "not-a-github-id")


class TestReplyTargetSchema(unittest.TestCase):
    dossier: ClassVar[str]
    targets: ClassVar[list[dict[str, object]]]

    @override
    @classmethod
    def setUpClass(cls) -> None:
        cls.dossier = _DOSSIER_OUTPUT.read_text(encoding="utf-8")
        cls.targets = _extract_json_fence(cls.dossier, "## Reply Target Schema")

    def test_documented_examples_preserve_schema_and_exact_routes(self) -> None:
        self.assertEqual(
            [target["reply_target_id"] for target in self.targets],
            [
                "reply-1",
                "reply-2",
                "reply-3",
                "reply-4",
            ],
        )
        for target in self.targets:
            self.assertEqual(_validate_reply_target(target), [])

        self.assertEqual(
            [
                (
                    target["source_comment_id"],
                    target["root_comment_id"],
                    target["comment_kind"],
                    target["reply_mode"],
                    target["endpoint"],
                    target["read_back_endpoint"],
                )
                for target in self.targets
            ],
            [
                (
                    101,
                    101,
                    "inline",
                    "threaded_inline",
                    "repos/{owner}/{repo}/pulls/{pr}/comments/101/replies",
                    "repos/{owner}/{repo}/pulls/{pr}/comments",
                ),
                (
                    202,
                    101,
                    "inline",
                    "sibling_inline",
                    "repos/{owner}/{repo}/pulls/{pr}/comments/101/replies",
                    "repos/{owner}/{repo}/pulls/{pr}/comments",
                ),
                (
                    303,
                    None,
                    "review",
                    "timeline",
                    "repos/{owner}/{repo}/issues/{pr}/comments",
                    "repos/{owner}/{repo}/issues/{pr}/comments",
                ),
                (
                    404,
                    None,
                    "top_level",
                    "timeline",
                    "repos/{owner}/{repo}/issues/{pr}/comments",
                    "repos/{owner}/{repo}/issues/{pr}/comments",
                ),
            ],
        )
        self.assertEqual(
            {target["comment_kind"] for target in self.targets}, _COMMENT_KINDS
        )
        self.assertEqual(
            {target["reply_mode"] for target in self.targets}, _REPLY_MODES
        )

    def test_embedded_artifact_fixture_uses_canonical_schema(self) -> None:
        encoded = _MAKE_SOURCE_TEMPLATE("artifact-id", "operation-id", "a" * 40)
        source = base64.b64decode(encoded).decode("utf-8")
        targets = _extract_embedded_reply_targets(source)

        self.assertEqual(len(targets), 1)
        self.assertEqual(_validate_reply_target(targets[0]), [])
        self.assertEqual(
            (
                targets[0]["source_comment_id"],
                targets[0]["root_comment_id"],
                targets[0]["reply_mode"],
                targets[0]["endpoint"],
                targets[0]["read_back_endpoint"],
            ),
            (
                42,
                42,
                "threaded_inline",
                "repos/owner/repo/pulls/1/comments/42/replies",
                "repos/owner/repo/pulls/1/comments",
            ),
        )

    def test_malformed_routes_block_before_post_without_generic_fallback(self) -> None:
        child = self.targets[1]
        mutations: list[dict[str, object]] = []

        child_root = copy.deepcopy(child)
        child_root["root_comment_id"] = 202
        mutations.append(child_root)

        unknown_kind = copy.deepcopy(child)
        unknown_kind["comment_kind"] = "discussion"
        unknown_kind["endpoint"] = "repos/{owner}/{repo}/pulls/{pr}/comments"
        mutations.append(unknown_kind)

        unknown_mode = copy.deepcopy(child)
        unknown_mode["reply_mode"] = "nested_inline"
        mutations.append(unknown_mode)

        missing_root = copy.deepcopy(child)
        missing_root["root_comment_id"] = None
        mutations.append(missing_root)

        for target in mutations:
            with self.subTest(target=target):
                disposition, post_count = _attempt_post(target)
                self.assertTrue(disposition.startswith("blocked:"), disposition)
                self.assertEqual(post_count, 0)


class TestReplyRouteContract(unittest.TestCase):
    dossier: ClassVar[str]
    contract: dict[str, object] = {}
    routes: list[dict[str, object]] = []

    @override
    @classmethod
    def setUpClass(cls) -> None:
        cls.dossier = _DOSSIER_OUTPUT.read_text(encoding="utf-8")

    @override
    def setUp(self) -> None:
        heading = "## Reply Posting and Reconciliation Contract"
        self.assertIn(heading, self.dossier)
        fixtures = _extract_json_fence(self.dossier, heading)
        self.contract = fixtures[0]
        self.routes = _as_object_list(self.contract.get("routes"), "routes")

    def test_four_routes_use_exact_endpoints_and_body_only_payloads(self) -> None:
        self.assertEqual(
            [
                (
                    route["source_comment_id"],
                    route["root_comment_id"],
                    route["reply_mode"],
                    _as_object(route["post"], "post")["endpoint"],
                    set(
                        _as_object(
                            _as_object(route["post"], "post")["payload"], "payload"
                        )
                    ),
                )
                for route in self.routes
            ],
            [
                (
                    101,
                    101,
                    "threaded_inline",
                    "repos/{owner}/{repo}/pulls/{pr}/comments/101/replies",
                    {"body"},
                ),
                (
                    202,
                    101,
                    "sibling_inline",
                    "repos/{owner}/{repo}/pulls/{pr}/comments/101/replies",
                    {"body"},
                ),
                (
                    303,
                    None,
                    "timeline",
                    "repos/{owner}/{repo}/issues/{pr}/comments",
                    {"body"},
                ),
                (
                    404,
                    None,
                    "timeline",
                    "repos/{owner}/{repo}/issues/{pr}/comments",
                    {"body"},
                ),
            ],
        )
        for route in self.routes:
            self.assertEqual(_validate_post_route(route), [])

    def test_forbidden_payload_fields_and_child_endpoint_mutations_fail(self) -> None:
        forbidden = self.contract.get("forbidden_post_fields")
        self.assertIsInstance(forbidden, list)
        self.assertEqual(set(cast(list[object], forbidden)), _FORBIDDEN_POST_FIELDS)

        root = self.routes[0]
        for field in sorted(_FORBIDDEN_POST_FIELDS):
            mutated = copy.deepcopy(root)
            post = _as_object(mutated["post"], "post")
            _as_object(post["payload"], "payload")[field] = "forbidden"
            with self.subTest(field=field):
                self.assertTrue(_validate_post_route(mutated))

        child = copy.deepcopy(self.routes[1])
        _as_object(child["post"], "post")["endpoint"] = (
            "repos/{owner}/{repo}/pulls/{pr}/comments/202/replies"
        )
        self.assertTrue(_validate_post_route(child))

    def test_fixed_and_partially_addressed_bodies_keep_full_sha(self) -> None:
        rendered = _as_object(
            self.contract.get("rendered_reply_bodies"), "rendered_reply_bodies"
        )
        self.assertEqual(len(_FIXTURE_SHA), 40)
        for reply_kind in ("fixed", "partially_addressed"):
            body = rendered.get(reply_kind)
            self.assertIsInstance(body, str)
            self.assertIn(_FIXTURE_SHA, cast(str, body))

        for route in self.routes[:2]:
            payload = _as_object(
                _as_object(route["post"], "post")["payload"], "payload"
            )
            self.assertEqual(set(payload), {"body"})
            self.assertIn(_FIXTURE_SHA, cast(str, payload["body"]))

    def test_read_back_endpoints_and_predicates_are_route_specific(self) -> None:
        expected = [
            (
                "repos/{owner}/{repo}/pulls/{pr}/comments",
                {
                    "actor": "authenticated_actor",
                    "body": "full_rendered_body",
                    "pull_request_url": "target_pr_api_url",
                    "in_reply_to_id": 101,
                },
            ),
            (
                "repos/{owner}/{repo}/pulls/{pr}/comments",
                {
                    "actor": "authenticated_actor",
                    "body": "full_rendered_body",
                    "pull_request_url": "target_pr_api_url",
                    "in_reply_to_id": 101,
                },
            ),
            (
                "repos/{owner}/{repo}/issues/{pr}/comments",
                {
                    "actor": "authenticated_actor",
                    "body": "full_rendered_body",
                    "issue_url": "target_pr_issue_api_url",
                },
            ),
            (
                "repos/{owner}/{repo}/issues/{pr}/comments",
                {
                    "actor": "authenticated_actor",
                    "body": "full_rendered_body",
                    "issue_url": "target_pr_issue_api_url",
                },
            ),
        ]
        actual: list[tuple[object, dict[str, object]]] = []
        for route in self.routes:
            read_back = _as_object(route["read_back"], "read_back")
            self.assertEqual(read_back.get("method"), "GET")
            actual.append(
                (
                    read_back.get("endpoint"),
                    _as_object(read_back.get("predicate"), "predicate"),
                )
            )
        self.assertEqual(actual, expected)

    def test_uncertain_writes_reconcile_once_and_never_repost(self) -> None:
        cases = [
            ("201_parseable_id", 1, "posted", "verified"),
            ("timeout", 1, "uncertain", "verified"),
            ("malformed_response", 1, "uncertain", "verified"),
            ("201_parseable_id", 0, "posted", "blocked_absent"),
            ("timeout", 0, "uncertain", "blocked_absent"),
            ("malformed_response", 2, "uncertain", "blocked_ambiguous"),
        ]
        for response_fixture, match_count, write_state, final_state in cases:
            with self.subTest(response=response_fixture, matches=match_count):
                result = _replay_reconciliation(
                    self.contract, response_fixture, match_count
                )
                self.assertEqual(result["post_attempts"], 1)
                self.assertEqual(result["write_state"], write_state)
                self.assertEqual(result["next"], "read_back")
                self.assertEqual(result["reconciled"], match_count == 1)
                self.assertEqual(result["final_state"], final_state)
                self.assertIs(result["second_post_authorized"], False)

    def test_legacy_post_commands_and_blind_retry_are_not_canonical(self) -> None:
        section = self.dossier.split("## Reply Endpoints", 1)[1].split(
            "## Dossier Structure", 1
        )[0]
        for field in sorted(_FORBIDDEN_POST_FIELDS):
            self.assertNotRegex(section, rf"-[fF]\s+{re.escape(field)}=")
        self.assertNotIn("Only re-POST if read-back proves", self.dossier)
        self.assertNotIn("different `in_reply_to`", self.dossier)
        self.assertNotIn("own `in_reply_to`", self.dossier)


if __name__ == "__main__":
    _ = unittest.main()
