#!/usr/bin/env python3
"""Portable Skill entry point using VeADK's existing managed task supervisor."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import stat
import uuid
from pathlib import Path

OWNER = "mpa-agent-create-skill"
DEFAULT_STATE = Path.home() / ".local/state/veadk/mpa-agent-create"


def emit(**event):
    print(json.dumps(event, ensure_ascii=False), flush=True)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="action", required=True)
    for action in ("plan", "create", "status", "retry"):
        command = commands.add_parser(action)
        command.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
        if action in {"plan", "create"}:
            command.add_argument("--name", required=True)
            command.add_argument("--description", default="")
            command.add_argument("--region", default="cn-beijing")
            command.add_argument("--request-id", required=action == "create")
            command.add_argument("--mpa-image", default="")
            command.add_argument("--worker-image", default="")
            command.add_argument("--openviking-url", default="")
            command.add_argument("--openviking-resource-id", default="")
        else:
            command.add_argument("--task-id", required=True)
        if action in {"create", "retry"}:
            command.add_argument(
                "--yes",
                action="store_true",
                required=True,
                help="Execute an explicitly authorized cloud creation/retry.",
            )
    return result


def canonical_id(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid request/task UUID") from None


def private_path(path: Path, *, directory=False, create=False):
    """Reject links and shared state; never chmod an unrelated existing path."""
    if path.is_symlink():
        raise ValueError("Unsafe state path")
    if not path.exists():
        if create and directory:
            path.mkdir(parents=True, mode=0o700, exist_ok=True)
        elif create:
            return
        else:
            raise ValueError("State or configuration snapshot is missing")
    info = path.lstat()
    if (
        (
            not stat.S_ISDIR(info.st_mode)
            if directory
            else not stat.S_ISREG(info.st_mode)
        )
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) & 0o077
    ):
        raise ValueError("State path must be private and owned by this user")


def prepare_state(root: Path, *, create=False):
    private_path(root, directory=True, create=create)
    profiles = root / "profiles"
    if create:
        private_path(profiles, directory=True, create=True)
    private_path(root / "tasks.sqlite3", create=create)
    # Failure can precede PG preparation; status/retry still need to work then.
    private_path(root / "pg-bootstrap.sqlite3", create=True)
    return root / "tasks.sqlite3"


def resources(payload):
    enabled = bool(payload.get("openvikingUrl") or payload.get("openvikingResourceId"))
    return {
        "openvikingUrl": payload.get("openvikingUrl", ""),
        "openvikingResourceId": payload.get("openvikingResourceId", ""),
        "openvikingApiKey": os.getenv("VEADK_MPA_SKILL_OPENVIKING_API_KEY", "")
        if enabled
        else "",
    }


def new_payload(args):
    from veadk.integrations.mpa.managed.config import validate_runtime_name

    request_id = canonical_id(args.request_id or str(uuid.uuid4()))
    name = validate_runtime_name(args.name)
    if len(args.description) > 2048:
        raise ValueError("Description exceeds 2048 characters")
    payload = {
        "requestId": request_id,
        "agentId": "mi-"
        + uuid.uuid5(uuid.NAMESPACE_URL, f"veadk:mpa:{OWNER}:{request_id}").hex[:24],
        "region": args.region,
        "name": name,
        "description": args.description,
    }
    for key, value in (
        ("runtimeImage", args.mpa_image),
        ("workerImage", args.worker_image),
        ("openvikingUrl", args.openviking_url),
        ("openvikingResourceId", args.openviking_resource_id),
    ):
        if value:
            payload[key] = value.strip()
    return payload


def profile_for(payload, root, *, snapshot=None):
    from veadk.integrations.mpa.managed.config import (
        load_profile,
        with_creation_images,
        with_creation_resources,
    )
    from veadk.integrations.mpa.managed.credentials import load_volcengine_credentials

    load_volcengine_credentials()
    profile = load_profile(snapshot, region=payload["region"])
    if profile.managed.postgres is None:
        raise ValueError("This Skill requires the managed PostgreSQL profile")
    profile.managed.postgres.bootstrap_path = str(root / "pg-bootstrap.sqlite3")
    images = profile.image_defaults()
    images.update(
        {key: payload[key] for key in ("runtimeImage", "workerImage") if key in payload}
    )
    profile = with_creation_images(profile, images)
    return with_creation_resources(profile, resources(payload))


def save_snapshot(path, root):
    from veadk.integrations.mpa.managed.studio_profile import studio_profile_values

    private_path(path, create=True)
    if path.exists():
        return
    raw = studio_profile_values()
    raw["managed"]["postgres"]["bootstrap-path"] = str(root / "pg-bootstrap.sqlite3")
    # The code-owned profile contains references, never resolved secret values.
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        private_path(path)
        return
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(raw, output)


def show_task(tasks, task):
    with tasks.db() as database:
        rows = database.execute(
            "SELECT operation,category,attempt,outcome FROM task_diagnostics WHERE task_id=? ORDER BY id DESC LIMIT 5",
            (task["taskId"],),
        ).fetchall()
    emit(
        type="task",
        **{
            key: task[key]
            for key in (
                "taskId",
                "requestId",
                "agentId",
                "state",
                "stage",
                "error",
                "result",
                "images",
            )
        },
        diagnostics=[dict(row) for row in reversed(rows)],
    )


async def execute(args):
    from veadk.integrations.mpa.managed.tasks import ACTIVE, CreationTasks

    root = args.state_dir.expanduser().absolute()
    payload = new_payload(args) if args.action in {"plan", "create"} else None
    if args.action == "plan":
        assert payload is not None
        profile = profile_for(payload, root)
        emit(
            type="plan",
            requestId=payload["requestId"],
            agentId=payload["agentId"],
            name=payload["name"],
            **profile.summary(),
            cloudVerified=False,
            openvikingEnabled=profile.openviking_enabled,
            prerequisites=[
                "cloud_product_enablement",
                "deployment_permissions",
                "model_access",
                "resource_quota",
                "database_endpoint_reachability",
            ],
        )
        return 0
    path = prepare_state(root, create=args.action == "create")
    tasks = CreationTasks(path)
    try:
        if payload is None:
            task = tasks.get(OWNER, canonical_id(args.task_id))
            if args.action == "status":
                show_task(tasks, task)
                return 0
            if task["state"] in ACTIVE | {"succeeded"}:
                show_task(tasks, task)
                return 0 if task["state"] == "succeeded" else 2
            payload = {
                key: task[key]
                for key in (
                    "requestId",
                    "agentId",
                    "region",
                    "name",
                    "description",
                    "runtimeImage",
                    "workerImage",
                    "openvikingUrl",
                    "openvikingResourceId",
                )
                if key in task
            }
        snapshot = root / "profiles" / (canonical_id(payload["requestId"]) + ".json")
        private_path(snapshot.parent, directory=True)
        if args.action == "create":
            # Validate before creating a persistent snapshot or dispatching work.
            private_path(snapshot, create=True)
            profile_for(payload, root, snapshot=snapshot if snapshot.exists() else None)
            save_snapshot(snapshot, root)
        else:
            private_path(snapshot)
        profile = profile_for(payload, root, snapshot=snapshot)
        task = await tasks.start(
            OWNER,
            payload,
            config_path=snapshot,
            timeout=profile.managed.timeout_seconds,
            images=profile.image_defaults(),
            secrets={"openvikingApiKey": resources(payload)["openvikingApiKey"]},
        )
        previous = None
        while True:
            task = tasks.get(OWNER, task["taskId"])
            state = (task["state"], task["stage"])
            if state != previous:
                show_task(tasks, task)
                previous = state
            if task["taskId"] not in tasks.running:
                return (
                    0
                    if task["state"] == "succeeded"
                    else (2 if task["state"] in ACTIVE else 1)
                )
            await asyncio.sleep(0.1)
    finally:
        await tasks.close()


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return asyncio.run(execute(args))
    except ImportError:
        emit(
            type="error",
            error="dependency_missing",
            detail="Install VeADK from the branch/release containing this Skill and its managed provisioning modules.",
        )
    except ValueError as error:
        from veadk.integrations.mpa.managed.config import ConfigurationError
        from veadk.integrations.mpa.managed.tasks import TaskError

        # Only these established safe exception classes may supply details.
        emit(
            type="error",
            error="invalid_configuration",
            detail=str(error)
            if isinstance(error, (ConfigurationError, TaskError))
            else "Check UUIDs, credentials, name and private state paths.",
        )
    except (OSError, sqlite3.Error):
        emit(
            type="error",
            error="state_unavailable",
            detail="Check the private state directory and saved configuration.",
        )
    except KeyboardInterrupt:
        emit(
            type="error",
            error="cancelled",
            detail="Creation stopped; preserve state and retry the same task.",
        )
        return 130
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
