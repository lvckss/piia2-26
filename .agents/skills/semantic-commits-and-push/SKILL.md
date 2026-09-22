---
description: Group all current repository changes into meaningful semantic commits and push the current branch
---

Group all current repository changes into meaningful, atomic commits and push the current branch.

Optional context for commit messages:

$ARGUMENTS

## Objective

Inspect every current repository change, group related files by intent, create clear semantic commits, and push the current branch only after all commits succeed.

Do not modify the contents of any file. This command is only for reviewing, staging, committing, and pushing changes that already exist.

## Safety rules

- Do not revert, discard, overwrite, or modify existing changes.
- Do not use `git add .`, `git add -A`, or another command that stages unrelated files implicitly.
- Do not use `--no-verify`.
- Do not amend existing commits.
- Do not use `git reset --hard`.
- Do not use `git clean`.
- Do not force-push.
- Do not create empty commits.
- Do not bypass failed hooks or checks.
- Do not switch branches.
- Do not rebase, merge, pull, or rewrite history.
- Do not include files whose purpose has not been understood.
- Do not silently ignore untracked, modified, staged, renamed, or deleted files.

## Initial inspection

Before staging or committing anything, inspect the complete repository state.

Run:

```bash
git status --short
git status --branch
git diff --stat
git diff
git diff --cached --stat
git diff --cached
git log --oneline -10
```

Also determine:

- The current branch.
- Whether the branch has a configured upstream.
- Whether the repository is in the middle of a merge, rebase, cherry-pick, or revert.
- Whether there are unresolved conflicts.
- Which files are untracked, renamed, deleted, staged, or partially staged.
- The commit-message style used by recent commits.

If there is an unfinished Git operation, unresolved conflict, detached `HEAD`, or another unsafe repository state, stop and explain the problem before making commits.

If there are no changes to commit, report that and stop without pushing.

## Sensitive-file inspection

Before staging anything, inspect filenames and diffs for sensitive or suspicious material, including:

- `.env` files
- API keys
- access tokens
- passwords
- credentials
- private keys
- certificates
- signing keys
- secret configuration
- authentication cookies
- database dumps
- files containing production secrets

Do not assume a file is safe solely because it is already tracked.

If any file may contain sensitive information, stop before staging or committing and clearly identify the file and concern.

## Change analysis

Analyze the actual diff and group changes by their logical intent, not merely by directory or file type.

Use categories such as:

- `feat`
- `fix`
- `refactor`
- `test`
- `docs`
- `chore`
- `build`
- `ci`
- `perf`
- `style`
- `release`
- `config`

Each commit must represent one coherent change.

Create multiple commits when changes are independently understandable, reviewable, or revertible.

Do not mix unrelated changes in the same commit.

Keep directly related implementation, tests, fixtures, types, migrations, and documentation together when they form one logical change.

Treat renames and deletions as part of their related logical change.

Treat formatting-only, generated, vendored, lockfile, dependency, or mechanical changes separately unless they are inseparable from the functional change.

Preserve existing partial staging when it reflects a clear intentional boundary. If staged and unstaged portions of the same file belong to different logical commits and cannot be safely separated without editing the file or using interactive staging, stop and explain the ambiguity.

## Commit-message rules

Use concise semantic commit messages consistent with the repository’s recent history.

Prefer this format when compatible with the repository:

```text
type(scope): imperative summary
```

Examples:

```text
feat(auth): add session refresh handling
fix(api): prevent duplicate retry requests
refactor(cli): simplify configuration loading
test(parser): cover malformed input cases
docs(readme): clarify local setup
chore(deps): update runtime dependencies
```

Commit messages must:

- Describe the actual change.
- Use an imperative, concise summary.
- Avoid vague messages such as `update files`, `changes`, or `fix stuff`.
- Avoid claiming behavior not supported by the diff.
- Follow the repository’s established style when it differs from Conventional Commits.
- Use `$ARGUMENTS` only as additional context.
- Ignore or adapt `$ARGUMENTS` when it does not accurately match the changes.
- Never force the exact wording from `$ARGUMENTS` into a misleading commit message.

## Commit plan

Before creating commits, show a proposed plan.

For each proposed commit, include:

1. The proposed commit message.
2. The exact files included.
3. A brief explanation of the shared intent.
4. Any notable staged, unstaged, generated, renamed, deleted, or untracked files.
5. Any files intentionally excluded and the reason.

Proceed automatically only when the grouping is clearly supported by the diff.

If multiple materially different groupings are equally reasonable, a file contains unrelated changes that cannot be safely separated, or the intent of a change cannot be determined, stop and ask for clarification before committing.

Do not ask for confirmation merely because there are multiple commits when the grouping is otherwise clear.

## Commit execution

For each approved logical group:

1. Stage only the exact files belonging to that group:

   ```bash
   git add -- <file1> <file2>
   ```

2. When applicable, stage deletions or renames explicitly and only for that group.

3. Review the staged result:

   ```bash
   git diff --cached --stat
   git diff --cached
   ```

4. Confirm that the staged diff contains only the intended logical change.

5. Create the commit using the planned semantic message.

6. If a commit hook, validation check, or commit command fails:
   - Stop immediately.
   - Do not bypass the failure.
   - Do not retry with `--no-verify`.
   - Report the command and relevant error.
   - Leave the repository in its current recoverable state.

7. After each successful commit, inspect the remaining changes again:

   ```bash
   git status --short
   git diff --stat
   git diff
   git diff --cached --stat
   git diff --cached
   ```

Do not modify files to make them fit the proposed commit structure.

## Pre-push verification

After all intended commits have been created, run:

```bash
git status --short
git log --oneline -10
```

Verify that:

- Every intended change was committed.
- No intended file was omitted.
- No unrelated or sensitive file was included.
- The working tree has no unexpected remaining changes.
- All commits were created successfully.
- The current branch is still the original branch.

If unexpected changes remain, do not push until they have been explained.

## Push

Push only after every commit has succeeded and the final repository state is understood.

If the current branch has an upstream, run:

```bash
git push
```

If the current branch has no upstream, run:

```bash
git push --set-upstream origin HEAD
```

Do not push to a different branch or remote.

Do not use `--force` or `--force-with-lease`.

If the push is rejected, stop and report the reason. Do not pull, rebase, merge, reset, or rewrite history automatically.

## Final summary

When finished, report:

- The branch that was pushed.
- The remote used.
- Every commit created, including its short hash and message.
- The files or logical purpose included in each commit.
- Whether the push succeeded.
- Any remaining uncommitted or untracked files.
- Any warnings or checks that require attention.
