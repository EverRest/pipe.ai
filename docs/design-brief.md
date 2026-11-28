# pipe.ai — MVP Design Brief

Status: approved in brainstorming, 2026-11-25. Amended 2026-11-26 (capability-agnostic core, decision 15; delegation decisions, decision 16; flexible core: transport port, declared capabilities, late binding by tag, capability schemas, decision 17). Amended 2026-11-26 (second batch, constitution 1.3.0: hop limit by plan source, flow templates, dialog step, plan proposal, gate, `exclude_agents_of`, `on_fail`, `upload_file`, `exec` input schema, `deny_rules` union, decisions 18 to 21).
Input for: GitHub Spec Kit (`/speckit.constitution`, `/speckit.specify`, `/speckit.plan`, `/speckit.tasks`).
Spec model: Sonnet 5.5 (`claude-sonnet-5-5`).
Language: write all specs, plans, and tasks in Simplified Technical English (STE).
Source idea: [raw.md](raw.md). This brief replaces the scope of `raw.md` for the MVP.

## 1. Goal

A team of 3–6 developers. Each developer has their own coding agents (Claude Code).
The agents of different owners must work together in Slack:

- **A. Review handoff.** My agent opens an MR. The agent of a colleague reviews it.
- **B. Status sync.** Agents report who works on what. This replaces the `sync` skill.
- **C. Delegation.** My agent asks the agent of a colleague to do work in the colleague's repo.

Pipelines are written ad hoc in chat. Schedules and events come from GitLab.

The MVP is an experiment. It must answer one question: do agents of different owners do useful work together?

## 2. Constitution (input for `/speckit.constitution`)

1. **No server in the MVP.** Slack is the UI, the message bus, and the task state. GitLab is the change gate and the scheduler. Do not add a database, a web UI, or a hosted service.
2. **The owner controls the agent.** The adapter runs on the owner's laptop. Only the owner decides who may send requests to the agent and which capabilities other people can use.
3. **Discovered is not exposed.** The adapter finds capabilities automatically. A capability that uses the owner's credentials is `owner-only` until the owner exposes it. This includes a capability that the owner declares in the config file.
4. **Every change goes through an MR.** An agent never pushes to `main`. The merge by a human is the approval.
5. **Thread content is untrusted input.** Trust `metadata` only from bots that have an agent card. Trust approvals only from the thread starter or the agent owner.
6. **Runtime-agnostic contract.** The adapter talks to the runtime through one contract. The first runtime is `claude -p`.
7. **Business rules are pure functions.** Router, trust, exposure, plan validation, and claim resolution are tested with unit tests, without Slack and without an LLM. TDD for these rules.
8. **Reuse before build.** Review is a capability with the tag `review`. wiz-review is the first implementation. Copy the wiz-review patterns (tick, launcher, doctor) for the adapter.
9. **Small dependencies.** Python, `slack_bolt`, `pyyaml`. Add nothing else without a reason in the plan.
10. **STE for all written artifacts.** Specs, plans, tasks, and docs use Simplified Technical English: short sentences, one instruction per sentence, active voice, no idioms. Keep code, paths, and identifiers exactly as they are.
11. **Core is runtime- and transport-agnostic.** The core (routing, plan, steps, trust, claim, hop, timeout, catch-up) knows nothing about plugins, skills, MCP, runtime tool names, wiz-review, GitLab, or Slack. It works only with `capability_id` values from agent cards and with transport-neutral identities (`sender_id`, `sender_is_bot`, `card_owner_id`). It handles tags as opaque strings. The standard tag vocabulary is data (`flows/tags.yaml`), not a core constant. Only a runtime adapter turns capability IDs into runtime flags. Only a transport adapter talks to the chat product. Only a replaceable provider reads the state of an external system. Claude Code, Slack, wiz-review, and GitLab are first implementations, not core concepts. An import-boundary test enforces this for every module in `src/pipe/core/`.

## 3. Decision log

| # | Decision | Rejected | Why |
| --- | --- | --- | --- |
| 1 | No coordinator. State lives in Slack message `metadata` | thin coordinator + Postgres; own platform | Fastest path to test the idea. Upgrade triggers are in §10 |
| 2 | Agents run on owner laptops | always-on per owner | Full access to local repos and toolchain. No hosting |
| 3 | Runtime-agnostic contract, first runtime `claude -p` | Agent SDK only | Existing skills, MCP, and commands work at once |
| 4 | Delegation: allowlist auto-accepts, others get a button, result is always an MR | MR only; button for all | Trust for known agents, control for others |
| 5 | No central config repo. Agents announce themselves with agent cards | `pipe-config` repo with `agents.yaml` | Must be dynamic |
| 6 | Pipeline from natural language. Planner shows the plan, human approves with ✅ | strict syntax; no approval | Easy to write. Plan errors are visible before work starts |
| 7 | Status: hook events + on-demand query | daily digest | Digest can be added later with one GitLab schedule |
| 8 | wiz-review stays the review engine. It is the first implementation of a capability with the tag `review`. A step ends when its agent posts `status: done` | rebuild review in pipe; a special "review done" callback in the core | wiz-review already works. The core needs no review-specific code (decision 15) |
| 9 | Capabilities are discovered automatically, published as A2A AgentCard | manual list | Must be dynamic. A2A format keeps external agents possible |
| 10 | Discovered ≠ exposed. Credential-backed tools are `owner-only` by default | publish all | Prevents the confused deputy problem |
| 11 | Python + `slack_bolt` | TypeScript; Go | Same stack as wiz-review |
| 12 | No always-on agents in the MVP | one shared always-on agent | Review has the wiz-review fallback. Any online agent can answer status queries |
| 13 | Metrics are computed from Slack `metadata` | metrics DB | No server rule |
| 14 | Any bot with a `kind: trigger` card can start a pipeline. The owner's allowlist or an accept/reject button gates it. GitLab CI (the `pipe-gitlab` bot) is the first template | ✅ always; HMAC signature from CI; a GitLab-only trigger in the core | Reuses the trust and allowlist rules. A schedule works when nobody is online |
| 15 | The core is capability-agnostic. A plan step names a `capability`. A runtime adapter maps capability IDs to runtime flags. A replaceable provider gives the MR state | Core code that knows plugins, skills, MCP tools, wiz-review, or GitLab | One agent stack must not shape the core. A new runtime, review tool, or trigger needs no core change |
| 16 | Delegation (spec 004). Only a `write` step from another person goes through the gate. A `read` step has no gate. The gate accepts without a click only when the sender bot is in the allowlist AND the thread starter is the owner of the sender or is in the allowlist. The target repo comes from the owner map `runtime.claude.delegate_repos` and an optional opaque `target` on the step. The MR comes from a new branch with git push options. A pending button has no expiry. A runtime `status: delegate` does not start a delegation. A rejected step has no Retry. `write_tools` allows no bare `Bash` | A gate for every step; a check of the sender only; one repo per agent; a repo as a capability on the card; an MR through an API token; button expiry; a delegation started by the runtime; Retry after a reject; `Bash` in the default write tools | An allowlisted agent must not give a stranger a way to a repo (confused deputy). Repo names and paths stay out of the card. No new secret. A reject is a final decision of the owner |
| 17 | The core is runtime- and transport-agnostic, and flexible. (a) A `Transport` port holds the chat operations; Slack (`transport_slack_*`) is the first adapter; trust rules use `sender_id`, `sender_is_bot`, `card_owner_id`. (b) The owner can declare capabilities in config (`exec`, `http`); each kind is a runtime adapter; a declared capability is `owner-only` until exposed. (c) A plan step can name `capability: tag:<tag>` with `agent: any`; the lowest claim `ts` wins; no claimer gives `failed`, `no_claimer`. (d) A capability can carry an optional `input_schema` and `output_schema`; the core validates the payload and the result with a small stdlib subset validator. `ToolPolicy` moves into the `claude` adapter | Slack names in the core; Claude-only capabilities; a planner that must name one agent; a `jsonschema` dependency; Discord and Telegram operations in the port now | One chat product or one agent stack must not shape the core. A new tool needs config only. The planner needs no knowledge of who is online. No new dependency |
| 18 | The `hop` limit depends on the plan source. A free plan has 3. A plan whose source is a verified template has 5. `pipeline.source` is `template:<name>@<hash>` or `free`. It is only a claim: every adapter recomputes it from its own template files (same name, same hash of the parsed file, matching step shape). Else `free`. A stale or different copy fails closed with "plan source not verified". Constitution 1.3.0 | A fixed limit of 3 for all; a fixed limit of 5 for all; trust the claim of the plan; a hash allowlist in the owner config (later, if wanted) | The two main flows have 4 agent steps. A plan must not raise its own limit. The check needs no new config |
| 19 | Flow templates are data. Files `flows/<name>.yaml` (git) and `~/.pipe/flows/<name>.yaml` (owner override). The standard tag vocabulary is the data file `flows/tags.yaml`. A `flow:<name>` word is a pipeline request, also with one agent. The planner may return only a template name and the core expands it. Saving pipelines from chat stays forbidden (spec 003 FR-021 relaxed for files only) | A tag list in the core; the LLM writes template steps; save a pipeline from chat | The core stays free of tag names. A template is reviewed in git. The LLM needs no step knowledge for a known flow |
| 20 | Step model of the second batch. (a) A dialog step returns `waiting`, `needs_input`. Only the thread starter or the agent owner answers. The same step resumes on the same agent. `hop` does not grow. `dialog_timeout_h` (24) ends it with `dialog_timeout`. (b) The next step gets the `text` and the `artifacts` of ALL previous steps. (c) A step can return a proposed plan. It passes `validate_plan` and needs a NEW ✅. A step never starts work by itself. In a template flow an approved proposal is context only. (d) `gate: approval` stops the thread until ✅. (e) `exclude_agents_of` makes the claim rule ignore agents of earlier steps (the planner sets it for review steps). (f) At most one `on_fail` branch per plan, no loop, taken only on `run_failed`. A timeout uses Retry. (g) Free plans may use these fields, with limit 3. (h) A rejected `write` tag step ends `failed`, `rejected`, with no second claimer | A general "author cannot review" rule in the core; a branch on any failure; loops; parallel steps; a proposal that starts work | Small, explicit fields. Each one only adds a stop or a restriction. No new trust path |
| 21 | Safety changes of the second batch. (a) `deny_rules` is a union: `Bash(git push:*)` is always denied and the owner list only adds. (b) An exposed `exec` capability MUST have an `input_schema`. (c) Declared `exec` and `http` capabilities are `read` only. `http` uses `https`, except for `localhost` and `127.0.0.1`. (d) `Transport.upload_file` sends artifacts (Slack: `files:write`) and the link goes in `artifacts`. (e) Card and task wire field names (`bot_id`, `bot_user_id`, `by`, `owner`) stay. (f) A step access fits a capability only on exact equality or when the card entry has no `access` | A custom `deny_rules` list that replaces the default; a schema for every capability; declared `write` capabilities; renaming wire fields; a loose access fit | A typo must not remove the push guard. A payload from another person must have a shape before it reaches a local command. No worktree path exists for `exec` and `http` |
| 22 | A wiki LLM becomes a read-only `knowledge` capability (spec 008, deferred). It is a declared `http` capability: `https`, Keychain token, `input_schema`, explicit exposure. Input `{question}` (max 500 characters), output `{answer, sources[]}`. Use 1: a step `tag:knowledge` before the work step; the answer goes into `context`. Use 2 (later): an MCP server over the wiki. An answer is untrusted data and never changes step rights | A Slack-native agent with a card (needs changes in the wiki bot); an @mention with free-text parsing (unreliable, unverified `app_mention` between bots) | Reuses the capability, tag, and `context` rules. No core change. Confused-deputy risk: the shared base holds only team-open documents, or the capability checks the asker |

Decisions 8 and 14 were reworded on 2026-11-26 to follow decision 15.

## 4. Architecture

```text
            Slack workspace (UI + bus + state)
   #pipe-agents (agent cards)   #pipe-status   #pipe-work (thread = task)
        ▲  Socket Mode (outbound WebSocket) ▲          ▲
        │                                   │          │
 ┌──────┴──────────── owner laptop ─────────┴──────────┴───────┐
 │  pipe-adapter (Python, launchd)                             │
 │   ├─ discovery → AgentCard, hash, chat.update               │
 │   ├─ router    → mention? next? hop? allowlist? exposure?   │
 │   ├─ planner   → natural language → plan in metadata → ✅    │
 │   ├─ runner    → RunRequest → runtime adapter (claude -p)   │
 │   └─ exposure  → discovered ≠ exposed                       │
 │  Claude Code hooks → status events                          │
 │  Agents with a card: any capability, for example review     │
 └─────────────────────────────────────────────────────────────┘
        ▲ webhooks / scheduled pipelines
   Triggers: any bot with a kind: trigger card (GitLab CI first)
   MR state: replaceable provider (GitLab first)
```

Ports. The core talks to the outside world through three ports only:

| Port | Role | First adapter |
| --- | --- | --- |
| `Transport` | Chat operations: publish and read pinned cards, post and update thread messages with `pipe.task.v1` metadata, read a thread, receive events (mention, reaction, button click, reconnect), post buttons, DM the owner, catch-up reads, upload a file (`upload_file`) | Slack (`transport_slack_*`, `slack_bolt` Socket Mode; files: `files_upload_v2`, scope `files:write`). Discord and Telegram are possible future adapters. |
| `Runtime` | Run one capability: `RunRequest` in, `{text, status, next?, artifacts?, data?}` out | `claude -p` (`runtime_claude_*`). `exec` (`runtime_exec`) and `http` (`runtime_http`) run capabilities that the owner declares in config. |
| `MR-state` | Read the state of an MR by URL | GitLab (`gitlab_io`) |

What we build:

1. `pipe-adapter`: one Python process per owner, run by launchd.
2. Status hook script for Claude Code hooks.
3. An agent card for the review agent. It lists a capability with the tag `review`. wiz-review is the first implementation. The agent posts `status: done` in the thread when its step ends. The core has no review callback.
4. A trigger template that posts a mention with `metadata` to Slack. GitLab CI is the first example.

## 5. Contracts

### 5.1 Runtime contract

```text
Input (adapter core → runtime adapter)
  thread:  messages of this thread only
  task:    { id: thread_ts, purpose, from_agent, owner, hop, pipeline?, step? }
  request: { capabilities: [capability_id, ...],   # capabilities to load
             access: read | write,                  # never approve: it runs no runtime
             requester_is_owner: bool,
             target?: string,                       # write only; opaque to the core
             output_schema?: object }               # from the capability; opaque to the core

Output (runtime adapter → adapter core)
  text:      reply for the thread
  status:    done | needs_approval | waiting | failed | delegate   # delegate: reserved, ignored by the core
  reason?:   string                                # with waiting: needs_input (text is the question)
  next?:     { agent, access, payload }
  artifacts: [MR url, file url, ...]
  data?:     object                                # structured result; checked against output_schema by the core
  proposal?: object                                # a proposed plan; the core checks it with validate_plan and needs a new ✅
```

The core picks the runtime adapter by the `runtime` of the capability (`claude`, `exec`, or `http`). The step `payload` goes in `task.payload`. A runtime adapter passes `output_schema` to its runtime when the runtime supports it (`claude`: `--json-schema`; `exec` and `http`: in the input).

`task.purpose` is the label of the call: `chat`, `plan`, or `step`. `task.payload` is the effective payload: the step `payload` plus the keys `context` (the `text` and `artifacts` of all done steps before it) and `artifacts` (all their links). A resume after a dialog answer is the same call again with the longer thread. `waiting` with `reason: needs_input` starts a dialog (§6). `status: failed` is the only status that can take an `on_fail` branch. A runtime exception does not.

The runtime does not know about `hop`, trust, or Slack. The adapter core does all checks. The core passes `request` and nothing else about tools. The runtime adapter (today: `claude`) turns `request` into runtime flags: `--plugin-dir`, `--allowedTools "Skill(pipe-exposed:<name>)"`, `--mcp-config`, `--strict-mcp-config`, and `--tools`. It reads its own config section (§5.4) for `owner_tools`, `repo_roots`, and deny rules. `access: read` means no file writes. `target` is an optional opaque name from the plan step. Only the runtime adapter reads it (§5.4 `delegate_repos`). The status `delegate` is reserved. The core ignores it: only a plan step starts a delegation, so a runtime result with `status: delegate` makes the step fail.

### 5.2 Slack message metadata `pipe.task.v1`

`event_type = "pipe.task.v1"`. `event_payload`:

```json
{
  "v": 1,
  "task_id": "<thread_ts>",
  "phase": "plan | step",
  "access": "read | write | approve",
  "status": "needs_approval | claimed | running | waiting | done | failed",   // waiting + reason needs_input = a dialog question
  "by": "<bot_id>",
  "hop": 0,
  "pipeline": { "source": "free | template:<name>@<hash>", "steps": [ { "agent": "<bot_id> | human:<user_id> | any", "capability": "<capability_id> | tag:<tag>", "access": "read", "goal": "...", "payload": {}, "exclude_agents_of": [0], "on_fail": 3, "gate": "approval" } ] },
  "step": 0,
  "next": { "agent": "<bot_id> | any", "access": "read", "payload": {} },
  "artifacts": ["https://gitlab.../merge_requests/1"],
  "reason": null
}
```

`access` is the level of a step: `read` (no file writes), `write` (file changes), or `approve` (a button, no runtime). What a step does comes from its `capability`, not from `access`. A `human:<user_id>` step has `access: approve` and no capability. A `write` step can have an optional `target` (an opaque string, at most 64 characters). The core carries it and never reads it. `validate_plan` does not check it, because the map of the target agent is private. `phase` tells a plan-phase message from a step message. `access` is present on step messages only. A task message has no field `kind`. The name `kind` belongs to the agent card only. `pipeline`, `next`, `artifacts`, and `reason` are optional.

**Step fields of the second batch.** `exclude_agents_of` is a list of earlier bot-step indexes. The claim rule ignores a claim from an agent that holds an excluded step. The planner sets it for a review step. `gate: approval` makes the thread wait for a new ✅ after the step (a type 5 result with `needs_approval`). `on_fail` is the index of the last step. It runs only when the source step ends `failed` with `reason: run_failed`. A plan has at most one `on_fail`, no loop, and no human step. The branch handoff is a `failed` message that carries `next`. A free plan may use all three fields. `pipeline.source` is `template:<name>@<hash>` or `free` (default). It is only a claim. Every adapter recomputes it from its own template files (same name, same hash, matching step shape). Else it is `free`. The `hop` limit is 3 for `free` and 5 for a verified template. **Dialog.** A step that returns `waiting` with `reason: needs_input` posts its question. Only the thread starter or the agent owner can answer. The answer mentions the agent. The same step runs again on the same agent. `hop` does not grow. The step timer counts only runs. After `dialog_timeout_h` the step is `failed` with `reason: dialog_timeout` and a Retry button. **Proposal.** A step may return a proposed plan. It passes `validate_plan` as a free plan, or the step fails with `reason: invalid_proposal`. A type 5 result with `needs_approval` shows it. A new ✅ releases the thread. A step never starts work by itself. The proposal is context only.

**Late binding.** A step with `agent: "any"` and `capability: "tag:<tag>"` can be claimed by any agent whose card has an exposed capability with that tag and a fitting access (the card entry has no `access`, or the same `access` as the step). The claim with the lowest `ts` wins. `validate_plan` checks that at least one card matches. If nobody claims within `step_timeout_min`, the sender of the handoff posts `failed` with `reason: no_claimer` and a Retry button. **Payload.** A step may have a `payload` object. When the capability has an `input_schema`, the core validates the payload before the run (`reason: invalid_payload`). When it has an `output_schema`, the core validates `data` after the run (`reason: invalid_result`). **Identities.** The core reads the author of a message as `sender_id`, `sender_is_bot`, and `sender_handle`, and the owner field of a card as `card_owner_id`. The Slack adapter maps `bot_id` or `user` to `sender_id`, and the presence of `bot_id` to `sender_is_bot`. The wire fields `bot_id`, `bot_user_id`, `by`, and `owner` keep their names.

### 5.3 Agent card

One pinned message per agent in `#pipe-agents`. `event_type = "pipe.card.v1"`. The payload follows the A2A AgentCard shape:

```json
{
  "name": "coder-pavlo",
  "description": "...",
  "owner": "<slack_user_id>",
  "bot_id": "<bot_id>",
  "kind": "agent | trigger",
  "mode": "laptop",
  "bot_user_id": "<slack_user_id of the bot>",
  "skills": [ { "id": "review-mr", "name": "...", "description": "...", "tags": ["review"], "access": "read", "input_schema": {}, "output_schema": {} } ],
  "hash": "<sha256 of the skills list>"
}
```

Only exposed capabilities go into `skills`. Never publish MCP URLs, tokens, local paths, or config content. `access`, `input_schema`, and `output_schema` are optional. They come from a declared capability (§5.4). A schema uses a JSON Schema subset (`type`, `properties`, `required`, `items`, `enum`, length and range limits, `additionalProperties` as a boolean) and is at most 2000 characters. The card never holds the runtime kind, a command, a URL, a token, or an environment name. `skills[].id` is the stable `capability_id`. The core uses only this ID. A tag `review` marks a review capability. Tags come from two sources: the `tags` list of the skill frontmatter (lower case, at most 8) and the optional owner config map `tags` (§5.4). The config map wins: for a capability that has an entry, its list replaces the frontmatter tags. `bot_user_id` comes from `auth.test` when the adapter publishes the card. The adapter mentions the next agent as `<@bot_user_id>`. The adapter does not need the `users:read` scope.

### 5.4 Local config `~/.pipe/config.yaml`

```yaml
agent_name: coder-pavlo
owner: <slack_user_id>                    # tool limits for non-owner senders need it
slack_tokens: keychain:pipe-coder-pavlo   # never a plain token in the file
allowlist: [<id>, ...]                    # Slack user IDs and bot IDs; see §6 C
exposed: [review-mr, ...]                 # capability_id values other people can use
tags:                                     # optional; replaces the frontmatter tags of that capability
  <capability_id>: [review]               # for example: mark a plugin skill that has no tags
step_timeout_min: 30
dialog_timeout_h: 24                      # longest wait for a dialog answer (spec 003)
capabilities:                             # optional; owner-declared capabilities (owner-only until listed in exposed)
  - id: lint-repo                         # capability_id is "exec:lint-repo"
    name: Lint repo
    description: Run the linter on a checkout
    tags: [lint]
    access: read                          # read only in this version
    runtime: exec                         # exec | http
    command: [/usr/local/bin/pipe-lint]   # exec: argv list, absolute first item, no shell
    env_allow: [HOME]                     # exec: only these variables plus PIPE_RUNTIME=1
    timeout_s: 120
    input_schema: { type: object, required: [repo], properties: { repo: { type: string } } }   # REQUIRED when this exec capability is in exposed
    output_schema: { type: object }
  - id: ticket-search                     # capability_id is "http:ticket-search"
    runtime: http
    url: https://tickets.example.com/api/search   # POST JSON; https only (http only for localhost)
    token: keychain:pipe-ticket-search    # Keychain name; never a plain token
    name: Ticket search
    description: Search tickets
    access: read
runtime:
  name: claude                            # default runtime adapter (claude | exec | http)
  claude:                                 # only the claude runtime adapter reads this section
    repo_roots: [~/code]                  # file confinement
    owner_tools: [Read, Grep, Glob]       # tools of an owner-started step (default)
    deny_rules: []                        # extra deny rules. Bash(git push:*) is ALWAYS denied (union). The owner can only add rules (spec 001)
    write_tools: [Read, Grep, Glob, Edit, Write]   # tools of a write step; scoped Bash(<cmd>:*) is allowed, bare Bash is an error
    delegate_repos:                       # target repos for write steps: name -> absolute path inside repo_roots
      app: /Users/me/code/app
    base_branch: main                     # start point and target of the MR
    worktree_root: ~/.pipe/worktrees      # one directory per write run
```

`owner_tools`, `repo_roots`, `deny_rules`, `write_tools`, `delegate_repos`, `base_branch`, and `worktree_root` are config of the `claude` runtime adapter. The effective deny list is `Bash(git push:*)` plus `deny_rules`. An exposed `exec` capability must have an `input_schema`, or the config load fails. A declared capability with `access: write`, or an `http` URL that is not `https` (except `localhost` and `127.0.0.1`), fails the config load. The key `allowlist` holds `sender_id` values (Slack: user IDs and bot IDs). The key `capabilities` declares capabilities for the `exec` and `http` runtime adapters (`command`, `env_allow`, `url`, `token`, and `timeout_s` are read by those adapters only and never enter the card). The core reads `allowlist`, `owner`, the `tags` map, and the generic fields of each declared capability (`id`, `name`, `description`, `tags`, `access`, schemas). They are not core concepts. The core never reads the `runtime` section. The `tags` map is core-side data: the card builder uses it. It does not name any runtime tool.

### 5.5 Transport: `upload_file`

`upload_file(channel, thread, name, data, title) -> link`. `data` is `bytes` or a `Path`. The operation sends an artifact (a screenshot or a report) into the thread. It returns an `https://` link. The core puts the link in `artifacts` and never reads the file. The Slack adapter uses `files_upload_v2` and the bot scope `files:write`. `name` and `title` pass `scrub`. A `Path` must be a regular file inside the upload roots of the adapter (default `~/.pipe/run/`), at most 10 MB. Else `UploadRefused`.

## 6. Flows

**Common rule.** The adapter acts only on a direct mention of its bot or on `metadata.next.agent == self`. Before it starts the runtime, it checks: `hop ≤ 3` for a free plan (`hop ≤ 5` for a verified template, see §8), the sender is trusted, the capabilities are exposed, the sender is in the allowlist (or the owner clicks the button).

**Pipeline from chat.**

1. A human writes: "@coder-pavlo add endpoint X, then @reviewer-olena reviews it".
2. The first mentioned agent is the planner. It reads the agent cards and builds `pipeline.steps`. A step is `{agent, capability, access, goal}`, with an optional `payload` and the optional `exclude_agents_of`, `gate`, and `on_fail` (§5.2). `agent` is a bot, `human:<user_id>`, or `any` (late binding with `capability: tag:<tag>`).
3. The planner validates the plan: every agent has a card, the card lists the `capability`, and the capability is exposed. For a step with `agent: any` and `capability: tag:<tag>`, at least one card must list an exposed capability with that tag and a fitting access. A `human:<user_id>` step has no capability.
4. The planner posts the plan with `status: needs_approval`. The human approves with ✅.
5. A step ends when its agent posts `status: done` in the thread. The result names `next` for the next step. For a tag step, the handoff mentions every eligible agent. The claim with the lowest `ts` wins. If nobody claims within `step_timeout_min`, the sender posts `failed`, `no_claimer`, with a Retry button. The agent that runs the step checks the `payload` against the `input_schema`, picks the runtime adapter by the `runtime` of its capability (`claude`, `exec`, or `http`), and checks `data` against the `output_schema`.
6. The last step `approve@human` shows a button. Then the thread gets `status: done`.

**C. Delegation.** Agent A sets `next = {agent: B, access: write}` (B can also be `any` with a tag: then the gate runs for the agent that wins the claim, with its own owner and allowlist). Only a `write` step from another person goes through the gate. A `read` step has no gate (exposure is the limit; the owner sets `max_budget_usd`). The gate accepts without a click only when both conditions are true: (1) the sender bot A is in the allowlist of owner B, and (2) the thread starter is the owner of A or is in the allowlist. In all other cases, owner B gets an accept/reject button. A pending button has no expiry. A reject gives `status: failed`, `reason: rejected`, and no Retry. Runtime B works in a separate git worktree and branch of the target repo. The target repo comes from `runtime.claude.delegate_repos` and the optional `target` of the step. A `target` that is not in the map fails with `reason: unknown_target`. With one map entry, `target` is optional. With more than one entry and no `target`, the step fails with `reason: target_required`. An empty map refuses every `write` step. Repo names and paths never go into the card. The adapter creates the MR with git push options (`-o merge_request.create`, `-o merge_request.target=<base_branch>`) on a new branch. It never pushes to `base_branch`. The MR link goes back in `artifacts`.

**A. Review.** A review step is a normal capability step. Its capability has the tag `review`. wiz-review is one possible implementation: its agent card lists a `review` capability. The review agent posts `status: done` in the thread when the drafts are ready. The pipeline then moves to the next step. The core has no special "review done" callback.

**B. Status.** Claude Code hooks (`SessionStart` → `working`, `Stop` → `idle`, `SessionEnd` → `stopped`) run a script. The script posts to `#pipe-status`, one message per session, and uses `chat.update` instead of new messages. Status messages use their own metadata type `pipe.status.v1` (not `pipe.task.v1`), with an `updated_at` field. The hook does nothing inside an adapter runtime child (`PIPE_RUNTIME=1`). An "MR created" status event is not in M0; add it later. To answer "who works on what?", any online agent reads `#pipe-status` for the last 24 hours.

**Triggers.** Any bot with a `kind: trigger` card can start a pipeline. A trigger bot has no skills. It posts a mention with `metadata` to `#pipe-work`. If the trigger bot is in the allowlist of the mentioned agent, the pipeline starts without ✅. If not, the owner gets an accept/reject button. A trigger carries EITHER a fixed `pipeline` in the metadata OR the text `flow:<name> <goal>` with no `pipeline` (the planner expands the template in code, no LLM). Both together, or a free goal text, are ignored (`bad_payload`). From then on it is a normal pipeline. GitLab CI is one example template: a schedule or webhook runs a CI job. The job posts as the `pipe-gitlab` bot. Its token is in a masked GitLab CI variable.

**Dialog step.** A step can need a human answer. Its agent returns `status: waiting` with `reason: needs_input`. The `text` is the question. The thread shows it and mentions the thread starter. Only the thread starter or the owner of that agent can answer. The answer is a thread reply that mentions the agent. The SAME step runs again on the SAME agent, with the thread as context. There is no new claim. `hop` does not grow. The step timer counts only the time of a run, so it is paused while the step waits. After `dialog_timeout_h` (default 24) the step is `failed` with `reason: dialog_timeout` and a Retry button. The next step gets the `text` and the `artifacts` of ALL previous steps in its payload (`context` and `artifacts`). Large context goes by link (`upload_file`).

**Plan proposal.** A step can return a proposed plan. The core checks it with `validate_plan` as a free plan. A bad proposal ends the step with `invalid_proposal`. A good one is shown in a type 5 result with `needs_approval`. A NEW ✅ from the thread starter or the planner owner releases it. A step never starts work by itself, and a proposal starts nothing. Inside a template flow, an approved proposal is context only and the template goes on. A step with `gate: approval` uses the same path: a mid-flow approval is a `needs_approval` result message plus ✅.

**Flow from a template.** A flow is a plan with a name. A template is a YAML file: `flows/<name>.yaml` (team git) or `~/.pipe/flows/<name>.yaml` (owner override; it wins by name). A template has only tag steps and names no agent, plugin, or tool. A person writes `@agent flow:<name> [key=value ...] <goal>`. One named agent is enough. The planner expands the template in code, with no LLM, checks it with `validate_plan`, and posts it with `needs_approval`. The planner can also pick a template from free text: the LLM returns only the name, and the core expands it. The plan records `pipeline.source` (`template:<name>@<hash>`). Every adapter recomputes the source from its own files. A verified template has `hop` limit 5. Everything else has 3. Missing tags are reported by name before ✅. Every gate stays: ✅ on the plan (or the trigger gate), the owner gate of §6 C for `write` steps. No chat message, button, or agent run writes a template file. The catalog of version 1 (ten flows) and the tag vocabulary are in spec 006.

## 7. Errors and edge cases

- **Agent was offline.** Socket Mode does not replay events. At start and after each Socket Mode reconnect (for example after laptop sleep), the adapter reads `conversations.history` after the last seen `ts` (stored locally) and picks up open steps with `next == self`.
- **Duplicates.** Drop repeated Slack events by `event_id`.
- **Two agents take one step.** Each posts `status: claimed`. The claim with the lowest `ts` wins. The other agent stops.
- **Runtime fails or hangs.** Timeout per step (default 30 min). Post `status: failed` with `reason` and a "Retry" button. No automatic retries.
- **Owner offline.** The step gets `status: waiting` with `reason: owner offline`. Record the wait time for the metrics.
- **Nobody answers a question.** After `dialog_timeout_h` the step gets `failed` with `reason: dialog_timeout` and a Retry button. The check also runs after an adapter restart.
- **Different template copies.** Two team members with different template files get the effective source `free` for the other copy. The thread stops at `hop` 4 with "plan source not verified". Both people update their copy.
- **Failure branch.** Only `reason: run_failed` takes `on_fail`. A timeout, `no_claimer`, `rejected`, or an invalid payload shows Retry instead.

## 8. Security

- Trust `metadata` only from `bot_id` values that have an agent card.
- Count ✅ and button clicks only from the thread starter or the agent owner.
- A plain mention from a person who is not the owner runs the runtime with no tools (`claude` adapter: `--tools ""`). The agent answers from the thread text only. File access for other people comes only with delegation (M3), in a worktree.
- The owner's own run has read-only tools by default (`owner_tools` of the `claude` adapter), limited to `repo_roots`. Files such as `~/.ssh` and `~/.aws` stay out of reach. Prompt injection from other people's text in the thread is an accepted MVP risk inside that limit.
- For foreign tasks, the core passes the capability IDs, the access level, and `requester_is_owner`. The `claude` adapter turns them into `--allowedTools` and blocks `owner-only` tools with `--disallowedTools`.
- Delegation works only in a separate worktree and branch. No push to `main`.
- Slack tokens live in the macOS Keychain.
- Before the adapter posts text, it removes strings that look like tokens.
- `hop ≤ 3` per thread for a free plan. `hop ≤ 5` for a plan whose source is a verified template. Every adapter recomputes the source from its own template files (same name, same hash of the parsed file, matching step shape). Else the source is `free`. A stale copy fails closed with "plan source not verified". In a free plan, two agents may hand a step back and forth at most two times.
- An exposed `exec` capability MUST have an `input_schema`. Declared `exec` and `http` capabilities are `read` only. `http` uses `https`, except for `localhost` and `127.0.0.1`.
- Only the thread starter or the agent owner can answer a dialog question or release a ✅ gate. A proposal never starts work.
- `Bash(git push:*)` is always denied in an owner run. The owner can only add deny rules.

## 9. Milestones (one `/speckit.specify` run each)

Each milestone gives value alone. Run `/speckit.specify` with the "Specify input" text, then `/speckit.plan` with the "Plan notes".

### M0 — Adapter core and status

**Specify input.** A developer installs `pipe-adapter` on a laptop. The developer mentions the agent in a Slack thread. The agent runs Claude Code with the thread as context and replies in the same thread. If the laptop was offline, the agent picks up missed mentions when it starts again. Claude Code sessions post their status (who, repo, branch, stage, blocker) to `#pipe-status`, one thread per session, updated in place. Anyone can ask an online agent "who works on what?" and get an answer from the last 24 hours.

**Plan notes.** Python, `slack_bolt` Socket Mode, `claude -p`, launchd, Keychain. Copy the tick, launcher, and doctor patterns from wiz-review. Catch-up by `conversations.history`. Dedupe by `event_id`. One Slack app per agent.

**Acceptance.**

- Mention → reply in the same thread.
- Mention while offline → reply after the adapter starts.
- The same Slack event twice → one reply.
- A session start and stop update one message in `#pipe-status`.
- `pipe doctor` checks the token, Slack access, `claude`, and launchd.

### M1 — Discovery and exposure

**Specify input.** When the adapter starts, it finds what the agent can do: plugins, skills, MCP servers, slash commands, and repos. It shows the owner the list. Capabilities that use the owner's credentials are owner-only by default. The owner chooses what to expose. The agent publishes its exposed capabilities as a pinned card in `#pipe-agents`. When the capabilities change, the card is updated.

**Plan notes.** Read the Claude Code plugin, skill, and MCP configuration. Card format is A2A AgentCard (§5.3). The card has `bot_user_id` from `auth.test` and stable `skills[].id` values (the `capability_id`). Tags come from the frontmatter and from the owner `tags` map (the map wins). Hash of the skills list. `chat.update` on hash change. Classification rule for `owner-only`: any MCP server and any skill that calls an external system with user credentials. The runtime adapter (`claude`) applies this rule. The core only consumes the result (`exposed`, `owner-only`, or skipped).

**Acceptance.**

- A new skill appears → the card updates within one adapter start.
- An MCP server is `owner-only` until the owner exposes it.
- The card has no URLs, tokens, or local paths.

### M2 — Pipelines from chat

**Specify input.** A human describes a chain of work in one message and names agents. The first named agent builds a plan from the agent cards, shows it in the thread, and waits for ✅. After ✅, the agents do the steps one by one in the same thread. Each step shows its status. The last step can ask a human to approve.

**Plan notes.** `pipe.task.v1` metadata (§5.2). Pure functions: `route(event, thread_state) → decision`, `validate_plan(plan, cards, starter, flows) → errors` (agent has a card, the card lists the capability, access is `read` or `approve`), `resolve_claim(claims) → winner`. The core passes `RunRequest{capabilities, access, requester_is_owner}` to the runtime adapter. Step timeout. Trust rules from §8.

**Acceptance.**

- A plan with an unknown agent or an owner-only capability is rejected before ✅.
- ✅ from a person who is not the thread starter does not start the pipeline.
- Metadata from a bot without a card is ignored.
- `hop` 4 is refused for a free plan (a verified template has limit 5, M5).
- Two claims → one winner, the lowest `ts`.
- A hung step → `failed` after the timeout, with a "Retry" button.
- A step that another person started loads only exposed capabilities and gets no file tool.
- The metrics script (§10) gives correct values for a test channel.

### M3 — Delegation

**Specify input.** My agent can ask the agent of a colleague to do work in the colleague's repo. If my agent is in the colleague's allowlist, the work starts at once. If not, the colleague gets a button to accept or reject. The colleague's agent works in a separate branch and opens an MR. The MR link comes back to the thread.

**Plan notes.** Allowlist in `~/.pipe/config.yaml`. Target repos in `runtime.claude.delegate_repos`. Git worktree per task. Steps with `access: write` run in the worktree. The runtime adapter sets the tool limits from `access`. Never push to `main`.

**Acceptance.**

- An agent in the allowlist → work starts without a button.
- An agent not in the allowlist → button to the owner. Reject → `status: failed`, `reason: rejected`.
- An agent in the allowlist, but a thread starter who is not the owner of that agent and not in the allowlist → button to the owner.
- An unknown `target`, or a missing `target` when the map has more than one entry → `status: failed`, `reason: unknown_target` or `target_required`.
- The result is an MR from a separate branch. `main` is never changed.

### M4 — Review via wiz-review and GitLab triggers

**Specify input.** A pipeline step can ask for a code review. A review step is a step whose capability has the tag `review`. wiz-review is the first implementation behind an agent card. When the review agent posts `status: done`, the pipeline continues. Any bot with a `kind: trigger` card can start a pipeline in Slack. A GitLab schedule or event is the first example.

**Plan notes.** The review agent card lists a capability with the tag `review`. The core has no review callback: a step ends when its agent posts `status: done` (a wiz-review agent wrapper posts it). Trigger gate: the owner's allowlist, or an accept/reject button. CI job template that posts a mention with `metadata` as the `pipe-gitlab` bot (an example). GitLab Pipeline schedules are edited in the GitLab UI.

**Acceptance.**

- A step whose capability has the tag `review` starts the review agent. When it posts `status: done`, the next step starts.
- A bot with a `kind: trigger` card posts a mention. The mentioned agent starts the pipeline (allowlist or button).
- A GitLab schedule posts a mention as one example of this rule.

### M5 — Flow catalog

**Specify input.** The team keeps flow templates as files in git. A person starts a flow with `@agent flow:<name> <goal>`, or the planner picks a template from the free text. A template has only tag steps. The plan from a template still needs approval. Ten flows are in version 1: feature-dev, bugfix, planning, brainstorm, research, test-run, troubleshoot, review-handoff, delegate, and nightly. A verified template can have up to 5 agent steps.

**Plan notes.** Spec 006. Data files in `flows/` and the tag vocabulary `flows/tags.yaml`. One pure core module `core/flows.py`, one loader `flows_io.py`, the command `pipe flows`. It needs the second batch of spec 003: plan source and hop limit, dialog step, context, plan proposal, gate, `exclude_agents_of`, `on_fail`. Constitution 1.3.0.

**Acceptance.**

- Each of the ten files passes `validate_flow` and expands to a valid plan with fake cards. No LLM runs.
- A plan with a tag that no card offers is rejected before ✅. The error lists the missing tags by name.
- The `hop` limit is 5 only when the template hash and the step shape match on the adapter. A forged, stale, or unknown source gives 3.
- An on_fail branch happens only for `run_failed`. An agent of an excluded step cannot claim the excluding step.
- A dialog answer resumes the same step on the same agent. `hop` does not grow.
- No code path writes a template file.

### M6 — Knowledge capability

M6 knowledge capability, deferred, spec 008. It waits for the two open questions in §12.

## 10. Experiment and metrics

Run for 2–4 weeks after M4. A script computes the metrics from `metadata` in `#pipe-work`. It reads the `artifacts` links of the task messages. It reads the MR state through a replaceable provider (GitLab is the first one).

| Metric | Threshold |
| --- | --- |
| Useful delegations between owners (an `artifacts` MR link with state merged, from the provider) | ≥ 3 per week |
| Chat pipelines that finish without manual help between steps | ≥ 50% |
| Agent messages marked noisy (🔇) | < 10%, and 0 loops stopped by `hop` |
| Median wait for `owner offline` | track only; it is a trigger |

**Upgrade triggers.**

- Saved pipelines or recurring schedules from chat are needed → add a thin coordinator (one service + Postgres).
- Steps often wait for `owner offline` → add one shared always-on agent.
- No single list of all tasks blocks the team → thin coordinator.

## 11. Out of scope for the MVP

Server, database, web UI, marketplace, payments, reputation, always-on agents, own LLM runtime, central agent registry in git, saved pipelines from chat (templates are files that people edit by hand, spec 006), recurring schedules from chat, parallel steps, loops, daily digest, agents outside the team.

## 12. Open questions

- Decided: the free Slack plan keeps 90 days of history. This is enough for the experiment. Review it before permanent use.
- Decided: the owner owns the wiz-review agent wrapper (the agent card and the `status: done` post) in the MVP.
- The `claude` runtime adapter runs every `claude -p` child with `--restricted`. M0 does this. This mode ignores user, project, and local settings files, so the child does not load the owner's plugins, skills, or MCP servers. M1–M3 need exposed skills inside runs. The 002/003 plan must load only the exposed capabilities explicitly (for example with `--settings`, `--plugin-dir`, or `--mcp-config`), and keep `--restricted` file confinement.
- Resolved on 2026-11-26 (second batch of owner decisions, constitution 1.3.0):
  - The `hop` limit is 3 for a free plan and 5 for a verified template. Every adapter recomputes the source.
  - The tag vocabulary is data (`flows/tags.yaml`). Saving pipelines from chat stays out of scope.
  - An exposed `exec` capability needs an `input_schema`. Declared capabilities are `read` only. `http` uses `https`.
  - `deny_rules` is a union with `Bash(git push:*)`.
  - `Transport.upload_file` (Slack scope `files:write`). `pipe flows`.
  - Dialog step, context for all previous steps, plan proposal, `gate`, `exclude_agents_of`, `on_fail`. The author-cannot-review rule is `exclude_agents_of` (the general rule was rejected).
  - A step access fits a capability only on equality or when the card entry has no `access`. A rejected `write` tag step has no second claimer (deferred).
  - Card and task wire field names stay.
- Confirmed by the owner on 2026-11-26 (pass 1 and pass 2): (1) `upload_file` reads `~/.pipe/run/` only (regular file, no symbolic link, 10 MB); (2) an approved proposal is context only, also in a free plan; (3) a dialog answer needs a mention of the agent; (4) `input_schema` validates the effective payload (a schema with `additionalProperties: false` lists `context` and `artifacts`); (5) the reason code of an expired dialog is `dialog_timeout`; (6) a dialog answer is not manual help in the metric. Decided later on 2026-11-26: the `exec` output field `files` (spec 005 O1 = a); a `write` step removes its worktree on a dialog and resumes in a new one, a `proposal` from `write` fails the step, and `gate: approval` is allowed on `write` (spec 004 O1 = a, O2 = allow). See `docs/reference.md` for the scope list and the config keys.
- Open (spec 008, knowledge capability): (1) Does the wiki bot have an HTTP API or a CLI, or is it Slack-only? (2) Does the wiki hold documents with restricted access?
- 14 ChatGPT image links in `raw.md` were not read (blocked). They are probably UI mockups. They do not affect the MVP, because the UI is Slack.
