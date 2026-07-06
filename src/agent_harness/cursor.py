"""Subprocess wrapper around the Cursor headless CLI (`agent -p`).

Contract (per cursor.com/docs/cli, 2026-07):
- success → exit 0 and a JSON result object on stdout (or NDJSON events in
  stream-json mode ending with a `result` event);
- failure → non-zero exit, errors on stderr, no parseable JSON. Exit code is
  therefore the primary signal.
- File edits only happen with --force; read-only stages use --mode plan.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_JSON_FENCE = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)


class AgentError(RuntimeError):
    """The agent process failed (non-zero exit or unparseable output)."""


@dataclass
class AgentResult:
    text: str
    session_id: str | None
    duration_ms: int | None = None


def extract_json_payload(text: str) -> dict | list:
    """Pull the structured payload out of an agent's answer.

    Skills are instructed to end with exactly one fenced ```json block; we
    take the last one. A bare-JSON answer is accepted too.
    """
    blocks = _JSON_FENCE.findall(text)
    candidate = blocks[-1] if blocks else text
    return json.loads(candidate)


class CursorAgent:
    def __init__(self, bin_name: str = "agent", model: str = "auto") -> None:
        self.bin = bin_name
        self.model = model

    def available(self) -> bool:
        return shutil.which(self.bin) is not None

    def _base_cmd(
        self,
        prompt: str,
        *,
        output_format: str,
        mode: str | None,
        force: bool,
        resume: str | None,
        workspace: Path | None,
        worktree: str | None,
        worktree_base: str | None,
    ) -> list[str]:
        cmd = [self.bin, "-p", "--output-format", output_format, "--trust", "--model", self.model]
        if mode:
            cmd += ["--mode", mode]
        if force:
            cmd.append("--force")
        if resume:
            cmd += ["--resume", resume]
        if workspace:
            cmd += ["--workspace", str(workspace)]
        if worktree:
            cmd += ["--worktree", worktree]
        if worktree_base:
            cmd += ["--worktree-base", worktree_base]
        cmd.append(prompt)
        return cmd

    def run(
        self,
        prompt: str,
        *,
        mode: str | None = None,
        force: bool = False,
        resume: str | None = None,
        workspace: Path | None = None,
        worktree: str | None = None,
        worktree_base: str | None = None,
        timeout: int = 1800,
    ) -> AgentResult:
        """One blocking invocation with `--output-format json`."""
        cmd = self._base_cmd(
            prompt,
            output_format="json",
            mode=mode,
            force=force,
            resume=resume,
            workspace=workspace,
            worktree=worktree,
            worktree_base=worktree_base,
        )
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, env=os.environ.copy()
            )
        except subprocess.TimeoutExpired as e:
            raise AgentError(f"agent timed out after {timeout}s") from e
        if proc.returncode != 0:
            raise AgentError(
                f"agent exited {proc.returncode}: {proc.stderr.strip()[:2000] or '(no stderr)'}"
            )
        # Docs promise a single JSON object; tolerate stray leading output by
        # falling back to the last line.
        stdout = proc.stdout.strip()
        try:
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError:
                payload = json.loads(stdout.splitlines()[-1])
        except (json.JSONDecodeError, IndexError) as e:
            raise AgentError(f"agent exited 0 but stdout was not JSON: {proc.stdout[:500]}") from e
        if payload.get("is_error"):
            raise AgentError(f"agent reported error result: {payload.get('result', '')[:2000]}")
        return AgentResult(
            text=payload.get("result", ""),
            session_id=payload.get("session_id"),
            duration_ms=payload.get("duration_ms"),
        )

    def run_streaming(
        self,
        prompt: str,
        *,
        transcript_path: Path,
        on_event: Callable[[dict], None] | None = None,
        mode: str | None = None,
        force: bool = False,
        resume: str | None = None,
        workspace: Path | None = None,
        worktree: str | None = None,
        worktree_base: str | None = None,
    ) -> AgentResult:
        """Invocation with `--output-format stream-json`.

        Every NDJSON event is appended raw to `transcript_path` and passed to
        `on_event` (for live terminal narration). Returns when the terminal
        `result` event arrives.
        """
        cmd = self._base_cmd(
            prompt,
            output_format="stream-json",
            mode=mode,
            force=force,
            resume=resume,
            workspace=workspace,
            worktree=worktree,
            worktree_base=worktree_base,
        )
        result_event: dict | None = None
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        # stderr goes to a sidecar file, not a pipe: we only drain stdout, and
        # a filling stderr pipe would deadlock a chatty agent.
        stderr_path = transcript_path.with_suffix(".stderr.log")
        with (
            transcript_path.open("a", encoding="utf-8") as transcript,
            stderr_path.open("w", encoding="utf-8") as stderr_file,
            subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=stderr_file,
                text=True,
                env=os.environ.copy(),
            ) as proc,
        ):
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                transcript.write(line + "\n")
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if on_event:
                    on_event(event)
                if event.get("type") == "result":
                    result_event = event
        stderr = stderr_path.read_text(encoding="utf-8") if stderr_path.exists() else ""
        if proc.returncode != 0 or result_event is None:
            raise AgentError(
                f"agent exited {proc.returncode} without a success result: "
                f"{stderr.strip()[:2000] or '(no stderr)'}"
            )
        if result_event.get("is_error"):
            raise AgentError(
                f"agent reported error result: {result_event.get('result', '')[:2000]}"
            )
        return AgentResult(
            text=result_event.get("result", ""),
            session_id=result_event.get("session_id"),
            duration_ms=result_event.get("duration_ms"),
        )

    def run_json(self, prompt: str, **kwargs) -> tuple[dict | list, AgentResult]:
        """run() + payload extraction, with one repair round-trip on bad JSON."""
        result = self.run(prompt, **kwargs)
        try:
            return extract_json_payload(result.text), result
        except json.JSONDecodeError:
            retry_kwargs = dict(kwargs)
            retry_kwargs["resume"] = result.session_id or kwargs.get("resume")
            # Worktree was already created by the first call; don't recreate.
            retry_kwargs.pop("worktree", None)
            retry_kwargs.pop("worktree_base", None)
            result = self.run(
                "Your previous answer was not parseable. Re-emit ONLY the fenced ```json block, "
                "no prose, matching the schema you were given.",
                **retry_kwargs,
            )
            return extract_json_payload(result.text), result
