# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Tests for the reply_to_comment MCP tool.
"""

import json
import pytest
from unittest.mock import patch, AsyncMock

from gerrit_mcp_server import main


@pytest.fixture
def mock_run_curl():
    with patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock) as m:
        yield m


# ---------------------------------------------------------------------------
# Payload structure tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reply_resolves_thread_by_default(mock_run_curl):
    """Replies with unresolved=False (default) mark the thread as resolved."""
    mock_run_curl.return_value = '{"labels": {}, "comments": {"src/foo.py": []}}'

    result = await main.reply_to_comment(
        "123", "deadbeef01", "Fixed.", file_path="src/foo.py"
    )

    assert "Reply posted" in result[0]["text"]
    assert "resolved" in result[0]["text"]

    args, _ = mock_run_curl.call_args
    curl_args = args[0]
    data_idx = curl_args.index("--data")
    body = json.loads(curl_args[data_idx + 1])
    comment = body["comments"]["src/foo.py"][0]
    assert comment["in_reply_to"] == "deadbeef01"
    assert comment["message"] == "Fixed."
    assert comment["unresolved"] is False


@pytest.mark.asyncio
async def test_reply_keeps_thread_open_when_unresolved_true(mock_run_curl):
    """Replies with unresolved=True keep the thread open."""
    mock_run_curl.return_value = '{"labels": {}, "comments": {"src/bar.py": []}}'

    result = await main.reply_to_comment(
        "456", "cafebabe", "See comment.", file_path="src/bar.py", unresolved=True
    )

    assert "kept open" in result[0]["text"]

    args, _ = mock_run_curl.call_args
    curl_args = args[0]
    data_idx = curl_args.index("--data")
    body = json.loads(curl_args[data_idx + 1])
    assert body["comments"]["src/bar.py"][0]["unresolved"] is True


@pytest.mark.asyncio
async def test_reply_default_file_path_is_patchset_level(mock_run_curl):
    """When file_path is omitted, the comment is posted to /PATCHSET_LEVEL."""
    mock_run_curl.return_value = '{"labels": {}, "comments": {}}'

    await main.reply_to_comment("789", "aabbccdd", "Looks good.")

    args, _ = mock_run_curl.call_args
    curl_args = args[0]
    data_idx = curl_args.index("--data")
    body = json.loads(curl_args[data_idx + 1])
    assert "/PATCHSET_LEVEL" in body["comments"]


@pytest.mark.asyncio
async def test_reply_posts_to_correct_review_url(mock_run_curl):
    """The tool must POST to /changes/{change_id}/revisions/current/review."""
    mock_run_curl.return_value = '{"labels": {}, "comments": {}}'

    await main.reply_to_comment(
        "321", "abc", "LGTM", gerrit_base_url="https://my-gerrit.com"
    )

    args, _ = mock_run_curl.call_args
    curl_args = args[0]
    assert (
        "https://my-gerrit.com/changes/321/revisions/current/review" in curl_args
    )
    assert "-X" in curl_args
    assert "POST" in curl_args


# ---------------------------------------------------------------------------
# Failure / error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reply_failure_response(mock_run_curl):
    """When Gerrit returns an unexpected body, a failure message is returned."""
    mock_run_curl.return_value = '{"error": "change not found"}'

    result = await main.reply_to_comment("999", "xyz", "hello")

    assert "Failed to post reply" in result[0]["text"]


@pytest.mark.asyncio
async def test_reply_curl_exception_is_propagated(mock_run_curl):
    """If run_curl raises, the exception bubbles up."""
    mock_run_curl.side_effect = Exception("network error")

    with pytest.raises(Exception, match="network error"):
        await main.reply_to_comment("123", "abc", "hi")
