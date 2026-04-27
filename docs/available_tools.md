# Available Tools

This document lists the tools available in the Gerrit MCP Server, extracted from
`gerrit_mcp_server/main.py`.

## Tools

-   **gerrit_authenticate**: Provides Gerrit HTTP Basic credentials (username + HTTP
    password) to the MCP server for the current session. Required when the host uses
    `gerritrc` authentication in `gerrit_config.json`. Read your `~/.gerritrc` file and
    call this tool before using any other tools against that host. Credentials are stored
    in-process only and are never written to disk.
-   **query_changes**: Searches for CLs matching a given query string.
-   **query_changes_by_date_and_filters**: Searches for Gerrit changes within a
    specified date range, optionally filtered by project, a substring in the
    commit message, and change status.
-   **get_change_details**: Retrieves a comprehensive summary of a single CL.
-   **get_commit_message**: Gets the commit message of a change from the current
    patch set.
-   **list_change_files**: Lists all files modified in the most recent patch set
    of a CL.
-   **get_file_diff**: Retrieves the diff for a single, specified file within a
    CL.
-   **list_change_comments**: Lists all comments on a change, grouped by file.
    Useful for reviewing feedback, analyzing comments, and responding to
    comments. Each comment entry includes its unique ID (shown as
    `(id: <comment_id>)`) which is required by `reply_to_comment`.
-   **add_reviewer**: Adds a user or a group to a CL as either a reviewer or a
    CC.
-   **set_ready_for_review**: Sets a CL as ready for review.
-   **set_work_in_progress**: Sets a CL as work-in-progress.
-   **revert_change**: Reverts a single change, creating a new CL.
-   **revert_submission**: Reverts an entire submission, creating one or more
    new CLs.
-   **create_change**: Creates a new change in Gerrit.
-   **set_topic**: Sets the topic of a change. An empty string deletes the
    topic.
-   **changes_submitted_together**: Computes and lists all changes that would be
    submitted together with a given CL.
-   **suggest_reviewers**: Suggests reviewers for a change based on a query.
-   **abandon_change**: Abandons a change.
-   **get_most_recent_cl**: Gets the most recent CL for a user.
-   **get_bugs_from_cl**: Extracts bug IDs from the commit message of a CL.
-   **post_review_comment**: Posts a review comment on a specific line of a file
    in a CL. Optionally accepts a `labels` dict (e.g. `{"Code-Review": 2}`) to
    submit a vote at the same time.
-   **reply_to_comment**: Replies to an existing review comment thread on a CL.
    Requires the comment ID from `list_change_comments` and the file path the
    comment belongs to. By default (`unresolved=False`) the reply marks the
    thread as resolved; pass `unresolved=True` to add a note while keeping the
    thread open.
-   **submit_change**: Submits (merges) a change. Gerrit enforces all submit
    requirements server-side (Code-Review +2, Verified +1) and returns an error
    if they are not met.
