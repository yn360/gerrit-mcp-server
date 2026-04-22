import json
import pytest
from unittest.mock import patch, AsyncMock

from gerrit_mcp_server import main


@pytest.fixture
def mock_run_curl():
    with patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock) as m:
        yield m


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_posts_multiple_comments_in_one_call(mock_run_curl):
    """All comments are batched into a single POST."""
    mock_run_curl.side_effect = [
        "{}",  # GET existing comments
        '{"labels": {}, "comments": {}}',  # POST review
    ]

    result = await main.post_bulk_comments(
        "123",
        [
            {"file_path": "src/a.py", "line_number": 1, "message": "comment A"},
            {"file_path": "src/a.py", "line_number": 5, "message": "comment B"},
            {"file_path": "src/b.py", "line_number": 3, "message": "comment C"},
        ],
        gerrit_base_url="https://gerrit.example.com",
    )

    assert mock_run_curl.call_count == 2  # one GET, one POST
    assert "3 comment(s)" in result[0]["text"]

    post_args = mock_run_curl.call_args_list[1][0][0]
    data_idx = post_args.index("--data")
    body = json.loads(post_args[data_idx + 1])

    assert len(body["comments"]["src/a.py"]) == 2
    assert len(body["comments"]["src/b.py"]) == 1


@pytest.mark.asyncio
async def test_bulk_defaults_unresolved_to_true(mock_run_curl):
    mock_run_curl.side_effect = ["{}", '{"labels": {}, "comments": {}}']

    await main.post_bulk_comments(
        "42",
        [{"file_path": "foo.py", "line_number": 10, "message": "msg"}],
        gerrit_base_url="https://gerrit.example.com",
    )

    post_args = mock_run_curl.call_args_list[1][0][0]
    body = json.loads(post_args[post_args.index("--data") + 1])
    assert body["comments"]["foo.py"][0]["unresolved"] is True


@pytest.mark.asyncio
async def test_bulk_respects_unresolved_false(mock_run_curl):
    mock_run_curl.side_effect = ["{}", '{"labels": {}, "comments": {}}']

    await main.post_bulk_comments(
        "42",
        [{"file_path": "foo.py", "line_number": 10, "message": "msg", "unresolved": False}],
        gerrit_base_url="https://gerrit.example.com",
    )

    post_args = mock_run_curl.call_args_list[1][0][0]
    body = json.loads(post_args[post_args.index("--data") + 1])
    assert body["comments"]["foo.py"][0]["unresolved"] is False


@pytest.mark.asyncio
async def test_bulk_includes_labels(mock_run_curl):
    mock_run_curl.side_effect = ["{}", '{"labels": {}, "comments": {}}']

    await main.post_bulk_comments(
        "99",
        [{"file_path": "foo.py", "line_number": 1, "message": "ok"}],
        labels={"Code-Review": -1},
        gerrit_base_url="https://gerrit.example.com",
    )

    post_args = mock_run_curl.call_args_list[1][0][0]
    body = json.loads(post_args[post_args.index("--data") + 1])
    assert body["labels"] == {"Code-Review": -1}


# ---------------------------------------------------------------------------
# Thread detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_replies_to_existing_unresolved_thread(mock_run_curl):
    """Comments at a line with an existing unresolved thread get in_reply_to."""
    existing = {
        "src/a.py": [
            {
                "id": "thread001",
                "line": 7,
                "message": "Original",
                "unresolved": True,
                "updated": "2025-01-01 10:00:00.000000000",
                "author": {"name": "reviewer"},
            }
        ]
    }
    mock_run_curl.side_effect = [
        json.dumps(existing),
        '{"labels": {}, "comments": {}}',
    ]

    await main.post_bulk_comments(
        "55",
        [
            {"file_path": "src/a.py", "line_number": 7, "message": "Addressed."},
            {"file_path": "src/a.py", "line_number": 9, "message": "New issue."},
        ],
        gerrit_base_url="https://gerrit.example.com",
    )

    post_args = mock_run_curl.call_args_list[1][0][0]
    body = json.loads(post_args[post_args.index("--data") + 1])
    comments = body["comments"]["src/a.py"]

    reply = next(c for c in comments if c["line"] == 7)
    new_comment = next(c for c in comments if c["line"] == 9)

    assert reply["in_reply_to"] == "thread001"
    assert "in_reply_to" not in new_comment


@pytest.mark.asyncio
async def test_bulk_falls_back_to_standalone_if_fetch_fails(mock_run_curl):
    mock_run_curl.side_effect = [
        Exception("network error"),
        '{"labels": {}, "comments": {}}',
    ]

    await main.post_bulk_comments(
        "77",
        [{"file_path": "x.py", "line_number": 1, "message": "hi"}],
        gerrit_base_url="https://gerrit.example.com",
    )

    post_args = mock_run_curl.call_args_list[1][0][0]
    body = json.loads(post_args[post_args.index("--data") + 1])
    assert "in_reply_to" not in body["comments"]["x.py"][0]


# ---------------------------------------------------------------------------
# Patchset-level comments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_patchset_level_comment_omits_line_field(mock_run_curl):
    """A patchset-level comment must not include a 'line' field in the payload."""
    mock_run_curl.side_effect = ["{}", '{"labels": {}, "comments": {}}']

    await main.post_bulk_comments(
        "10",
        [{"file_path": "/PATCHSET_LEVEL", "message": "Overall feedback."}],
        gerrit_base_url="https://gerrit.example.com",
    )

    post_args = mock_run_curl.call_args_list[1][0][0]
    body = json.loads(post_args[post_args.index("--data") + 1])
    comment = body["comments"]["/PATCHSET_LEVEL"][0]
    assert "line" not in comment
    assert comment["message"] == "Overall feedback."


@pytest.mark.asyncio
async def test_bulk_patchset_level_replies_to_existing_thread(mock_run_curl):
    """Patchset-level comments reply into an existing patchset-level thread."""
    existing = {
        "/PATCHSET_LEVEL": [
            {
                "id": "ps_thread_01",
                "message": "Please add tests.",
                "unresolved": True,
                "updated": "2025-02-01 09:00:00.000000000",
                "author": {"name": "reviewer"},
            }
        ]
    }
    mock_run_curl.side_effect = [
        json.dumps(existing),
        '{"labels": {}, "comments": {}}',
    ]

    await main.post_bulk_comments(
        "20",
        [{"file_path": "/PATCHSET_LEVEL", "message": "Tests added."}],
        gerrit_base_url="https://gerrit.example.com",
    )

    post_args = mock_run_curl.call_args_list[1][0][0]
    body = json.loads(post_args[post_args.index("--data") + 1])
    comment = body["comments"]["/PATCHSET_LEVEL"][0]
    assert "line" not in comment
    assert comment["in_reply_to"] == "ps_thread_01"


@pytest.mark.asyncio
async def test_bulk_mixed_patchset_and_line_comments(mock_run_curl):
    """Patchset-level and line comments can be mixed in one bulk call."""
    mock_run_curl.side_effect = ["{}", '{"labels": {}, "comments": {}}']

    await main.post_bulk_comments(
        "30",
        [
            {"file_path": "/PATCHSET_LEVEL", "message": "Overall LGTM."},
            {"file_path": "src/foo.py", "line_number": 5, "message": "Nit here."},
        ],
        gerrit_base_url="https://gerrit.example.com",
    )

    post_args = mock_run_curl.call_args_list[1][0][0]
    body = json.loads(post_args[post_args.index("--data") + 1])

    ps_comment = body["comments"]["/PATCHSET_LEVEL"][0]
    line_comment = body["comments"]["src/foo.py"][0]

    assert "line" not in ps_comment
    assert line_comment["line"] == 5


# ---------------------------------------------------------------------------
# Failure / error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_failure_response(mock_run_curl):
    mock_run_curl.side_effect = ["{}", '{"error": "not found"}']

    result = await main.post_bulk_comments(
        "999",
        [{"file_path": "f.py", "line_number": 1, "message": "x"}],
        gerrit_base_url="https://gerrit.example.com",
    )

    assert "Failed to post comments" in result[0]["text"]


@pytest.mark.asyncio
async def test_bulk_curl_exception_propagates(mock_run_curl):
    mock_run_curl.side_effect = ["{}", Exception("curl failed")]

    with pytest.raises(Exception, match="curl failed"):
        await main.post_bulk_comments(
            "123",
            [{"file_path": "f.py", "line_number": 1, "message": "x"}],
            gerrit_base_url="https://gerrit.example.com",
        )
