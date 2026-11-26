# Contract: Runtime adapters `exec` and `http`

Source: constitution principles VI and XI, design brief §5.1 and §5.4. These adapters follow [runtime-contract.md](runtime-contract.md). Spec 002 defines the config entries (declared capabilities). Spec 003 implements and tests the adapters.

## Common rules

- Each adapter is its own module: `src/pipe/runtime_exec.py` and `src/pipe/runtime_http.py`. Each implements `RuntimePort`.
- The core picks the adapter by the `runtime` value of the capability (`exec` or `http`). The default adapter is `runtime.name` (`claude`). The core never reads an adapter field.
- The adapter runs only when the capability is declared in the local config AND is exposed now (`state_of` gives `exposed`). Else the step fails with `reason: capability not available`. This holds also for a step that the owner started.
- The adapter gets the request `RunRequest((<capability_id>,), access, requester_is_owner, target?, output_schema?)` and `task = {id, purpose: "step", step, payload?, pipeline: {goal}}`.
- The adapter sends one JSON input (below). It reads one JSON result.
- The result is `{text, status, next?, artifacts?, data?, files?}`. `parse_output` (core) parses it. A bad result raises `RuntimeFailed`.
- `files` is an optional list of paths to upload, for example e2e screenshots and reports. The stepper uploads each path with `Transport.upload_file` and adds the links to `artifacts`. The `upload_file` path rules apply: a regular file in `~/.pipe/run/`, not a symlink, at most 10 MB. A refused file gives a log line and no link (005 O1 = a).
- The adapter applies `scrub` to `text`, `reason`, and `artifacts`, and `escape_mentions` to `text`, before it returns. This is the same as for `claude`.
- The adapter never puts a token, a URL, a command line, or an environment value in a log line, in a reason, or in a posted text. A log line may hold the capability ID and the host name of an `http` URL.
- The size of the result is at most 1 MB. A larger result raises `RuntimeFailed("result too large")`.
- The timeout is the capability `timeout_s`, or `step_timeout_min` minutes when the key is missing. A timeout raises `RuntimeFailed("timeout")`.

## Input (JSON)

```json
{
  "goal": "<step goal>",
  "payload": { },
  "task": { "id": "<thread id>", "step": 1 },
  "output_schema": { }
}
```

`payload` and `output_schema` are present only when they exist. The input holds no thread text, no `hop`, no trust data, and no chat identity.

## `exec`

- Config fields (spec 002): `command` (argv list), `env_allow` (list of variable names), `timeout_s`.
- The adapter starts the process with an argv list. It uses no shell. `command[0]` is an absolute path.
- The JSON input goes to stdin. The adapter reads stdout as the result. Stderr is not posted. The first 200 scrubbed characters of stderr go to the adapter log.
- The working directory is a new empty directory under `~/.pipe/run/<run_id>/` (mode 0700). The adapter removes it after the run, also after a failure and a timeout.
- The environment is minimal. It holds only the variables named in `env_allow` (copied from the adapter environment) and `PIPE_RUNTIME=1`. It holds no token variable of the adapter.
- A non-zero exit code raises `RuntimeFailed("exit <code>")`. A timeout kills the process group.

## `http`

- Config fields (spec 002): `url` (an `https://` URL; `http://` only for `localhost` and `127.0.0.1`), `token` (`keychain:<service>`, optional), `timeout_s`.
- The adapter sends `POST <url>` with `Content-Type: application/json` and the JSON input as the body. It uses `urllib` from the standard library.
- If `token` is set, the adapter reads it from the macOS Keychain (service from the config, account `token`) and sends it as `Authorization: Bearer <token>`. The token goes only to that URL. The adapter follows no redirect.
- The response body is the result. A status code outside 200 to 299 raises `RuntimeFailed("http <code>")`.
- The token is never in the config file. A value that looks like a token in `token` is a config error.

## Not in this contract

- No streaming. No retry by the adapter (a "Retry" button starts a new run). No worktree and no MR for these adapters.
