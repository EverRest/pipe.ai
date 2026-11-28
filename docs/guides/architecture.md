# Architecture

## Components

```mermaid
flowchart LR
    subgraph Slack
        W["#pipe-work<br/>tasks and threads"]
        A["#pipe-agents<br/>agent cards"]
        S["#pipe-status<br/>session status"]
    end
    subgraph Laptop["Owner laptop"]
        AD["Adapter (pipe run)"]
        CORE["Core: pure rules"]
        TP["Transport port<br/>SlackTransport"]
        RP["Runtime port<br/>claude, exec, http"]
        HOOK["pipe status-hook"]
    end
    GL["GitLab<br/>branches, MRs, schedules"]
    TB["Trigger bot (CI job)"]

    TP <--> W
    TP <--> A
    TP --> S
    HOOK --> S
    AD --> CORE
    AD --> TP
    AD --> RP
    RP -- "git push (write step)" --> GL
    GL --> TB
    TB --> W
```

## Ports

[src/pipe/ports.py](../../src/pipe/ports.py) defines the ports. The core imports no transport module and no runtime module.

| Port | Implementation | Notes |
|---|---|---|
| `Transport` | `transport_slack.py` | Socket Mode events come from `transport_slack_events.py`. |
| `RuntimePort` | `runtime_claude.py` | Runs `claude -p`. A `write` step runs in a git worktree. |
| `RuntimePort` | `runtime_exec.py` | Runs a declared command. `read` only. |
| `RuntimePort` | `runtime_http.py` | Sends a POST to a declared URL. `read` only. |

The capability ID selects the runtime. `exec:...` and `http:...` go to their runtimes. All other runs go to `claude`.

## Trust model

```mermaid
flowchart TD
    M["Slack message"] --> B{"Sender is a bot?"}
    B -- "no" --> H["Person: a mention starts a chat or a plan"]
    B -- "yes" --> C{"Valid card in #pipe-agents<br/>and pipe.task.v1 metadata?"}
    C -- "no" --> I["Ignore"]
    C -- "yes" --> R{"Step access"}
    R -- "read" --> RO["Run an exposed capability<br/>Owner tools only for a clean owner thread"]
    R -- "write" --> G{"Owner thread, or allowlist rule?"}
    G -- "yes" --> X["Run in a worktree"]
    G -- "no" --> BTN["Owner clicks Accept or Reject"]
```

The rules are in [Security](security.md).

## Design sources

- [Design brief](../design-brief.md)
- [Constitution](../../.specify/memory/constitution.md)
