import unittest

from gerrit_mcp_server.main import mcp


EXPECTED_TOOLS = {
    "gerrit_authenticate",
    "query_changes",
    "query_changes_by_date_and_filters",
    "get_change_details",
    "get_commit_message",
    "list_change_files",
    "get_file_diff",
    "list_change_comments",
    "add_reviewer",
    "set_ready_for_review",
    "set_work_in_progress",
    "revert_change",
    "revert_submission",
    "create_change",
    "set_topic",
    "changes_submitted_together",
    "suggest_reviewers",
    "abandon_change",
    "get_most_recent_cl",
    "get_bugs_from_cl",
    "post_review_comment",
    "post_bulk_comments",
    "reply_to_comment",
    "submit_change",
}


class TestToolRegistration(unittest.TestCase):
    def test_all_expected_tools_are_registered(self):
        registered = {tool.name for tool in mcp._tool_manager.list_tools()}
        missing = EXPECTED_TOOLS - registered
        self.assertEqual(missing, set(), f"Tools missing @mcp.tool() decorator: {missing}")

    def test_no_unexpected_tools_registered(self):
        registered = {tool.name for tool in mcp._tool_manager.list_tools()}
        unexpected = registered - EXPECTED_TOOLS
        self.assertEqual(unexpected, set(), f"Unexpected tools registered: {unexpected}")


if __name__ == "__main__":
    unittest.main()
