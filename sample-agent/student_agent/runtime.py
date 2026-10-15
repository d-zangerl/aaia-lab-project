"""Tool registry and permission boundary."""

import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path


TOOL_ARGUMENTS = {
    "list_files": (),
    "read_file": ("path",),
    "search_files": ("query",),
    "write_file": ("path", "content"),
    "edit_file": ("path", "old", "new"),
    "fetch_url": ("url",),
    "bash": ("command",),
}

PROTECTED_FILES = {
    "orders/validation.py",
    "tests/test_acceptance.py",
    "docs/business-rules.md",
}

MAX_TEXT = 12_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError(f"redirect not allowed: {newurl}")


class Runtime:
    """Validate and execute model-requested tools inside a workspace."""

    def __init__(
        self,
        root,
        mode="read-only",
        enabled=None,
        approve=None,
        offline=False,
    ):
        self.root = Path(root).resolve()
        self.mode = mode
        self.enabled = set(TOOL_ARGUMENTS if enabled is None else enabled)
        self.approve = approve or (lambda _command, _cwd: False)
        self.offline = offline

    def _deny(self, message):
        return {"status": "denied", "output": message}

    def _error(self, message):
        return {"status": "error", "output": message}

    def _allowed_tools(self):
        if self.mode == "edit":
            return set(TOOL_ARGUMENTS)
        return {"list_files", "read_file", "search_files", "fetch_url"}

    def _validate_text_arg(self, value, name):
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a string")
        if len(value) > MAX_TEXT:
            raise ValueError(f"{name} exceeds the 12,000-character limit")
        return value

    def _resolve_relative_path(self, value):
        if not isinstance(value, str):
            raise ValueError("path must be a string")
        if not value or value.startswith(("/", "\\")):
            raise ValueError("absolute paths are not allowed")

        relative = Path(value)
        if any(part in {"..", ""} for part in relative.parts):
            raise ValueError("path traversal is not allowed")
        if any(part.startswith(".") for part in relative.parts):
            raise ValueError("hidden paths are not allowed")

        target = (self.root / relative).resolve(strict=False)
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("path escapes the workspace root") from exc
        return target

    def _relative(self, path):
        return path.resolve(strict=False).relative_to(self.root).as_posix()

    def _protected(self, path):
        rel = self._relative(path)
        return rel in PROTECTED_FILES

    def _run_list_files(self):
        files = []
        for path in sorted(self.root.rglob("*")):
            if path.is_dir() or path.is_symlink():
                continue
            if path.is_file():
                files.append(path.relative_to(self.root).as_posix())
                if len(files) >= 200:
                    break
        return {"status": "ok", "output": files}

    def _run_read_file(self, path):
        if not isinstance(path, str):
            return self._error("path must be a string")
        try:
            target = self._resolve_relative_path(path)
        except ValueError as exc:
            return self._deny(str(exc))

        if not target.exists() or not target.is_file():
            return self._error("file not found")

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return self._error("file is not valid UTF-8 text")

        if len(content) > MAX_TEXT:
            return {
                "status": "ok",
                "output": {
                    "path": self._relative(target),
                    "content": content[:MAX_TEXT],
                    "truncated": True,
                },
            }

        return {
            "status": "ok",
            "output": {
                "path": self._relative(target),
                "content": content,
                "truncated": False,
            },
        }

    def _run_search_files(self, query):
        try:
            text = self._validate_text_arg(query, "query")
        except ValueError as exc:
            return self._error(str(exc))

        matches = []
        files_seen = 0
        for path in sorted(self.root.rglob("*")):
            if path.is_dir() or path.is_symlink():
                continue
            if not path.is_file():
                continue
            files_seen += 1
            if files_seen > 200:
                break

            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                if text in line:
                    matches.append({
                        "path": path.relative_to(self.root).as_posix(),
                        "line": line_no,
                        "excerpt": line[:200],
                    })
                    if len(matches) >= 50:
                        return {"status": "ok", "output": matches}
        return {"status": "ok", "output": matches}

    def _run_write_file(self, path, content):
        if not isinstance(path, str):
            return self._error("path must be a string")
        try:
            target = self._resolve_relative_path(path)
            payload = self._validate_text_arg(content, "content")
        except ValueError as exc:
            return self._deny(str(exc))

        if self._protected(target):
            return self._deny("protected file cannot be edited")
        if target.exists():
            return self._error("file already exists")
        if len(payload.encode("utf-8")) > MAX_TEXT:
            return self._error("content exceeds 12,000 bytes")

        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(payload, encoding="utf-8")
        except OSError as exc:
            return self._error(str(exc))
        return {"status": "ok", "output": {"path": self._relative(target)}}

    def _run_edit_file(self, path, old, new):
        if not isinstance(path, str):
            return self._error("path must be a string")
        try:
            target = self._resolve_relative_path(path)
            old_text = self._validate_text_arg(old, "old")
            new_text = self._validate_text_arg(new, "new")
        except ValueError as exc:
            return self._deny(str(exc))

        if self._protected(target):
            return self._deny("protected file cannot be edited")
        if not target.exists() or not target.is_file():
            return self._error("file not found")

        try:
            original_bytes = target.read_bytes()
        except OSError as exc:
            return self._error(str(exc))

        if len(original_bytes) > MAX_TEXT:
            return self._error("file is larger than 12,000 bytes")

        if old_text == "":
            return self._error("old text must not be empty")

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return self._error("file is not valid UTF-8 text")

        count = content.count(old_text)
        if count != 1:
            return self._error("old text must occur exactly once")

        updated = content.replace(old_text, new_text, 1)
        try:
            target.write_text(updated, encoding="utf-8")
        except OSError as exc:
            return self._error(str(exc))
        return {"status": "ok", "output": {"path": self._relative(target)}}

    def _run_fetch_url(self, url):
        try:
            parsed = urllib.parse.urlparse(self._validate_text_arg(url, "url"))
        except ValueError as exc:
            return self._error(str(exc))

        if parsed.scheme != "https":
            return self._deny("only HTTPS URLs are allowed")
        if parsed.hostname != "docs.python.org":
            return self._deny("unapproved host")
        if parsed.username or parsed.password:
            return self._deny("credentials are not allowed in URLs")
        if parsed.query or parsed.fragment:
            return self._deny("query strings and fragments are not allowed")
        if parsed.port not in (None, 443):
            return self._deny("only the default HTTPS port is allowed")

        if self.offline:
            fixture = Path(__file__).resolve().parents[2] / "fixtures" / "decimal-offline.txt"
            if not fixture.exists():
                return self._error("offline fixture is missing")
            text = fixture.read_text(encoding="utf-8")
            return {
                "status": "ok",
                "output": {
                    "url": parsed.geturl(),
                    "content": text[:MAX_TEXT],
                    "truncated": len(text) > MAX_TEXT,
                    "source": "offline fixture",
                },
            }

        opener = urllib.request.build_opener(_NoRedirect)
        request = urllib.request.Request(parsed.geturl(), headers={"User-Agent": "agent-runtime/1.0"})
        try:
            with opener.open(request, timeout=10) as response:
                content_type = response.headers.get_content_type()
                if not content_type.startswith("text/") and content_type != "application/xhtml+xml":
                    return self._error("URL content type is not text or HTML")
                data = response.read(MAX_TEXT + 1)
        except Exception as exc:
            return self._error(f"fetch failed: {exc}")

        truncated = len(data) > MAX_TEXT
        payload = data[:MAX_TEXT]
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            text = payload.decode("utf-8", errors="replace")
        return {
            "status": "ok",
            "output": {
                "url": parsed.geturl(),
                "content": text,
                "truncated": truncated,
                "source": "live",
            },
        }

    def _run_bash(self, command):
        if self.mode != "edit":
            return self._deny("bash is disabled in read-only mode")

        try:
            cmd = self._validate_text_arg(command, "command")
        except ValueError as exc:
            return self._error(str(exc))

        if not self.approve(cmd, str(self.root)):
            return self._deny("bash was not approved")

        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", str(self.root)),
            "TERM": os.environ.get("TERM", "dumb"),
        }
        try:
            completed = subprocess.run(
                ["bash", "--noprofile", "--norc", "-lc", cmd],
                cwd=str(self.root),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=20,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            return self._error(f"bash timed out: {exc}")
        except (OSError, ValueError) as exc:
            return self._error(f"bash failed: {exc}")

        combined = (completed.stdout or "") + (completed.stderr or "")
        if len(combined) > MAX_TEXT:
            combined = combined[:MAX_TEXT]
            truncated = True
        else:
            truncated = False

        return {
            "status": "ok",
            "output": {
                "command": cmd,
                "cwd": str(self.root),
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "exit_code": completed.returncode,
                "truncated": truncated,
            },
        }

    def execute(self, action):
        """Validate one action, enforce policy, and return a result object."""
        if not isinstance(action, dict):
            return self._error("action must be a dictionary")

        tool = action.get("tool")
        args = action.get("args", {})
        if not isinstance(tool, str) or not tool:
            return self._error("tool must be a non-empty string")
        if tool not in TOOL_ARGUMENTS:
            return self._error(f"unknown tool: {tool}")
        if tool not in self.enabled:
            return self._deny(f"tool is disabled: {tool}")
        if tool not in self._allowed_tools():
            return self._deny(f"tool is not allowed in {self.mode} mode")
        if not isinstance(args, dict):
            return self._error("args must be a dictionary")
        expected = set(TOOL_ARGUMENTS[tool])
        received = set(args)
        if received != expected:
            return self._error(f"invalid arguments for {tool}: expected {sorted(expected)}, got {sorted(received)}")

        if tool == "list_files":
            return self._run_list_files()
        if tool == "read_file":
            return self._run_read_file(args["path"])
        if tool == "search_files":
            return self._run_search_files(args["query"])
        if tool == "write_file":
            return self._run_write_file(args["path"], args["content"])
        if tool == "edit_file":
            return self._run_edit_file(args["path"], args["old"], args["new"])
        if tool == "fetch_url":
            return self._run_fetch_url(args["url"])
        if tool == "bash":
            return self._run_bash(args["command"])
        return self._error(f"unsupported tool: {tool}")
