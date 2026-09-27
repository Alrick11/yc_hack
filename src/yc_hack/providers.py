"""Optional memory integrations with deterministic local fallbacks."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LocalPreferenceStore:
    """Small fallback store used when a provider is unavailable."""

    values: dict[str, list[str]] = field(default_factory=dict)

    def remember(self, agent_id: str, preference: str) -> None:
        self.values.setdefault(agent_id, []).append(preference)

    def recall(self, agent_id: str, query: str) -> list[str]:
        del query
        return list(self.values.get(agent_id, []))


class GBrainAdapter:
    """Use one GBrain CLI brain per participant, with a local fallback."""

    def __init__(self, command: str | None = None, fallback: LocalPreferenceStore | None = None):
        self.command = command or os.environ.get("GBRAIN_BIN") or self._default_command()
        self.fallback = fallback or LocalPreferenceStore()
        self.available = shutil.which(self.command) is not None or Path(self.command).exists()

    @staticmethod
    def _default_command() -> str:
        discovered = shutil.which("gbrain")
        if discovered:
            return discovered
        bun_binary = Path.home() / ".bun" / "bin" / "gbrain"
        return str(bun_binary) if bun_binary.exists() else "gbrain"

    def remember(self, agent_id: str, preference: str) -> None:
        self.fallback.remember(agent_id, preference)
        if not self.available:
            return
        args = [
            self.command,
            "remember",
            preference,
            "--provenance",
            f"yc_hack participant {agent_id}",
            "--kind",
            "preference",
            "--visibility",
            "private",
        ]
        try:
            subprocess.run(args, check=True, capture_output=True, text=True, timeout=20, env=self._agent_env(agent_id))
        except (OSError, subprocess.SubprocessError):
            self.available = False

    def recall(self, agent_id: str, query: str) -> list[str]:
        if self.available:
            try:
                result = subprocess.run(
                    [self.command, "search", query, "--limit", "20"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    env=self._agent_env(agent_id),
                )
                if result.stdout.strip():
                    return [result.stdout.strip()]
            except (OSError, subprocess.SubprocessError):
                self.available = False
        return self.fallback.recall(agent_id, query)

    def _agent_env(self, agent_id: str) -> dict[str, str]:
        env = os.environ.copy()
        root = os.environ.get("GBRAIN_HOME")
        if root:
            env["GBRAIN_HOME"] = str(Path(root) / agent_id)
        return env


class MemorableAdapter:
    """Submit sanitized traces to Memorable, or retain them locally."""

    def __init__(self, runtime_dir: str | Path = ".runtime/memorable"):
        self.api_key = os.environ.get("MEMORABLE_API_KEY")
        self.endpoint = os.environ.get(
            "MEMORABLE_URL",
            "https://memorable-extraction-api.memorable.workers.dev/v1/extract",
        )
        self.runtime_dir = Path(runtime_dir)
        self.enabled = bool(self.api_key)

    def record(self, session_id: str, task_description: str, tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "session_id": session_id,
            "harness": "yc-consensus-agent",
            "task_description": task_description[:200],
            "tool_calls": self._sanitize(tool_calls),
        }
        if self.enabled:
            request = urllib.request.Request(
                self.endpoint,
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    return {"mode": "memorable-api", "response": json.loads(response.read())}
            except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as error:
                payload["provider_error"] = type(error).__name__

        try:
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.runtime_dir = Path(tempfile.gettempdir()) / "yc_hack-memorable"
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
        trace_path = self.runtime_dir / f"{session_id}.json"
        try:
            trace_path.write_text(json.dumps(payload, indent=2) + "\n")
        except OSError:
            self.runtime_dir = Path(tempfile.gettempdir()) / "yc_hack-memorable"
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            trace_path = self.runtime_dir / f"{session_id}.json"
            trace_path.write_text(json.dumps(payload, indent=2) + "\n")
        return {"mode": "local-fallback", "path": str(trace_path)}

    @staticmethod
    def _sanitize(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        clean: list[dict[str, Any]] = []
        for call in tool_calls:
            clean.append({
                "name": str(call.get("name", "agent_decision"))[:80],
                "input": {"action": str(call.get("action", ""))[:400]},
                "result": {"ok": bool(call.get("ok", False))},
            })
        return clean
