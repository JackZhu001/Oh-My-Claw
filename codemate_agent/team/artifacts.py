"""
Artifact helpers for team task handoff.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def ensure_artifact_dir(workspace_dir: Path, task_id: int | str) -> Path:
    root = Path(workspace_dir).resolve() / ".team" / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    task_dir = root / f"task_{str(task_id).strip()}"
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def list_artifacts(artifact_dir: Path) -> list[str]:
    base = Path(artifact_dir)
    if not base.exists():
        return []
    files: list[str] = []
    for path in sorted(base.rglob("*")):
        if path.is_file():
            files.append(str(path))
    return files


def build_artifact_manifest(artifact_dir: Path) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for file_path in list_artifacts(artifact_dir):
        path = Path(file_path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        manifest.append(
            {
                "path": str(path),
                "size": path.stat().st_size,
                "kind": path.suffix.lstrip(".") or "file",
                "checksum": digest,
            }
        )
    return manifest


def manifest_path(artifact_dir: Path) -> Path:
    return Path(artifact_dir) / "manifest.json"


def write_manifest(
    artifact_dir: Path,
    *,
    task_id: int | str,
    agent_id: str,
    request_id: str,
    status: str,
    summary: str,
    extra: dict[str, Any] | None = None,
) -> Path:
    base = Path(artifact_dir)
    base.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_id": task_id,
        "agent_id": agent_id,
        "request_id": request_id,
        "status": status,
        "summary": summary,
        "artifacts": build_artifact_manifest(base),
        "extra": dict(extra or {}),
    }
    path = manifest_path(base)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_manifest(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
