# Setup

Everything needed to get Code-Bot running on your own n8n instance. What the workflows do in detail is in `docs/workflows.md`.

## Prerequisites

| What | What for | Note |
|---|---|---|
| n8n instance with its own domain and HTTPS | all automations | Telegram must reach n8n from outside. The version must support **Data Tables**. |
| Claude Pro or Max | Claude Code Remote (routines) | Every run counts against the subscription quota. |
| GitHub account | repos, issues, PRs | one repo per project |
| Telegram account | channel to the system | a bot of your own |
| Google account | calendar, Gemini | Gemini API key from Google AI Studio |

## Steps

The order matters: tables and credentials first, the Telegram Router last.

### 1. Telegram bot

1. In Telegram at `@BotFather`: `/newbot`, choose a name, note the **bot token**.
2. Send the new bot a message.
3. Find out your own **chat ID**: open `https://api.telegram.org/bot<TOKEN>/getUpdates` in the browser and note the value `message.chat.id`. It goes into `codebot_settings` in step 5.

> **The chat ID is your own ID, not the bot's.** Two numbers are easy to mistake for it, and both belong to the bot:
>
> | Number | What it is |
> |---|---|
> | the one in the address of Telegram Web while the bot's chat is open (`web.telegram.org/a/#…`) | the bot's ID |
> | the one before the colon in the bot token | the bot's ID |
> | `message.chat.id` in `getUpdates` | **your chat ID** |
>
> With the bot's ID in `codebot_settings`, the Telegram trigger still fires for every message, but the router discards it and nothing replies.

`getUpdates` only answers while the bot has no webhook, that is, before the Telegram Router is active. Later, deactivate the router for a moment, or read `message.chat.id` in the output of `Telegram Trigger` in one of the router's executions.

The system serves exactly this one chat ID. All other senders are discarded.

### 2. GitHub

1. Create a **token for n8n** (Settings → Developer settings → Personal access tokens). Permissions: read repos, read and create issues, read pull requests, create labels. For a classic token this is the scope `repo`.
2. Install the **Claude GitHub App**: connect GitHub at claude.ai/code and grant the app access to the project repos. Without the app a worker cannot push. Repeat for every new repo, or grant the app access to all repos of the account.

Nothing is configured in the project repos themselves: no GitHub Actions, no webhooks.

### 3. Google

1. **Gemini:** create an API key in Google AI Studio.
2. **Calendar:** create a “Google Calendar OAuth2” credential in n8n. n8n guides you through the steps (OAuth client in the Google Cloud Console, redirect URL of your own n8n domain). Note the **calendar ID** of the calendar in which events should be created (Google Calendar settings, under “Integrate calendar”). It goes into `codebot_settings` in step 5.

### 4. Credentials in n8n

The names are up to you, but the exports refer to these:

| Name | Type | Content |
|---|---|---|
| Telegram CodeBot account | Telegram API | bot token |
| Header Auth account | Header Auth | name `Authorization`, value `Bearer <GitHub token>` |
| GitHub account | GitHub API | the same GitHub token |
| Google Gemini(PaLM) Api account | Google Gemini | API key |
| Google Calendar account 2 | Google Calendar OAuth2 | see step 3 |

The exports carry placeholders instead of credential IDs (`TELEGRAM_CREDENTIAL_ID`, `GITHUB_HEADER_AUTH_CREDENTIAL_ID`, `GITHUB_CREDENTIAL_ID`, `GEMINI_CREDENTIAL_ID`, `GOOGLE_CALENDAR_CREDENTIAL_ID`). After the import, select your own credential in every node that shows a warning.

### 5. Data Tables

Create three tables in the same n8n project as the workflows (menu “Data tables”). Names and columns exactly as under “Data tables” below:

| Table | Content |
|---|---|
| `codebot_projects` | project list, 15 columns |
| `codebot_routines` | trigger URL and token per worker |
| `codebot_settings` | key-value pairs |

Then fill `codebot_settings`:

| `key` | `value` |
|---|---|
| `telegram_bot_token` | the bot token from step 1 |
| `telegram_chat_id` | **your** chat ID from step 1 (`message.chat.id`), not the bot's ID; the only chat the system serves and writes to |
| `calendar_id` | the calendar ID from step 3; deadlines and planning sessions are created there |
| `timezone` | your IANA time zone, e.g. `Europe/Berlin`; all dates, time windows and calendar events use it |
| `ready_label` | optional: the label that releases a ticket for a worker. Without this row it is `ready-for-agent` |

These rows are everything that is specific to you. The workflows read them at run time, so nothing has to be edited in the workflow JSON.

It is quicker with the workflow `CodeBot - Setup (one-time)`: import it and run it once. It creates the three tables with all columns and adds the rows above to `codebot_settings`, with empty values (`ready_label` gets `ready-for-agent`). You then only fill in the four values under “Data tables”. Running it again changes nothing that already exists. After that the workflow can be deleted in n8n.

The tables live in the database of your own n8n instance. The workers' tokens are there too; no external service is involved.

### 6. Import the workflows

In n8n, create a new workflow per file and load it through “Import from file”. Order:

1. `CodeBot - Start Claude Routine`
2. `CodeBot - _work (Telegram → Claude)`, `CodeBot - Chat`, `CodeBot - Connect Repo`
3. `CodeBot - Dev-Orchestrator`, `CodeBot - Planning`, `CodeBot - Signal Sweep`
4. `CodeBot - Telegram Router`

After the import, adjust in every workflow:

| What | Where |
|---|---|
| Select credentials | every node with a warning symbol |
| Calendars to ignore | Planning: `Config` (`IGNORE_CALENDARS`). Planning reads busy times from all calendars of the Google account; list the exceptions here. |
| Times for planning sessions | Planning: `Config` (`PLANNING_TIMES`): per weekday, the time windows in which a planning session may take place |
| Select the target workflows | Router: the four Execute Workflow nodes; /work and Dev-Orchestrator: `Start Claude Routine`. The exports contain no workflow IDs, because every workflow gets a new one on import. |
| Time windows and thresholds | in the `Config` node of each workflow |

**Check the prompts before you activate anything.** Two nodes send a prompt to Gemini, and both ship with a generic text:

| Workflow | Node | Field |
|---|---|---|
| CodeBot - Chat | `CodeBot agent` | Options → System Message |
| CodeBot - Signal Sweep | `Phrase question` | Prompt |

Read both and adapt the first sentence (who you are, what kind of projects you run, when you work on them) and the reply language (“Reply in English”, “in English”). Leave the expressions in `{{ … }}` and, in the Chat prompt, the rules about the `<update>` block as they are: the workflows parse that block to update `codebot_projects`.

The workers' prompt is a separate text. Read it too before you create the first routine (step 7).

Activate:

- `CodeBot - Dev-Orchestrator`, `CodeBot - Planning`, `CodeBot - Signal Sweep`. Their schedules (7:00, 8:00, hourly) fire in the time zone of the n8n instance (`GENERIC_TIMEZONE`), not in `timezone` from `codebot_settings`; set both to the same zone.
- the called workflows (`/work`, `Chat`, `Connect Repo`, `Planning`, `Start Claude Routine`) must be published in newer n8n versions so that they can be called
- **last** `CodeBot - Telegram Router`. It is the only workflow with a Telegram trigger. A bot has exactly one webhook; a second active trigger on the same bot takes the messages away from the router.

For `/work`, `Connect Repo`, `Planning` and `Start Claude Routine`, turn off saving successful executions in the workflow settings: tokens pass through there.

### 7. Create a worker (per project)

A worker is a routine in Claude Code Remote with exactly one repo: one routine per project, no connectors.

1. Create the routine: name `codebot-<repo-name>`, one repository, the prompt, no connectors, at https://claude.ai/code/routines. After `/connect`, the prompt is in the “Setup” issue of the repo, ready to copy with the repo filled in; its source is `WORKER_PROMPT` in the `Config` node of CodeBot - Connect Repo (replace `{{REPO}}` with `owner/name`).
2. On the web: open the routine → Edit → Add another trigger → **API** → Generate token. The token is shown only once.
3. In n8n, the row in `codebot_routines` (`/connect` reserves it, otherwise create it): `key`, `repo` (`owner/name`), `fire_url` (the ID of the routine, `trig_…`), `token` (without “Bearer”), `active = true`.
4. If the project's tests need tools such as PHP, Composer or Node, a setup script belongs in the routine's environment.
5. Test: `/work <key>`, “No” the first time, then “Yes”.

The Claude GitHub App must be installed on the repo, otherwise the worker cannot push. Leave “Allow unrestricted branch pushes” off. If a repo is renamed on GitHub, update the routine's prompt and repository, otherwise the worker aborts.

The API trigger can only be created on the web, not from n8n and not through the API. After `/connect`, these steps including the prompt are in the “Setup” issue of the repo.

### 8. First project

Code-Bot does not create repos. You add an existing repo with `/connect owner/repo` or `/connect <address of the repo>`. That creates:

- the row in `codebot_projects` with default values
- the label `ready-for-agent` in the repo
- a reserved row in `codebot_routines` (`active = false`)
- a “Setup” issue in the repo: setting up the worker as a checklist, with the routine's prompt to copy

Nothing is committed in the repo in the process. Then work through the “Setup” issue (that is step 7 for this repo). What a ticket needs is in the `README.md`.

### 9. Finishing up

- At `@BotFather`, `/setcommands`:
  ```
  work - Let Claude work on a project
  plan - Propose planning sessions
  connect - Add an existing repo as a project
  ```
- Turn on branch protection for `main` in the project repos. The workers push only to `claude/…` branches and never merge.

## Checking that everything works

| Test | Expected |
|---|---|
| any message to the bot | a reply from the chat agent, the projects are right |
| `/work` | the project list as buttons |
| `/work <key>` without a released ticket | “No tickets with the label ready-for-agent” |
| `/work <key>` with a ticket, “Yes” | “Claude started” with a session link, after 90 minutes the PR message |
| `/work` for a project whose row in `codebot_routines` is missing or still reserved (`active = false`) | “No worker set up for …” |
| `/connect` without a repo | the help text |
| `/connect owner/repo` | exactly one message “Connected” with a link to the “Setup” issue; a row in `codebot_projects`, a row in `codebot_routines` with `active = false`, the label `ready-for-agent` in the repo, no commit |
| `/connect` for a repo that is already in `codebot_projects` | “Not connected: … It is already in codebot_projects as [key]” |
| `/plan` | one proposal with three buttons per project that needs planning, otherwise “No project needs a planning session right now” |
| button “Schedule” under a proposal | an event “🧭 Planning: …” in the calendar, the message shows “scheduled” |
| run the Dev-Orchestrator by hand | deadlines in the calendar |

## Data tables

Three tables in the n8n project of the CodeBot workflows. The setup workflow creates them; this is the reference for creating or checking them by hand. They live in the n8n database, not in Git, and their values are not encrypted: anyone who gets into the n8n UI can read them. The workflows address the tables by name, so do not rename them.

### `codebot_projects`

The project list. It contains no secrets, because CodeBot - Chat passes all fields to the language model.

| Column | Type | Content | Written by |
|---|---|---|---|
| `key` | string | key, unique, e.g. `my-project`; `[key]` in Telegram, `/work <key>` | Connect Repo |
| `name` | string | | Connect Repo |
| `status` | string | Active, Waiting, Paused, Someday, Done | Chat, Connect Repo |
| `group` | string | Private, Club, Family, Friends | Connect Repo |
| `priority` | string | High, Medium, Low | Connect Repo |
| `repo` | string | `owner/name`, required | Connect Repo |
| `quiet_days` | number | after how many days silence gets noticed (7, for “Someday” 30) | Connect Repo |
| `deadline` | string | `YYYY-MM-DD` or empty | Connect Repo |
| `waiting_for` | string | | Chat |
| `waiting_since` | string | `YYYY-MM-DD` or empty | Chat |
| `next_step` | string | | Chat, Connect Repo |
| `description` | string | context for the AI | Connect Repo |
| `last_checkin` | string | `YYYY-MM-DD` | Chat, Connect Repo |
| `last_ping` | string | ISO timestamp | Signal Sweep |
| `next_block` | string | ISO timestamp of the next planning session | Dev-Orchestrator (reads it from the calendar) |

Date values are deliberately strings in ISO format: they can be entered by hand, and the Code nodes read them with `DateTime.fromISO`.

The writing workflows check the allowed values of `status`, `group`, `priority`; the table itself does not. When entering by hand, write them exactly like this.

### `codebot_routines`

Access to the CCR workers. CodeBot - Start Claude Routine reads it. CodeBot - Connect Repo reserves a row for a new project (`key`, `repo`, `active = false`, the rest empty); you enter `fire_url` and `token` by hand and set `active` to `true`.

| Column | Type | Content |
|---|---|---|
| `key` | string | project, for orientation |
| `repo` | string | `owner/name`; the worker is found through it |
| `fire_url` | string | ID of the routine (`trig_…`); the workflow builds `https://api.anthropic.com/v1/claude_code/routines/trig_…/fire` from it. The whole address works too. |
| `token` | string | token of the routine (`sk-ant-oat01-…`), without “Bearer” |
| `active` | boolean | `false` turns the worker off |

### `codebot_settings`

Key-value pairs.

| `key` | `value` | Read by |
|---|---|---|
| `telegram_bot_token` | token of the bot (`123456:ABC…`) | CodeBot - /work, CodeBot - Planning (messages with buttons) |
| `telegram_chat_id` | your Telegram chat ID (`message.chat.id`, see step 1; not the bot's ID); the only chat that is served, and the one all messages go to | every workflow except CodeBot - Setup (one-time) |
| `calendar_id` | ID of the calendar in which events are created, in the form of an email address (`…@group.calendar.google.com`, or the address of the Google account for the main calendar) | CodeBot - Dev-Orchestrator, CodeBot - Planning |
| `timezone` | IANA time zone, e.g. `Europe/Berlin` | CodeBot - Chat, Connect Repo, Dev-Orchestrator, Planning, Signal Sweep |
| `ready_label` | optional; the label that releases a ticket for a worker, default `ready-for-agent` | CodeBot - /work, Connect Repo, Dev-Orchestrator, Planning |

The label is `ready-for-agent` in the rest of these docs. If you change `ready_label` later, repos that are already connected still carry the old label.

A workflow that needs a missing value stops with `<key> is missing in codebot_settings`.

## Troubleshooting

| Problem | Cause / fix |
|---|---|
| `Credentials not found` | no credential selected in the node |
| GitHub `rate limit exceeded` | node without a token (60/h instead of 5000/h) |
| GraphQL returns an empty list | token without the right permissions, or a wrong search term |
| Webhook `404` | workflow inactive, or `/webhook-test/` instead of `/webhook/` |
| Telegram reacts in only one workflow | two triggers on the same bot |
| `/work` without any reaction, but the chat replies | in the Telegram Router the node `→ CodeBot - /work` is deactivated, or the target workflow is not published |
| `/work`: “No project … in codebot_projects” | the key or repo is not in the table |
| `/work`: “Repo … not found” | the repo is misspelt in `codebot_projects`, or the GitHub token has no access |
| `/work`: “No tickets with the label ready-for-agent” | there is no released ticket in the repo, or the label is missing in the repo |
| `/work`: “already have an open PR” | every released ticket has an open PR (drafts too); review and merge, or close the PR |
| `/connect` without any reaction | in the Telegram Router no workflow is selected in the node `→ CodeBot - Connect Repo`, or CodeBot - Connect Repo is not published |
| `/connect` ends up in the chat | the router is out of date |
| `/connect`: “GitHub does not know the repo” | wrong spelling, or the GitHub token does not see the repo (foreign org, SSO not authorised) |
| `/connect`: “The “Setup” issue could not be created” | GitHub token without write permission for issues in the repo; the manual steps are then in step 7 above |
| `/connect`: “The row in codebot_routines could not be reserved” | the table `codebot_routines` is missing, or a column is named differently than under “Data tables”; create the row by hand |
| `/plan` without any reaction | in the Telegram Router no workflow is selected in the node `→ CodeBot - Planning`, the router is out of date, or CodeBot - Planning is not published |
| `/plan`: proposals arrive, buttons do not react | the prefix `s\|` is missing in the Telegram Router |
| Planning: never a proposal on a particular day | `PLANNING_TIMES` in `Config` of CodeBot - Planning: the window is missing or shorter than `PLANNING_MINUTES` |
| Planning: “your own calendar could not be read” | `calendar_id` in `codebot_settings` is wrong (HTTP 404), or the Google credential has expired (HTTP 401) |
| Planning: proposals fall on times that look busy, or there is never a free slot | a calendar is missing from the calendar list of the Google account, or a calendar with all-day entries blocks the days; enter such calendars in `IGNORE_CALENDARS` |
| Planning: a proposal for a project that already has a planning session | the event has no `codebot-key: codebot-plan:<owner/repo>` in its description (created by hand, line deleted), the repo in it differs from `codebot_projects`, or it lies further ahead than `SESSION_LOOKAHEAD_DAYS` |
| Dev-Orchestrator: `Calendar parameter's value is invalid` | `calendar_id` in `codebot_settings` does not have the form of an email address |
| A workflow fails with `… is missing in codebot_settings` | the row with that key (`telegram_chat_id`, `calendar_id`, `timezone`, `telegram_bot_token`) is missing or empty |
| A workflow fails with `timezone in codebot_settings is not a valid IANA time zone` | write the zone as `Area/City`, e.g. `Europe/Berlin` |
| The daily runs come at the wrong hour | the schedule triggers use the time zone of the n8n instance (`GENERIC_TIMEZONE`), not `timezone` from `codebot_settings` |
| The bot does not react to anything; the router's execution ends at `Where to?` | open the execution and read `reason` in the output of `Route`. Usually `telegram_chat_id` in `codebot_settings` holds the bot's ID instead of yours (see the note in step 1); `reason` names the ID that belongs there. A group has its own negative ID |
| Planning: “GitHub returned no data for …” | the repo is misspelt in `codebot_projects`, or the token has no access; a single missing repo makes the query fail for all |
| `/work`: “are waiting for open predecessors” | all tickets with `ready-for-agent` have open blockers; close the predecessors or remove the dependency |
| Buttons do not arrive | `telegram_bot_token` is missing or wrong in `codebot_settings` |
| Chat, Sweep or Orchestrator without GitHub data | a repo in `codebot_projects` does not exist; the shared query then fails for all |
| `/work`: a project is missing from the list | status Done / Paused / Someday, no repo, or button data above 64 bytes |
| Claude does not start, no message | double-start guard (168 h per issue) without `force` |
| “No worker set up for …” | the row in `codebot_routines` is missing, `repo` differs, `active` is `false`, or `fire_url` / `token` are empty |
| Start fails with `Invalid URL` or `404` | `fire_url` in `codebot_routines` is neither the ID `trig_…` nor the whole address, or the routine was deleted |
| `/fire` returns `401` | token wrong, renewed or revoked |
| Claude aborts immediately | `repo` in `codebot_routines` points to the routine of another repo |
| “No PR” after 90 minutes | the session ran longer, the GitHub App is missing on the repo, or the branch is not named `claude/issue-<N>-…` and the PR does not name the issue |
| CCR session does not reach n8n | domain not allowed in the environment (`x-deny-reason: host_not_allowed`) |
