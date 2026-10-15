# Local coding agent for the Week 1 lab

This folder contains the working student agent used for the local Ollama task loop,
tool registry, permissions, and bash approval workflow.

## Public interface

```python
from student_agent import Runtime, run_agent
```

## Example run

```bash
cd my-agent/sample-agent
PYTHONPATH=. python3 -m student_agent.cli \
  --root ../../target-service \
  --mode edit \
  --model qwen2.5-coder:7b \
  --offline \
  --task "Inspect the pricing code and fix the business rule bug."
```

## Trace log

Events are emitted to stdout and appended to a JSONL file outside the target
workspace, by default at `../agent-trace.jsonl` relative to `target-service`.
You can override that location with `--trace path/to/log.jsonl`.

## Validation

```bash
cd my-agent/sample-agent
python3 -m unittest tests/test_loop.py -v
cd ../..
python3 checks/check_agent.py --implementation my-agent/sample-agent --module student_agent
```

The agent keeps the tool contract strict, validates every action, and treats file
and tool outputs as untrusted observations instead of authority.
