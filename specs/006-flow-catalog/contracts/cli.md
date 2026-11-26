# Contract: CLI `pipe flows`

Spec FR-031. Spec 001 owns the command dispatch (`flows_handler(action, name)` with `action` `list`, `show`, or `validate`, [../../001-adapter-core-status/contracts/cli.md](../../001-adapter-core-status/contracts/cli.md)). Spec 006 owns the handler. The command reads files and the card cache. It writes nothing. It makes no network call except the read of `#pipe-agents` that `pipe doctor` already does (the cards).

```text
pipe flows                       # list all templates
pipe flows show <name>           # show one template: steps, tags, access, gates, hash
pipe flows validate [<name>]     # check all templates, or one, and print the errors
```

## List output

```text
NAME             ORIGIN    HASH (first 12)  TAGS NEEDED                      MISSING
feature-dev      git       3fa9c01b22de     decompose implement e2e review   -
nightly          override  91bc77aa10f3     e2e troubleshoot                 troubleshoot
bugfix           git       -                -                                (invalid: step reproduce: tag not in vocabulary)
```

- `ORIGIN` is `git` or `override`. When an override hides a git file, the line says `override (hides git)`.
- `HASH` is the first 12 characters of the 32-character source hash. An invalid file shows `-`.
- `MISSING` lists the tags that no trusted card offers. It uses the card cache. When the cache is empty, the column says `(no cards)`.
- Exit code 0 when all files are valid. Exit code 1 when one file is invalid. The command still prints all lines.

## Show output

One line per step: index, id, agent (`any`, `$agent`, or human), tag, access, and the flags (`gate`, `on_fail`, `exclude`). Then the full 32-character hash, which a person can compare with the `source` of a plan.

## Validate output

```text
OK    feature-dev   git
OK    nightly       override (hides git)
FAIL  bugfix        git       step reproduce: tag not in vocabulary
```

`validate` prints one line for each file with `OK` or `FAIL` and the first error. With `<name>` it prints all errors of that file. It checks the file with `validate_flow` and, when cards exist, `missing_tags`. Exit code 0 when all files are valid, 1 when one is invalid, 2 for an unknown name. It writes nothing.

No command writes or deletes a template. There is no `pipe flows save`. The form `pipe flows <name>` of the first draft is replaced by `pipe flows show <name>`.
