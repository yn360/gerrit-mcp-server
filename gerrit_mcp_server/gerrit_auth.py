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
This module handles the creation of authentication-specific curl commands for Gerrit.
"""

import contextvars
import os
import uuid
from typing import List, Dict, Any
from weakref import WeakKeyDictionary

# Same env var / default path used by main.py for LOG_FILE_PATH.
_LOG_FILE = os.environ.get("GERRIT_LOG_FILE", "/tmp/server.log")

# Fallback ContextVar — used only when request_ctx is unavailable (unit tests,
# stdio mode outside an active request context).  In production (streamable-HTTP)
# _get_session_key() reads the MCP SDK's own request_ctx instead.
session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "mcp_session_id", default=""
)

# Maps ServerSession objects → stable UUID hex string.
# WeakKeyDictionary so entries are GC'd automatically when a session ends.
_session_key_map: WeakKeyDictionary = WeakKeyDictionary()

# In-process credentials cache for 'gerritrc' auth type.
# Populated at runtime by the gerrit_authenticate MCP tool.
# Key:   session_key (str)  →  {"username": str, "api_key": str}
_credentials_cache: Dict[str, Dict[str, str]] = {}


def _get_session_key() -> str:
    """Return a stable unique key for the current MCP session.

    Reads from the MCP SDK's ``request_ctx`` ContextVar which is reliably set
    for every tool call (both stdio and streamable-HTTP transports).  Each
    session has a unique ``ServerSession`` object; we assign a UUID to it on
    first access and store it in a ``WeakKeyDictionary`` so that the mapping
    is cleaned up automatically when the session ends.

    Falls back to ``session_id_var`` when called outside an active MCP request
    context (unit tests, manual invocations, etc.).
    """
    try:
        from mcp.server.lowlevel.server import request_ctx  # type: ignore[import]

        session = request_ctx.get().session
        if session not in _session_key_map:
            _session_key_map[session] = uuid.uuid4().hex
        return _session_key_map[session]
    except LookupError:
        # Outside MCP request context (unit tests / stdio fallback).
        return session_id_var.get()


def store_gerritrc_credentials(username: str, api_key: str) -> None:
    """Cache HTTP Basic credentials for the current MCP session."""
    key = _get_session_key()
    _credentials_cache[key] = {"username": username, "api_key": api_key}


def _get_auth_for_gob(config: Dict[str, Any]) -> List[str]:
    """Returns the command for gob-curl authentication."""
    return ["gob-curl", "-s"]


def _get_auth_for_http_basic(config: Dict[str, Any]) -> List[str]:
    """Returns the command for HTTP basic authentication."""
    username = config.get("username")
    auth_token = config.get("auth_token")
    if not username or not auth_token:
        raise ValueError(
            "For 'http_basic' authentication, both 'username' and 'auth_token' must be configured."
        )
    return ["curl", "--user", f"{username}:{auth_token}", "-L"]


def _get_auth_for_gitcookies(gerrit_base_url: str, config: Dict[str, Any]) -> List[str]:
    """
    Returns the command for gitcookies authentication, falling back to an
    unauthenticated request if the cookie is not found.
    """
    gitcookies_path_str = config.get("gitcookies_path")
    if not gitcookies_path_str:
        # This indicates a configuration error where gitcookies is the intended
        # method but the path is missing.
        raise ValueError("Authentication method requires 'gitcookies_path' to be set.")

    gitcookies_path = os.path.expanduser(gitcookies_path_str)

    last_found_cookie = None
    if os.path.exists(gitcookies_path):
        domain = (
            gerrit_base_url.replace("https://", "").replace("http://", "").split("/")[0]
        )
        with open(gitcookies_path, "r") as f:
            for line in f:
                if domain in line:
                    parts = line.strip().split("\t")
                    if len(parts) == 7:
                        last_found_cookie = f"{parts[5]}={parts[6]}"

        if last_found_cookie:
            return ["curl", "-b", last_found_cookie, "-L"]

    # Fallback for when the cookie file doesn't exist or has no matching cookie.
    return ["curl", "-s", "-L"]


def _get_auth_for_gerritrc() -> List[str]:
    """Returns curl command using credentials from the current session's cache.

    Credentials are supplied at runtime by calling the ``gerrit_authenticate``
    MCP tool.  Each MCP session (one per Claude Code instance) has its own
    isolated credential store, keyed by a UUID derived from the session's
    ``ServerSession`` object via ``_get_session_key()``.

    Raises:
        ValueError: If no credentials have been cached for this session yet.
    """
    key = _get_session_key()
    with open(_LOG_FILE, "a") as log_file:
        log_file.write(f"[gerrit-auth] lookup: session_key={key!r} cache_keys={list(_credentials_cache.keys())!r}\n")
    creds = _credentials_cache.get(key)
    if not creds:
        raise ValueError(
            f"No credentials cached for this session. "
            "Read your ~/.gerritrc and call gerrit_authenticate(username=..., api_key=...) first."
        )
    return ["curl", "--user", f"{creds['username']}:{creds['api_key']}", "-L"]