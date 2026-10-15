# Local AI Agent Lab

This repository contains the agent scaffold and local tooling used for the lab exercise.

## My setup

- The repo root is the nested project folder for this lab.
- The code that matters for the lab is under `sample-agent/student_agent`.
- The runtime is expected to use a local Ollama instance on `http://127.0.0.1:11434`.
- The model is selected per run through the CLI flags, typically using a small local model such as `qwen2.5-coder:7b`.
- This project is designed to run locally and to keep the target service outside the agent runtime boundary.

## Where the lab project is

The actual lab implementation is not at the repo root. It lives under:

- `sample-agent/student_agent`

That directory contains the agent loop, runtime policy checks, model adapter, and CLI wiring.

## Model selection

The agent accepts a model name via the CLI. Typical usage:

```bash
python3 -m student_agent.cli \
  --root ../../target-service \
  --mode read \
  --model qwen2.5-coder:7b \
  --offline \
  --task "Inspect the target service and summarize the current state."
```

If Ollama is running locally, the chosen model needs to be available in the local model list before execution.

## Run commands

From inside the sample agent folder:

```bash
cd sample-agent
python3 -m student_agent.cli --help
```

Example read-only inspection:

```bash
cd sample-agent
python3 -m student_agent.cli \
  --root ../../target-service \
  --mode read \
  --model qwen2.5-coder:7b \
  --offline \
  --task "Read the business rules and summarize the pricing logic."
```

Example edit mode (only when the task is explicitly scoped and approved):

```bash
cd sample-agent
python3 -m student_agent.cli \
  --root ../../target-service \
  --mode edit \
  --model qwen2.5-coder:7b \
  --offline \
  --task "Repair the pricing bug according to the documented business rules."
```

## Permissions and safety rules

The runtime enforces a strict permission model:

- `read` mode allows read-only actions such as listing files, reading files, searching, and fetching safe HTTPS URLs.
- `edit` mode allows writing only under the allowed root and only for permitted paths.
- Path traversal, hidden paths, absolute paths, and symlinks are blocked.
- Protected files are refused, including service validation and business-rule files that are explicitly marked as sensitive.
- Bash execution is not implicitly approved. The agent must receive an explicit approval for shell actions.
- HTTPS fetches are restricted to `docs.python.org` and must avoid redirects, query strings, and fragments.

In other words, the agent is intentionally constrained to keep the lab environment safe and reproducible.

## Unfinished / current status

This repository includes working agent scaffolding and validated public checks, but the full service repair is not yet in an acceptable end state.

The important project reality is:

- the agent infrastructure is implemented and passes the public contract checks,
- but the actual target-service pricing repair still requires a verified final fix,

## Notes

- Public checks are stored under `checks/`.
- The target service under test is in `target-service` and the injected variant is in `target-service-inject`.
- The local model and file access policy should be reviewed before running broad edit operations.
