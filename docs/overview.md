# Overview

The whole system in one diagram: who triggers what, and what each workflow does. Details per workflow are in `workflows.md`.

| Colour | Meaning |
|---|---|
| green | workflow or data table in this repo |
| grey, dashed | not built yet |
| blue | services outside n8n, and steps you do by hand |

Dashed arrows are manual steps or side paths. Solid arrows run on their own.

```mermaid
flowchart TD
  classDef done fill:#d4edda,stroke:#2e7d32,color:#111
  classDef open fill:#f4f4f4,stroke:#888,color:#555,stroke-dasharray:5 5
  classDef ext fill:#e7f0fb,stroke:#3b6ea5,color:#111

  TG["Telegram<br/>the only channel"]:::ext
  CRON["Schedule in n8n"]:::done
  YOU["You create tickets<br/>whichever way suits you"]:::ext

  subgraph N8N["n8n workflows"]
    ROUTER["CodeBot - Telegram Router<br/>the only Telegram trigger"]:::done
    WORK["CodeBot - /work<br/>project list, oldest startable ticket,<br/>yes or no"]:::done
    CONNECT["CodeBot - Connect Repo<br/>/connect: adds an existing repo,<br/>label, “Setup” issue"]:::done
    CHAT["CodeBot - Chat<br/>questions and status updates"]:::done
    START["CodeBot - Start Claude Routine<br/>fires the worker, watchdog after 90 min"]:::done
    ORCH["CodeBot - Dev-Orchestrator<br/>daily at 7:00, at most 3 tickets,<br/>deadlines"]:::done
    PLAN["CodeBot - Planning<br/>daily at 8:00 or /plan,<br/>proposes planning sessions"]:::done
    SWEEP["CodeBot - Signal Sweep<br/>asks about quiet projects"]:::done
    SYNC["Sync through the n8n API<br/>instead of manual import"]:::open
    TARGETED["/work with an issue number<br/>start one specific issue"]:::open
  end

  subgraph DATA["n8n Data Tables"]
    PROJ[("codebot_projects<br/>project list")]:::done
    ROUT[("codebot_routines<br/>trigger URL and token per worker")]:::done
    SET[("codebot_settings<br/>bot token, chat ID, calendar ID")]:::done
  end

  subgraph GH["GitHub"]
    REPO["Project repo"]:::ext
    ISSUES["Issues<br/>tickets carry ready-for-agent"]:::ext
    SETUP["“Setup” issue<br/>by hand: create the routine, generate a token,<br/>fill in codebot_routines; prompt ready to copy"]:::ext
    PR["Pull request<br/>you review and merge"]:::ext
  end

  CCR["Claude Code Remote<br/>one worker per project"]:::ext
  CAL["Google Calendar<br/>planning sessions, deadlines"]:::ext

  TG -->|"every message"| ROUTER
  ROUTER -->|"/work, buttons"| WORK
  ROUTER -->|"/plan, buttons"| PLAN
  ROUTER -->|"/connect"| CONNECT
  ROUTER -->|"everything else"| CHAT

  WORK -->|"reads projects"| PROJ
  WORK -->|"finds a ticket"| ISSUES
  WORK -->|"after yes"| START
  TARGETED -.-> WORK

  CONNECT -->|"new row"| PROJ
  CONNECT -->|"reserves the worker"| ROUT
  CONNECT -->|"label"| ISSUES
  CONNECT -->|"creates"| SETUP

  SETUP -.->|"you create the routine"| CCR
  SETUP -.->|"you enter ID and token"| ROUT

  CHAT -->|"reads and updates"| PROJ

  CRON --> ORCH
  CRON --> SWEEP
  CRON --> PLAN
  PLAN -->|"reads projects"| PROJ
  PLAN -->|"needs planning?"| ISSUES
  PLAN -->|"planning session after confirmation"| CAL
  ORCH -->|"tickets, without asking"| START
  ORCH -->|"deadlines"| CAL
  ORCH -->|"reads"| ISSUES
  ORCH -->|"reads, next planning session"| PROJ
  SWEEP -->|"question"| TG
  SWEEP -->|"reads"| PROJ

  START -->|"worker for the repo"| ROUT
  START -->|"POST /fire"| CCR
  START -->|"start and result"| TG
  CCR -->|"branch and PR"| PR
  PR -->|"merge closes the ticket,<br/>its successors become startable"| ISSUES
  START -.->|"watchdog checks"| PR

  YOU -->|"tickets with the label"| ISSUES
  REPO --- ISSUES
  SET -.->|"read by every workflow"| N8N
  SYNC -.-> N8N
```

## The path of a ticket

1. `/connect` in Telegram adds an existing repo as a project: a row in `codebot_projects`, the label `ready-for-agent`, a reserved worker in `codebot_routines`, and a “Setup” issue in the repo.
2. You work through the “Setup” issue once: create the routine on the web (the prompt is in the issue), generate a token, and enter both in `codebot_routines`. Until then, `/work` replies that no worker is set up.
3. CodeBot - Planning proposes a planning session as soon as the project runs out of released tickets. You create the tickets and release them with the label `ready-for-agent` (see `../README.md`).
4. `/work <key>` or the Dev-Orchestrator hands the oldest startable ticket to CodeBot - Start Claude Routine.
5. The project's worker implements it and opens a PR. 90 minutes after the start, the watchdog reports the result in Telegram.
6. You review and merge. That closes the ticket, and its successors become startable.
