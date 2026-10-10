# Workflows (reference)

The diagram of how they fit together is in `overview.md`; the setup, the data tables and troubleshooting are in `../SETUP.md`.

All files are in `workflows/`.

| Workflow | File | Trigger |
|---|---|---|
| CodeBot - Telegram Router | `CodeBot - Telegram Router.json` | Telegram trigger (`message`, `callback_query`) |
| CodeBot - /work (Telegram → Claude) | `CodeBot - _work (Telegram → Claude).json` | called by the router |
| CodeBot - Chat | `CodeBot - Chat.json` | called by the router |
| CodeBot - Connect Repo | `CodeBot - Connect Repo.json` | called by the router |
| CodeBot - Start Claude Routine | `CodeBot - Start Claude Routine.json` | called from /work and the Dev-Orchestrator |
| CodeBot - Signal Sweep | `CodeBot - Signal Sweep.json` | schedule, hourly |
| CodeBot - Dev-Orchestrator | `CodeBot - Dev-Orchestrator.json` | schedule, daily at 7:00 |
| CodeBot - Planning | `CodeBot - Planning.json` | schedule, daily at 8:00, or called by the router |
| CodeBot - Setup (one-time) | `CodeBot - Setup (one-time).json` | manual, only for a new installation |

The exports contain no workflow IDs; n8n assigns them on import. Sub-workflow references are therefore empty and are selected after the import.

## Credentials

| Name in n8n | Type | Placeholder ID in the exports | Used for |
|---|---|---|---|
| Telegram CodeBot account | telegramApi | `TELEGRAM_CREDENTIAL_ID` | Telegram trigger and Telegram nodes |
| Header Auth account | httpHeaderAuth | `GITHUB_HEADER_AUTH_CREDENTIAL_ID` | GitHub GraphQL (`Authorization: Bearer …`) |
| GitHub account | githubApi | `GITHUB_CREDENTIAL_ID` | GitHub REST in CodeBot - Connect Repo (check repo, label, setup issue) |
| Google Gemini(PaLM) Api account | googlePalmApi | `GEMINI_CREDENTIAL_ID` | Gemini models |
| Google Calendar account 2 | googleCalendarOAuth2Api | `GOOGLE_CALENDAR_CREDENTIAL_ID` | Dev-Orchestrator, CodeBot - Planning |

The credential “Claude Code n8n Routine” (Bearer) is no longer used; the tokens come from `codebot_routines`.

## Shared building blocks

- **`Settings` → `Config`**: `Settings` reads `codebot_settings`; `Config` takes `CHAT_ID` (`telegram_chat_id`), `TIMEZONE` (`timezone`) and, where needed, `CALENDAR_ID` (`calendar_id`) and the ticket label (`ready_label`, default `ready-for-agent`) from it, and stops with `… is missing in codebot_settings` if a required value is absent. The remaining constants in `Config` are tuning values under `ADJUST HERE`.
- **Data Table nodes** address the tables by name (`mode: name`). Read nodes have `executeOnce` and `alwaysOutputData`; with an empty table an empty item arrives, which the Code nodes filter out through `r.key`.
- **`Build GitHub query` → `GitHub`** (Chat, Signal Sweep, Dev-Orchestrator): the Code node builds a GraphQL query from the repos in `codebot_projects`. Aliases `r0`, `r1`, … return `pushedAt` per repo, `search` returns the open issues (and PRs) with `repo:` filters. The GraphQL node has `onError: continueRegularOutput`; without data the workflows carry on and report it.
- **`openBlockers(issue, openSet)`** (/work, Dev-Orchestrator): open predecessors from `blockedBy` plus the line `Blocked by: #n` in the issue text.
- **Templates** (Connect Repo): the text of the setup issue and the workers' prompt are the constants `ISSUE_TEMPLATE` and `WORKER_PROMPT` in the `Config` node, between the markers `// >>> …` and `// <<< …`. The node `Prepare issue` only computes the values and switches and fills the template (`fill`). The notation is under “Template notation” below.
- **Telegram messages** go out with `parse_mode: HTML` and escaped `& < >`. The node's default is Markdown, which breaks on underscores in repo names and links.

## CodeBot - Telegram Router

`Telegram Trigger` → `Settings` → `Route` → `Where to?` → four Execute Workflow nodes (they do not wait for the sub-workflow).

| Input | Target |
|---|---|
| sender is not `telegram_chat_id` from `codebot_settings` | discarded |
| `callback_query` with `data` starting with `p\|` or `w\|` | CodeBot - /work |
| `callback_query` with `data` starting with `s\|` | CodeBot - Planning |
| `callback_query` with another prefix | discarded |
| text starts with `/work` | CodeBot - /work |
| text starts with `/plan` | CodeBot - Planning |
| text starts with `/connect`, or is `connect <address on github.com>` | CodeBot - Connect Repo |
| everything else, unknown commands too | CodeBot - Chat |

Hand-over to the sub-workflows: `{ route, update }`; `update` is the unchanged Telegram update. A discarded update leaves `Route` as `{ route: 'ignored', reason }`; no output of `Where to?` takes it, so the execution ends there and the reason is in the output of `Route`. New workflows with buttons reserve their callback prefix in the node `Route`.

The four Execute Workflow nodes contain no workflow ID, because the target workflows only get one on import. Select the workflows there after the import.

## CodeBot - /work (Telegram → Claude)

`From router` → `Settings` → `Router` (Code, checks the chat against `telegram_chat_id`, returns `kind`) → `Which case?`

| `kind` | Trigger | Flow |
|---|---|---|
| `list` | `/work` | `Projects: List` → `Build project list` → send |
| `command` | `/work <key\|repo\|owner/repo>` | `Projects` → `Resolve repo` → `GitHub: Oldest issues` → `Oldest issue` → `Issue found?` → send or `Telegram: Info` |
| `pick` | button `p\|<key>` | `Acknowledge selection`, then as for `command` |
| `callback` | button `w\|<y\|n>\|<owner/repo>\|<no>` | `Acknowledge button` → `Update message` → `Answer = yes?` → `GitHub: Fetch issue` → `Build contract` → `Start Claude Routine` |

- `Build project list`: projects with a repo, without the status Done / Paused / Someday, by priority and name; buttons above 64 bytes are dropped.
- `Resolve repo`: matches only in `codebot_projects` (key, `owner/repo` or repo name). No match → a note, no fallback to the account.
- `Oldest issue`: the 100 oldest open issues; of those only the ones with the label `ready-for-agent` (`ready_label` from `Settings`); without those with an open PR; the oldest one **without open predecessors**. The preview says how many older ones were skipped and how many are waiting for their PR to be reviewed. If there is no ticket with the label, a note arrives; if all have an open PR, a link to the PR list.
- **Parent issues are not tickets** (same for /work and the Dev-Orchestrator): an issue with sub-issues, or one that an open issue names as its parent (natively, a section `## Parent` with `#N`, or a line `Parent: #N` / `Part of #N`), is never started, not even with `ready-for-agent`.
- **Open PR for the ticket** (same for /work and the Dev-Orchestrator): an open PR that links the issue (`Closes #N`), or an open PR from the branch `claude/issue-<N>-…`. Draft PRs count too. Such a ticket is not started again, no matter how long the PR sits. If the PR is closed without a merge, the ticket is startable again.
- Sending: `Prepare send` (takes `telegram_bot_token` from `Settings`) → `Send to Telegram (API)`. The HTTP node stays because the Telegram node does not accept a freely built `reply_markup`.
- `Build contract` sets `source: 'telegram-work'` and `force: true`. The call does not wait for the sub-workflow.

## CodeBot - Start Claude Routine

Input per item:

| Field | Required | Meaning |
|---|---|---|
| `repo` | yes | `owner/name`; determines the worker |
| `issue_number` | yes | |
| `title` | yes | |
| `url`, `body`, `extra` | no | link, issue text, extra note |
| `source` | no | origin, appears in the Telegram message |
| `force` | no | ignore the double-start guard |
| `dedup_hours` | no | lock time per issue, default 168 |

Flow:

1. `Prepare`: key `repo#number`, lock through workflow static data, builds `text` (at most 60,000 characters).
2. `Settings` (for the chat ID of the Telegram messages) → `Routines` → `Assign worker`: the row in `codebot_routines` with the same `repo` and `active` not `false`.
3. `Worker exists?` No → `Telegram: No worker`.
4. `Routine API`: `POST https://api.anthropic.com/v1/claude_code/routines/{{fire_url}}/fire` (`fire_url` is the ID `trig_…`; if a whole address is already there, it is called unchanged), headers `Authorization: Bearer {{token}}`, `anthropic-version: 2023-06-01`, `anthropic-beta: experimental-cc-routine-2026-04-01`, body `{ text }`. Errors carry on (`continueRegularOutput`).
5. `Remember`: on success a timestamp in static data and the message “Claude started” with a session link; on failure a message with the error text, no entry.
6. **Watchdog:** `Started?` → `Wait` (90 minutes) → `GitHub: Find PR` (the 30 newest PRs of the repo) → `Result` → `Telegram: Result`.

`Result` recognises the PR by: created after the start and branch `claude/issue-<N>…`, or a linked issue, or `Closes #N` in the text. Message: the PR link with its status (ready, draft, merged, closed) and the section “Gaps in the issue” from the PR text; otherwise “No PR” with the session link.

## CodeBot - Chat

`From router` → `Settings` → `Config` → `Only me` (text messages only) → `Projects` → `Build GitHub query` → `GitHub` → `Build context` → `CodeBot agent` → `Parse reply` → `Telegram: Reply` → `Prepare updates` → `Update project`.

- `Build context`: one text block per project (without the status Done) with status, priority, last activity, deadline, **next planning session**, waiting state, next step, description, open issues and PRs.
- `CodeBot agent` (Gemini, `Memory`: 20 messages per chat). The system message is generic; adapt who you are and the reply language there (`SETUP.md`, step 6). Status changes are in the hidden block `<update>[{"key": …}]</update>`.
- `Prepare updates` computes the new values of `status`, `waiting_for`, `waiting_since`, `next_step`, `last_checkin` per project; `Update project` writes these five columns.
- Reply to a follow-up question: the project is recognised by `[key]` at the start of the quoted message.
- All project fields go to Gemini. That is why tokens are never in `codebot_projects`.

## CodeBot - Connect Repo

Adds an existing repo as a project (`/connect`). Nothing is committed in the repo: the label and exactly one issue are created.

`From router` → `Settings` → `Config` → `Input` → `Is repo?` → `Projects` → `GitHub: Check repo` → `Check` → `Allowed?` → `Create project` → `Routines` → `Routine missing?` → `Reserve routine` → `Prepare labels` → `GitHub: Create label` → `Prepare issue` → `GitHub: Create issue` → `Build message` → `Telegram: Done`.

| Input (`Input`) | Behaviour |
|---|---|
| `/connect owner/repo` | connects the repo |
| `/connect <address>` or `connect <address>` | the same; `https://github.com/owner/repo` (also with `.git` or a path after it) becomes `owner/repo` |
| `/connect` without a repo, or only a name without an owner | `Telegram: Help` |

- `Check` rejects (`Rejected?` → `Telegram: Rejected`) when GitHub does not know the repo or the token does not see it, when it is archived, when issues are turned off, or when it is already in `codebot_projects`. Then nothing is created.
- **Project data without a language model and without asking:** `key` and `name` come from the repo name (a key that is taken gets `-2`, `-3`, …), `description` from the repo's description on GitHub, `status`, `group`, `priority` and `quiet_days` from `DEFAULTS` in `Config` (Active, Private, Medium, 7). `repo` is GitHub's spelling, even after a rename. `next_step` points to the setup issue.
- **Worker:** n8n does not create a routine and does not generate a token; both only work with the login of the claude.ai account (`SETUP.md`, step 7). If `codebot_routines` has no row for the repo yet, `Reserve routine` enters one: `key`, `repo`, `fire_url` and `token` empty, `active = false`. An existing row stays unchanged (`Routine exists?`).
- `Prepare labels` → `GitHub: Create label`: creates `ready-for-agent` (`READY_LABEL`). Already there → HTTP 422, which is skipped.
- **The “Setup” issue** (`ISSUE_TITLE`) carries no label, so no worker touches it. `Prepare issue` builds it as a checklist:

| Section | Tasks |
|---|---|
| Worker (Claude Code Remote) | create the routine `codebot-<repo-name>` on the web (name, prompt, one repository, no connectors, trigger API); only if the repo is missing from the repository selection: install the Claude GitHub App and select it afterwards; generate an API token; enter `fire_url`, `token` and `active = true` in `codebot_routines`. Below that, collapsible, is the routine's prompt to copy, with `owner/name` filled in. |
| In the repo | check or create `CLAUDE.md` |
| Wrapping up | check the project data in `codebot_projects`, go through the open issues, test with `/work <key>`, close the issue |

  The section “Worker” is left out when `codebot_routines` already has an active row with `fire_url` and `token` for the repo. Whatever did not work (the row in `codebot_projects`, the label) appears as an additional task in the issue. Tokens are never in the issue.
- Text and prompt come from `ISSUE_TEMPLATE` and `WORKER_PROMPT` in `Config`.
- `Telegram: Done`: the only message. It names the repo, the state of `codebot_projects`, `codebot_routines` and the label, the link to the issue and, as long as the worker is missing, the link “Create the Claude Code routine here” (https://claude.ai/code/routines).
- `Create project` and `Reserve routine` run with `continueRegularOutput`, the GitHub nodes with `neverError`: an error appears in the message, the chain carries on.
- Saving successful executions is turned off (`saveDataSuccessExecution: none`), because `Routines` reads the workers' tokens.
- n8n cannot check with the GitHub token whether the Claude GitHub App is installed on the repo. That is why this task in the issue is tied to whether the repo is in the selection when the routine is created.

## CodeBot - Signal Sweep

`Hourly` → `Settings` → `Config` → `Time window` (weekdays 18–22, weekend 9–21) → `Projects` → `Build GitHub query` → `GitHub` → `Scoring` → `Phrase question` (Gemini) → `Telegram: Question` (prefix `[key]`) → `Last ping`.

- Score: silence against `quiet_days` (default 7, “Someday” 30), waiting time above 5 days, deadline, PRs without movement; times the priority factor, times a random 0.8–1.2. Threshold `THRESHOLD: 3`.
- Brakes: at most one follow-up question per 18 h, half the quiet days per project, no ping when there is a block in the next 5 days. Skipped: Done, Paused.

## CodeBot - Dev-Orchestrator

`Daily at 7:00` → `Settings` → `Config` → `Select calendars` → `Calendar: Events` → `Projects` → `Build GitHub query` → `GitHub` → `Plan` → three branches.

| Branch | Content | Next |
|---|---|---|
| `Events only` | deadlines with advance warning | `Calendar: Create event` → `Summary` → `Telegram: Info` |
| `Block only` | earliest future planning session per project, read from the calendar | `Next block` (`codebot_projects.next_block`) |
| `CCR only` | tickets with the label `ready-for-agent` (`CCR_LABEL`) | `Start Claude Routine` (`source: 'dev-orchestrator'`) |

- The orchestrator does not schedule planning sessions; CodeBot - Planning does that after confirmation. The orchestrator only reads them (`codebot-key: codebot-plan:<owner/repo>`) and writes the next one to `next_block`.
- Inactive projects (Paused, Done, Someday) are skipped.
- The orchestrator does not schedule work blocks for individual issues. Implementation runs through the workers.
- The orchestrator starts tickets with `ready-for-agent` without asking: only without an open PR (see /work) and without open predecessors, at most `MAX_CCR_PER_RUN` (3) per run, by score (priority, near deadline). CodeBot - Start Claude Routine prevents the double start (168 h).
- The orchestrator ignores issues without `ready-for-agent`.
- Events are recognised again through `codebot-key: …` in the last line of the description.
- Calendar: the orchestrator reads and writes only `CALENDAR_ID` (`calendar_id` in `codebot_settings`). The deadlines and the planning sessions are there.

## CodeBot - Planning

Proposes planning sessions and enters them in the calendar after confirmation. The only place where planning sessions are created.

`Daily at 8:00` or `From router` → `Input` → `Settings` → `Config` → `Calendar: List` → `Select calendars` → `Calendar: Events` → `Calendar: Sessions` → `Projects` → `Build GitHub query` → `GitHub` → `Plan` → two branches:

| Branch | Content | Next |
|---|---|---|
| `Telegram only` | proposals, notes, replies to buttons | `Telegram: Send` |
| `Event only` | the confirmed event | `Calendar: Create event` → `Report event` → `Telegram: Send` |

| Input (`Input`) | Behaviour |
|---|---|
| schedule | proposals for all projects that need planning, except those in the re-proposal pause |
| `/plan` | the same without the re-proposal pause; if there is nothing, “No project needs a planning session right now” arrives |
| button `s\|e\|<key>\|<start>` | schedules the event; if it is no longer free, another proposal arrives |
| button `s\|a\|…` | replaces the proposal in the same message with another random slot |
| button `s\|x\|…` | skips; the daily run proposes nothing for `SKIP_DAYS` (7) |

- A project **needs planning** when it has a status from `STATUS` (Active, Waiting) and a valid repo, and has no open ticket with `READY_LABEL`. If the calendar already has a future planning session for the repo (`codebot-key: codebot-plan:<owner/repo>`), there is no proposal.
- **Time windows**: `PLANNING_TIMES` in `Config` defines any number of windows `[from, to]` per weekday (`mon` … `sun`). Possible start times lie on the grid `GRID_MINUTES` (30), the session (`PLANNING_MINUTES`, 60) lies entirely within the window, at the earliest `LEAD_HOURS` (2) from now, at most `HORIZON_DAYS` (14) ahead. Busy times from all calendars of the Google account are dropped, as are days that already have a planning session. A slot is picked at random from the rest.
- **One proposal per project** as a message of its own, starting with `[key]`, with the buttons Schedule, Another slot, Skip. Proposals of one run fall on different days. After the tap, the message shows the result and the buttons disappear.
- **Re-proposal pause**: the daily run proposes for the same project again after `REPROPOSE_DAYS` (3) at the earliest. The state is in the workflow's static data (`pause`), so it does not apply to manual test runs.
- **Calendars**: `Calendar: List` fetches the calendar list of the Google account (`calendarList`), `Select calendars` turns it into one item per calendar without those in `IGNORE_CALENDARS` (ID or name), `Calendar: Events` reads the events within the horizon per calendar. Both run through the HTTP node with the Google Calendar credential directly against the calendar API. Events marked as free do not count as busy. Your own calendar (`CALENDAR_ID`) must be readable; if another one is not readable or the list cannot be fetched, a note says so. Events are only entered in `CALENDAR_ID`.
- **Sessions already scheduled**: `Calendar: Sessions` (runs once, `executeOnce`) reads your own calendar (`CALENDAR_ID`) `SESSION_LOOKAHEAD_DAYS` (90) ahead, that is, further than the horizon of the proposals. That way a session that was moved further out counts too. It is recognised by the `codebot-key` in the description, even when Google returns the description as HTML after an edit. An event without a `codebot-key`, for example one created by hand, does not count as a planning session. If the calendar is not readable here, the same message arrives as for `Calendar: Events`, and no proposal.
- `Build GitHub query` asks per repo for the number of open tickets with `READY_LABEL` (aliases `r0`, `r1`, …), without the search and its limit of 100 results.
- The event is called “🧭 Planning: <name>”, the description names the repo.
- Telegram runs through the HTTP node against `api.telegram.org` with the token from `codebot_settings` (`neverError`), as plain text without `parse_mode`.
- `Calendar: List`, `Calendar: Events`, `Calendar: Sessions`, `GitHub` and `Calendar: Create event` run with `continueRegularOutput`: an error arrives as a message in Telegram. If GitHub returns nothing for a repo, a note names the key.

## CodeBot - Setup (one-time)

`Start manually` → `Table codebot_projects` → `Table codebot_routines` → `Table codebot_settings` → `Settings` → `Missing settings` → `Add settings rows`.

Creates the three Data Tables with their columns; existing ones stay unchanged (`createIfNotExists`). Then it adds the rows that `codebot_settings` needs (`telegram_bot_token`, `telegram_chat_id`, `calendar_id`, `timezone` with empty values, `ready_label` with `ready-for-agent`). `Missing settings` leaves out keys that already exist, so values you entered are never overwritten. The empty values are filled in by hand; a workflow that meets an empty value stops with `… is missing in codebot_settings`. It is only needed for a new installation and can be deleted in n8n afterwards.

## Template notation

For `ISSUE_TEMPLATE` and `WORKER_PROMPT` in the `Config` node of CodeBot - Connect Repo. If you change `WORKER_PROMPT`, existing routines need the new prompt too.

| Notation | Meaning |
|---|---|
| `{{NAME}}` | is replaced by a value |
| `{{#NAME}}` … `{{/NAME}}` | the block stays only if `NAME` applies |
| `{{^NAME}}` … `{{/NAME}}` | the block stays only if `NAME` does not apply |

The lines with `{{#…}}`, `{{^…}}` and `{{/…}}` stand alone and disappear together with their line break. Blocks may be nested, but not the same name twice. An unknown name stays in the text literally; that way a typo shows up in the finished issue.

`WORKER_PROMPT` knows only `{{REPO}}` (`owner/name`). `ISSUE_TEMPLATE` knows:

| Placeholder | Value |
|---|---|
| `{{REPO}}` | `owner/name` |
| `{{KEY}}` | key of the project in `codebot_projects` |
| `{{STATUS}}`, `{{GROUP}}`, `{{PRIORITY}}` | values of the new row in `codebot_projects` |
| `{{ROUTINE}}` | suggested name of the routine, `codebot-<repo-name>` |
| `{{DATE}}` | today's date, `YYYY-MM-DD` |
| `{{READY_LABEL}}` | the ticket label from `Config` |
| `{{WORKER_PROMPT}}` | `WORKER_PROMPT` with the repo filled in |

| Switch | Applies when |
|---|---|
| `PROJECT_OK` | the row in `codebot_projects` was written |
| `LABELS_OK` | the label is in the repo |
| `WORKER_MISSING` | `codebot_routines` does not yet have an active worker with routine and token |
| `WORKER_READY` | the opposite |
| `ROUTINE_RESERVED` | the workflow has just reserved the row in `codebot_routines` |
| `ROUTINE_UNCHANGED` | an incomplete row already existed and stayed unchanged |
| `ROUTINE_ROW_EXISTS` | there is a row in `codebot_routines`, reserved or already present |

Tokens do not belong in the templates or in the issue.

## Known limits

- GitHub queries fetch at most 100 open issues and PRs across all project repos together, without paging. Beyond that, some are missing.
- The watchdog checks exactly once, 90 minutes after the start. If a session takes longer, it reports “no PR”.
- A worker's token and the bot token are stored in plain text in the Data Tables and in the execution data of the workflows that read them. That is why saving successful executions should be turned off for CodeBot - /work, CodeBot - Planning, CodeBot - Connect Repo and CodeBot - Start Claude Routine.
- `/work` does not set `in-progress` at the start.
- No tickets are created through Telegram. A running session of a routine cannot be answered through the API; every call to `/fire` starts a new session. A conversation with follow-up questions is only possible in Claude's own interface.
- `/connect` commits nothing in the repo: the worker and the `CLAUDE.md` remain manual work, and the “Setup” issue in the repo lists them.
- `/connect` cannot check whether the Claude GitHub App is installed on the repo. That only shows when the routine is created.
- An umbrella issue with the label `ready-for-agent` that has no sub-issues yet looks like a ticket to the system. So give the label only to the small tickets.
- The Dev-Orchestrator starts up to 3 tickets every morning without asking. If many tickets are released, the workers run for days; the only brakes are dependencies or removing the label.
- The system recognises open PRs by the link (`Closes #N`) or by the branch `claude/issue-<N>-…`, at most the 50 newest open PRs per repo. A PR with neither is not recognised; then only the 168-hour lock protects.
