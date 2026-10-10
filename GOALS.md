# Goals

Code-Bot hands tickets from GitHub to Claude Code Remote and reports in Telegram how it went. It decides when which ticket starts, and it adds existing repos as projects.

What is not part of it: creating repos and creating tickets. Another system can do both, or you do them by hand. Code-Bot works without such a system, and such a system works without Code-Bot. The interface between the two is a GitHub issue with the label `ready-for-agent`.

Every change to this repo is measured against these three goals. If it helps none of them, it is not built.

## 1. Delegate from the phone

Start a ticket through Telegram and, at the right moment, only review the PR.

Met when: `/work` → confirmation → finished PR, without me touching a computer, and I learn in Telegram how it went.

## 2. Work through released tickets on its own

What is released gets implemented bit by bit, without me kicking off every single ticket. The order follows from age, dependencies and open PRs.

Met when: a ticket with the label `ready-for-agent` and without open predecessors shows up in `/work` without further upkeep and is started by the Dev-Orchestrator.

## 3. Remind

No project disappears for months. Follow-up questions, proposals for planning sessions and deadlines in the calendar make sure the workers do not run out of work and nothing is left lying around.

Met when: every active project, within its quiet days, either shows activity, has an event in the calendar, or has triggered a follow-up question.

## Why bit by bit

Software is built here in small tickets, not in one big job. Three reasons:

- **Use the subscription without hitting limits.** Small runs spread the usage.
- **Avoid slop.** I make every decision before Claude builds; every PR is small enough to really review.
- **Experience the application.** I test the applications myself so that I know what is being built.

## Way of working

- **Tickets come from outside:** Code-Bot does not prescribe how a ticket is created. What it needs so that a worker can implement it is in the `README.md`.
- **Implementation is delegated:** tickets with the label `ready-for-agent` go to Claude Code Remote, one worker per project. No worker touches other issues.
- **Review stays with me:** I review and merge PRs. Claude never merges on its own.

## Guard rails

- **GitHub issues are the central task management.** There is no second task list. That is why every project has a repo.
- **One project list, one source.** It lives in n8n. Workflows do not search the GitHub account, they ask the project list.
- **Sensitive data stays on your own infrastructure.** Tokens and trigger URLs live in n8n, not with a third party and not in this repo.
- **One worker per project.** A CCR session clones only the repo it works on.
- **Claude starts only from n8n.** No GitHub Actions, no GitHub webhooks, nothing to configure per repo beyond what is unavoidable.
- **The result is always a PR,** a draft PR when there are problems. I fix gaps in a ticket in the ticket itself or in a new one, not through comments from the worker.
- **Adding a repo is rare, working on projects is frequent.** One-time manual work when adding a repo is acceptable, friction in the daily flow is not.
- **Everything can be restored.** The workflows are stored as JSON in this Git repo.
