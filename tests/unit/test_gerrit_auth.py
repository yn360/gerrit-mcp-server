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
Tests for the gerrit_auth module.
"""

import unittest
from unittest.mock import patch, mock_open
from gerrit_mcp_server import gerrit_auth


def _clean_cache(session_id: str) -> None:
    """Helper: remove a session entry from the in-process cache."""
    gerrit_auth._credentials_cache.pop(session_id, None)


class TestGerritAuth(unittest.TestCase):

    def test_get_auth_for_gob(self):
        """Tests that the correct command is returned for gob-curl."""
        self.assertEqual(gerrit_auth._get_auth_for_gob({}), ["gob-curl", "-s"])

    def test_get_auth_for_http_basic_success(self):
        """Tests that the correct command is returned for http_basic auth."""
        config = {"username": "testuser", "auth_token": "secret"}
        expected = ["curl", "--user", "testuser:secret", "-L"]
        self.assertEqual(gerrit_auth._get_auth_for_http_basic(config), expected)

    def test_get_auth_for_http_basic_missing_username(self):
        """Tests that an error is raised if username is missing for http_basic."""
        with self.assertRaisesRegex(ValueError, "both 'username' and 'auth_token'"):
            gerrit_auth._get_auth_for_http_basic({"auth_token": "secret"})

    def test_get_auth_for_http_basic_missing_token(self):
        """Tests that an error is raised if auth_token is missing for http_basic."""
        with self.assertRaisesRegex(ValueError, "both 'username' and 'auth_token'"):
            gerrit_auth._get_auth_for_http_basic({"username": "testuser"})

    @patch("os.path.exists", return_value=True)
    def test_get_auth_for_gitcookies_success(self, mock_exists):
        """Tests that the correct command is returned for gitcookies auth."""
        config = {"gitcookies_path": "~/.gitcookies"}
        url = "https://my-gerrit.com"
        m = mock_open(
            read_data="my-gerrit.com\tFALSE\t/\tTRUE\t2147483647\to\tgit-token"
        )
        with patch("builtins.open", m):
            command = gerrit_auth._get_auth_for_gitcookies(url, config)
        self.assertEqual(command, ["curl", "-b", "o=git-token", "-L"])

    @patch("os.path.exists", return_value=False)
    def test_get_auth_for_gitcookies_file_not_found(self, mock_exists):
        """Tests fallback to unauthenticated curl if gitcookies file is not found."""
        config = {"gitcookies_path": "~/.gitcookies"}
        url = "https://my-gerrit.com"
        command = gerrit_auth._get_auth_for_gitcookies(url, config)
        self.assertEqual(command, ["curl", "-s", "-L"])

    def test_get_auth_for_gitcookies_missing_path(self):
        """Tests that an error is raised if gitcookies_path is missing."""
        with self.assertRaisesRegex(ValueError, "requires 'gitcookies_path'"):
            gerrit_auth._get_auth_for_gitcookies("https://a.com", {})

    @patch("os.path.exists", return_value=True)
    def test_get_auth_for_gitcookies_selects_last_entry(self, mock_exists):
        """Tests that _get_auth_for_gitcookies selects the last matching cookie entry."""
        config = {"gitcookies_path": "~/.gitcookies"}
        url = "https://my-gerrit.com"
        multi_cookie_content = (
            "other-gerrit.com\tFALSE\t/\tTRUE\t2147483647\to\tgit-oldtoken\n"
            "my-gerrit.com\tFALSE\t/\tTRUE\t2147483647\to\tgit-firsttoken\n"
            "another-gerrit.com\tFALSE\t/\tTRUE\t2147483647\to\tgit-anothertoken\n"
            "my-gerrit.com\tFALSE\t/\tTRUE\t2147483647\to\tgit-lasttoken"
        )
        m = mock_open(read_data=multi_cookie_content)
        with patch("builtins.open", m):
            command = gerrit_auth._get_auth_for_gitcookies(url, config)
        self.assertEqual(command, ["curl", "-b", "o=git-lasttoken", "-L"])


    # --- gerritrc auth tests ---

    def test_store_gerritrc_credentials_caches_by_session(self):
        """Tests that credentials are stored under the current session_id."""
        sid = "unit-test-session-store"
        _clean_cache(sid)
        token = gerrit_auth.session_id_var.set(sid)
        try:
            with patch("builtins.open", mock_open()):
                gerrit_auth.store_gerritrc_credentials("alice", "s3cr3t")
            self.assertEqual(
                gerrit_auth._credentials_cache.get(sid),
                {"username": "alice", "api_key": "s3cr3t"},
            )
        finally:
            gerrit_auth.session_id_var.reset(token)
            _clean_cache(sid)

    def test_store_gerritrc_credentials_overwrites_previous(self):
        """Tests that storing credentials twice replaces the old entry."""
        sid = "unit-test-session-overwrite"
        _clean_cache(sid)
        token = gerrit_auth.session_id_var.set(sid)
        try:
            with patch("builtins.open", mock_open()):
                gerrit_auth.store_gerritrc_credentials("alice", "first")
                gerrit_auth.store_gerritrc_credentials("alice", "second")
            self.assertEqual(
                gerrit_auth._credentials_cache[sid]["api_key"], "second"
            )
        finally:
            gerrit_auth.session_id_var.reset(token)
            _clean_cache(sid)

    def test_get_auth_for_gerritrc_returns_curl_command(self):
        """Tests that _get_auth_for_gerritrc returns the correct curl command."""
        sid = "unit-test-session-lookup"
        gerrit_auth._credentials_cache[sid] = {"username": "bob", "api_key": "topsecret"}
        token = gerrit_auth.session_id_var.set(sid)
        try:
            with patch("builtins.open", mock_open()):
                result = gerrit_auth._get_auth_for_gerritrc()
            self.assertEqual(result, ["curl", "--user", "bob:topsecret", "-L"])
        finally:
            gerrit_auth.session_id_var.reset(token)
            _clean_cache(sid)

    def test_get_auth_for_gerritrc_raises_when_no_credentials(self):
        """Tests that _get_auth_for_gerritrc raises ValueError when no creds cached."""
        sid = "unit-test-session-missing"
        _clean_cache(sid)
        token = gerrit_auth.session_id_var.set(sid)
        try:
            with patch("builtins.open", mock_open()):
                with self.assertRaisesRegex(ValueError, "No credentials cached"):
                    gerrit_auth._get_auth_for_gerritrc()
        finally:
            gerrit_auth.session_id_var.reset(token)

    def test_sessions_are_isolated(self):
        """Tests that credentials from one session are not visible in another."""
        sid_a = "unit-test-session-a"
        sid_b = "unit-test-session-b"
        _clean_cache(sid_a)
        _clean_cache(sid_b)

        token_a = gerrit_auth.session_id_var.set(sid_a)
        try:
            with patch("builtins.open", mock_open()):
                gerrit_auth.store_gerritrc_credentials("userA", "passA")
        finally:
            gerrit_auth.session_id_var.reset(token_a)

        token_b = gerrit_auth.session_id_var.set(sid_b)
        try:
            with patch("builtins.open", mock_open()):
                with self.assertRaisesRegex(ValueError, "No credentials cached"):
                    gerrit_auth._get_auth_for_gerritrc()
        finally:
            gerrit_auth.session_id_var.reset(token_b)
            _clean_cache(sid_a)


if __name__ == "__main__":
    unittest.main()
