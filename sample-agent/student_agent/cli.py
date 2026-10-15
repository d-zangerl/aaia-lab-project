"""Command-line entry point for the student agent."""

import argparse
import json
import os
from pathlib import Path

from .agent import run_agent
from .model import OllamaModel
from .runtime import Runtime


def build_parser():
    parser = argparse.ArgumentParser(description="Run the Week 1 coding agent")
    parser.add_argument("--root", required=True, help="target workspace")
    parser.add_argument(
        "--mode",
        choices=("read-only", "edit"),
        default="read-only",
    )
    parser.add_argument("--tools", help="comma-separated enabled tools")
    parser.add_argument(
        "--model",
        default=os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b"),
    )
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--trace", help="path for JSONL event log outside the target workspace")
    parser.add_argument("--task", required=True)
    return parser


def approve_command(command, cwd):
    """Prompt the human for bash approval and return True only for an exact yes."""
    print(f"Command: {command}")
    print(f"Working directory: {cwd}")
    try:
        answer = input("Approve this command only? Type yes: ").strip()
    except EOFError:
        print("Approval decision: denied (EOF)")
        return False

    approved = answer == "yes"
    print(f"Approval decision: {'approved' if approved else 'denied'}")
    return approved


def parse_tools(raw_tools):
    if raw_tools is None:
        return None
    parsed = {tool.strip() for tool in raw_tools.split(",") if tool.strip()}
    return parsed or None


def main():
    args = build_parser().parse_args()
    enabled = parse_tools(args.tools)
    model = OllamaModel(args.model)
    runtime = Runtime(
        args.root,
        mode=args.mode,
        enabled=enabled,
        approve=approve_command,
        offline=args.offline,
    )

    trace_path = Path(args.trace).expanduser() if args.trace else (Path(args.root).resolve().parent / "agent-trace.jsonl")
    trace_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(event):
        payload = json.dumps(event, ensure_ascii=False)
        with trace_path.open("a", encoding="utf-8") as handle:
            handle.write(payload + "\n")

    result = run_agent(model, runtime, args.task, emit=emit)
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
