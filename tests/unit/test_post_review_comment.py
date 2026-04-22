import json
import unittest
from unittest.mock import patch, AsyncMock
import asyncio

from gerrit_mcp_server.main import post_review_comment


class TestPostReviewComment(unittest.TestCase):
    @patch('gerrit_mcp_server.main.run_curl', new_callable=AsyncMock)
    def test_post_review_comment_with_labels(self, mock_run_curl):
        # First call: GET existing comments (none found), second call: POST review
        mock_run_curl.side_effect = ['{}', '{"done": true}']
        asyncio.run(post_review_comment(
            '123', 'test.py', 1, 'test comment',
            labels={'Verified': 1},
            gerrit_base_url='https://gerrit-review.googlesource.com',
        ))
        # The second call is the POST to /revisions/current/review
        post_call_args = mock_run_curl.call_args_list[1][0][0]
        data_idx = post_call_args.index('--data')
        body = json.loads(post_call_args[data_idx + 1])
        comment = body['comments']['test.py'][0]
        self.assertEqual(comment['line'], 1)
        self.assertEqual(comment['message'], 'test comment')
        self.assertEqual(comment['unresolved'], True)
        self.assertNotIn('in_reply_to', comment)
        self.assertEqual(body['labels'], {'Verified': 1})

    @patch('gerrit_mcp_server.main.run_curl', new_callable=AsyncMock)
    def test_post_creates_standalone_when_no_existing_comments(self, mock_run_curl):
        mock_run_curl.side_effect = ['{}', '{"labels": {}, "comments": {}}']
        asyncio.run(post_review_comment(
            '42', 'src/foo.py', 10, 'looks good',
            gerrit_base_url='https://gerrit-review.googlesource.com',
        ))
        post_call_args = mock_run_curl.call_args_list[1][0][0]
        data_idx = post_call_args.index('--data')
        body = json.loads(post_call_args[data_idx + 1])
        comment = body['comments']['src/foo.py'][0]
        self.assertNotIn('in_reply_to', comment)

    @patch('gerrit_mcp_server.main.run_curl', new_callable=AsyncMock)
    def test_post_replies_to_existing_unresolved_thread(self, mock_run_curl):
        existing_comment = {
            'id': 'abc123',
            'line': 5,
            'message': 'Original comment',
            'unresolved': True,
            'updated': '2025-01-01 10:00:00.000000000',
            'author': {'name': 'reviewer'},
        }
        mock_run_curl.side_effect = [
            json.dumps({'src/bar.py': [existing_comment]}),
            '{"labels": {}, "comments": {}}',
        ]
        asyncio.run(post_review_comment(
            '99', 'src/bar.py', 5, 'Addressed.',
            gerrit_base_url='https://gerrit-review.googlesource.com',
        ))
        post_call_args = mock_run_curl.call_args_list[1][0][0]
        data_idx = post_call_args.index('--data')
        body = json.loads(post_call_args[data_idx + 1])
        comment = body['comments']['src/bar.py'][0]
        self.assertEqual(comment['in_reply_to'], 'abc123')
        self.assertEqual(comment['message'], 'Addressed.')

    @patch('gerrit_mcp_server.main.run_curl', new_callable=AsyncMock)
    def test_post_does_not_reply_when_existing_thread_is_resolved(self, mock_run_curl):
        resolved_comment = {
            'id': 'dead0001',
            'line': 7,
            'message': 'Already fixed',
            'unresolved': False,
            'updated': '2025-01-01 09:00:00.000000000',
            'author': {'name': 'reviewer'},
        }
        mock_run_curl.side_effect = [
            json.dumps({'src/baz.py': [resolved_comment]}),
            '{"labels": {}, "comments": {}}',
        ]
        asyncio.run(post_review_comment(
            '77', 'src/baz.py', 7, 'New issue here.',
            gerrit_base_url='https://gerrit-review.googlesource.com',
        ))
        post_call_args = mock_run_curl.call_args_list[1][0][0]
        data_idx = post_call_args.index('--data')
        body = json.loads(post_call_args[data_idx + 1])
        comment = body['comments']['src/baz.py'][0]
        # Falls back to replying to resolved comment (most recent) since no unresolved exist
        self.assertEqual(comment['in_reply_to'], 'dead0001')

    @patch('gerrit_mcp_server.main.run_curl', new_callable=AsyncMock)
    def test_post_falls_back_to_standalone_if_comments_fetch_fails(self, mock_run_curl):
        mock_run_curl.side_effect = [
            Exception('network error'),
            '{"labels": {}, "comments": {}}',
        ]
        asyncio.run(post_review_comment(
            '55', 'src/err.py', 3, 'comment',
            gerrit_base_url='https://gerrit-review.googlesource.com',
        ))
        post_call_args = mock_run_curl.call_args_list[1][0][0]
        data_idx = post_call_args.index('--data')
        body = json.loads(post_call_args[data_idx + 1])
        comment = body['comments']['src/err.py'][0]
        self.assertNotIn('in_reply_to', comment)


if __name__ == '__main__':
    unittest.main()
