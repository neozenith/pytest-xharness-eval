# Ticketing

This repository tracks work in GitHub Issues at `neozenith/pytest-xharness-eval`.
Run commands from the repository root. All `gh` commands use the account selected here.

## Who Am I

Corroborate the Git author with the GitHub login before filtering or changing work.
The maintainer is Josh Peak, with Git email `neozenith.dev@gmail.com` and GitHub login `neozenith`.

```sh
git config user.name
git config user.email
GH_TOKEN="$(gh auth token --user neozenith)" gh api user --jq .login
```

Stop if these identities disagree. Select the account per command, without switching the default login:

```sh
GH_TOKEN="$(gh auth token --user neozenith)" gh issue list --repo neozenith/pytest-xharness-eval
```

## Backlog

Assign every issue to `neozenith`.

| Category | Title prefix | Label |
|----------|--------------|-------|
| Bug | `[bug]` | `bug` |
| Feature | `[feat]` | `enhancement` |

Write the problem and acceptance criteria in a body file. Create the issue with the matching prefix and label.

```sh
GH_TOKEN="$(gh auth token --user neozenith)" gh issue create --repo neozenith/pytest-xharness-eval --title "[feat] {title}" --label enhancement --assignee neozenith --body-file {body-file}
```

## Deduplication

Search open and closed issues before creating one. Broaden the search if the first keywords miss related work.

```sh
GH_TOKEN="$(gh auth token --user neozenith)" gh issue list --repo neozenith/pytest-xharness-eval --state all --search "{keywords} in:title,body" --json number,title,state,createdAt --limit 200
```

The earliest issue for the same work is canonical. Report its URL instead of filing another issue.
Close existing later duplicates against it:

```sh
GH_TOKEN="$(gh auth token --user neozenith)" gh issue close {duplicate} --repo neozenith/pytest-xharness-eval --duplicate-of {canonical}
```

Keep one tracking comment on the canonical issue, with `Duplicates: N` followed by one issue link per bullet.
Create it on the first duplicate and edit that same comment thereafter.
Rewrite the canonical title and body when a duplicate adds useful requirements. Preserve its scope and acceptance criteria.
Use a thumbs-up reaction for repeat demand. Demand is the duplicate count plus total reactions.
Matching a closed issue does not reopen it automatically. Ask whether the request is a regression or unfinished work.

## Relationships

Use GitHub's `blocked by` and `blocking` relationships to form an acyclic dependency graph.
Check transitive blockers before adding a link. Ask about dependencies when creating an issue if they cannot be established from the request.

```sh
GH_TOKEN="$(gh auth token --user neozenith)" gh issue edit {issue} --repo neozenith/pytest-xharness-eval --add-blocked-by {blocker}
GH_TOKEN="$(gh auth token --user neozenith)" gh issue list --repo neozenith/pytest-xharness-eval --state all --json number,title,state,labels,blockedBy,blocking,reactionGroups,comments --limit 200
```

An issue is ready when every blocker is closed. Retrieve missing linked issues and increase the limit if the listing reaches it.
Choose ready issues in dependency order. Break ties by most open issues unblocked, bug before feature, highest demand, then lowest issue number.

## Works In Progress (WIP)

List open issues assigned to `neozenith`, draft and ready PRs authored by `neozenith`, local branches, and worktrees.
Group by feature branch without a PR, draft PR, and open PR. List unmatched issues, branches, PRs, and worktrees separately.

```sh
GH_TOKEN="$(gh auth token --user neozenith)" gh issue list --repo neozenith/pytest-xharness-eval --assignee neozenith --state open --json number,title,url --limit 200
GH_TOKEN="$(gh auth token --user neozenith)" gh pr list --repo neozenith/pytest-xharness-eval --author neozenith --state open --json number,title,isDraft,headRefName,body,url --limit 200
git branch --list
git worktree list --porcelain
```

Use `XHE` as the issue key prefix and four descriptive words, kebab-cased in paths.

| Item | Bug | Feature |
|------|-----|---------|
| Branch | `fix/XHE-{number}-{description}` | `feat/XHE-{number}-{description}` |
| PR title | `[bug] XHE-{number} {description}` | `[feat] XHE-{number} {description}` |
| Worktree | `../XHE-{number}-{description}` | `../XHE-{number}-{description}` |

The PR body contains `Closes #{number}`. Prefer a sibling worktree based on fresh `origin/main`.
Match older work through PR closing references, body links, and branch names without renaming it.
When no open PR or active development branch remains, report ready backlog issues in dependency order and what each unblocks.

## Completed Work

Judge completion against freshly fetched `origin/main`. Start every cleanup plan by updating local `main` to match it without discarding work.
Name dirty files or local commits that prevent the update. Stop that step if a fast-forward is impossible.

| Trigger | Issue | Branches and worktrees |
|---------|-------|------------------------|
| PR merged | Close its related issue | Remove its local and remote branch and associated worktree |
| PR closed unmerged | Keep its related issue open | Remove its local and remote branch and associated worktree |
| Issue closed | Keep closed | Remove related branches and worktrees |

Present one cleanup section per trigger, with each affected item on its own line. Ask once before closing issues or removing branches and worktrees.
Flag uncommitted changes and commits that removal would lose. Never force removal; report refused removals and unmatched work left untouched.
