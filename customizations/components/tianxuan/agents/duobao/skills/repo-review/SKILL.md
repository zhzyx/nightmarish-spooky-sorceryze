---
name: duobao-repo-review
description: Review repository changes for Tianxuan and coordinate concurrent merges using Git facts.
---

Read the repository, target branch, protection policy and authorization from the host. Base review on Git objects: commit, tree, diff and the actual merge base.

Check the diff against the stated intent, protected paths, tests and rollback. Report blocking and non-blocking findings with file and line; never approve on behalf of a human reviewer.

For concurrent merges, isolate each candidate in its own worktree, verify the merge base still matches, and hand technical conflicts to the integration owner with both versions preserved.

On unknown remote state, read back the original ref before retrying. Do not force-push protected branches.

Report through the shared Diting binding; local receipts are not delivery.
