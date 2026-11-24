"""Record fixture evidence before traversing a real completion edge."""

import issue_lifecycle


def accept_current_issue(store, actor, issue_id):
    issue = store.get_issue(issue_id)
    evidence = store.add_issue_comment(
        actor, issue_id, "Test fixture: verified " + (issue["acceptance"] or issue["title"])
    )
    state = issue_lifecycle.read(store, actor, issue_id, issue["project"])
    return issue_lifecycle.mutate(
        store,
        actor,
        issue_id,
        issue["project"],
        "accept",
        state["version"],
        state["revision"],
        evidence["id"],
        "accept-" + evidence["id"],
        state["asset_version"],
    )
