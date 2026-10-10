# Code-Bot (n8n)

Code-Bot hands tickets from GitHub to Claude Code Remote and reports the result in Telegram. Telegram is the channel, n8n Data Tables hold the project list, GitHub issues are the tasks, Claude Code Remote implements them and opens pull requests.

What the system does:

- **Delegate from the phone:** `/work` in Telegram starts Claude on a ticket; 90 minutes later the PR link arrives.
- **Remind:** follow-up questions about quiet projects, planning sessions and deadlines in the calendar.
- **Work through tickets:** the system works through every issue with the label `ready-for-agent` without further upkeep. How repos and tickets come into being is up to you; `/connect` adds existing repos.

This repo contains the workflow exports (`workflows/CodeBot - *.json`) and the docs. Nothing runs here.
| Where to read on | Content |
|---|---|
| `SETUP.md` | the complete setup, the data tables and troubleshooting |
| `GOALS.md` | goals and guard rails |
| `docs/overview.md` | the whole system as one diagram |
| `docs/workflows.md` | every workflow in detail, and the known limits |

## What you need

An n8n instance reachable over HTTPS, a Claude Pro or Max subscription, and GitHub, Telegram and Google accounts. `SETUP.md` walks through everything.

## Which tickets the system starts

An issue is a startable ticket when all of this applies:

| Condition | How the system recognises it |
|---|---|
| released | label `ready-for-agent` |
| no open predecessors | GitHub's native “blocked by” relationship, or else a line `Blocked by: #1, #2` in the issue text |
| not yet in progress | no open PR that links the issue (`Closes #N`) or comes from the branch `claude/issue-<N>-…`; draft PRs count too |
| not a parent issue | no sub-issues, and no open issue names it as its parent |

No worker touches any other issue. The worker gets the text of the issue and asks no questions, so a good ticket is understandable on its own, says when it is done, is small enough for one PR, and has its decisions made. Whatever is missing the worker decides itself and names in the PR under “Gaps in the issue”; the system sends you that section in Telegram.

## In operation

| You | The system |
|---|---|
| create tickets and release them with the label `ready-for-agent` | starts up to 3 released tickets without open predecessors and without an open PR every morning |
| work through the “Setup” issue once after `/connect` | can then hand the project's tickets to the worker |
| write `/work <key>` | starts the oldest such ticket after confirmation |
| review and merge PRs | makes the successors startable |
| reply to follow-up questions | updates the status and “waiting for” in `codebot_projects` |

Secrets never belong in this repo. They live in n8n credentials and in the Data Tables.

## License

MIT, see `LICENSE`.
