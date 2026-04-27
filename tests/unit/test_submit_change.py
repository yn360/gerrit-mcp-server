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

import unittest
from unittest.mock import patch, AsyncMock
import asyncio
import json

from gerrit_mcp_server import main


class TestSubmitChange(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_submit_change_success(self, mock_run_curl):
        async def run_test():
            change_id = "12345"
            subject = "Fix a critical bug"
            mock_run_curl.return_value = json.dumps(
                {
                    "_number": int(change_id),
                    "subject": subject,
                    "status": "MERGED",
                }
            )
            gerrit_base_url = "https://my-gerrit.com"

            result = await main.submit_change(change_id, gerrit_base_url=gerrit_base_url)

            self.assertIn(f"Successfully submitted CL {change_id}", result[0]["text"])
            self.assertIn(f"Subject: {subject}", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_submit_change_api_failure(self, mock_run_curl):
        async def run_test():
            change_id = "12345"
            mock_run_curl.return_value = json.dumps({"status": "NEW"})
            gerrit_base_url = "https://my-gerrit.com"

            result = await main.submit_change(change_id, gerrit_base_url=gerrit_base_url)

            self.assertIn(f"Failed to submit CL {change_id}", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_submit_change_exception(self, mock_run_curl):
        async def run_test():
            change_id = "12345"
            gerrit_base_url = "https://my-gerrit.com"
            mock_run_curl.side_effect = Exception("submit conditions not met")

            with self.assertRaisesRegex(Exception, "submit conditions not met"):
                await main.submit_change(change_id, gerrit_base_url=gerrit_base_url)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
