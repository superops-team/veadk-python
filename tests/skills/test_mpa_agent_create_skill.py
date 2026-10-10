"""Portable creation Skill contracts; all cloud work uses isolated fake children."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest

from veadk.integrations.mpa.managed.tasks import CreationTasks

SCRIPT = Path(__file__).parents[2] / "skills/mpa-agent-create/scripts/create_mpa.py"
REQUEST = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def helper(monkeypatch):
    for key in tuple(os.environ):
        if key.startswith(("VOLC", "VEADK_STUDIO_MPA", "VEADK_MPA_", "OPENVIKING")):
            monkeypatch.delenv(key)
    monkeypatch.setenv("VOLCENGINE_ACCESS_KEY", "fixture-access-value")
    monkeypatch.setenv("VOLCENGINE_SECRET_KEY", "fixture-secret-value")
    monkeypatch.setenv("VEADK_MPA_CONFIG_MODEL_AGENT_API_KEY", "fixture-model-value")
    spec = importlib.util.spec_from_file_location("mpa_creation_skill", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def arguments(tmp_path, action="plan", *extra):
    common = [action, "--state-dir", str(tmp_path / "state")]
    if action in {"plan", "create"}:
        common += ["--name", "Support-Agent", "--request-id", REQUEST]
    return common + list(extra)


def events(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def fake_child(monkeypatch, *, fail=False, received=None):
    program = (
        "import json,sys; d=json.load(sys.stdin); "
        "print('private-sdk-output-that-must-be-hidden'); "
        "print('MPA_EVENT '+json.dumps({'stage':'worker'}),flush=True); "
    )
    if received:
        program += f"from pathlib import Path; Path({str(received)!r}).write_text(json.dumps(d)); "
    if fail:
        program += "sys.exit(1)"
    else:
        program += (
            "r=dict(runtime_id='r-test',skill_space_id='ss-test',gateway_id='gw-test',"
            "agent_id=d['agentId'],region=d['region'],state='ready'); "
            "print('MPA_EVENT '+json.dumps({'result':r}),flush=True)"
        )
    monkeypatch.setattr(
        CreationTasks, "command", lambda _: [sys.executable, "-c", program]
    )


def test_plan_is_local_preserves_ids_and_does_not_write_state(
    helper, tmp_path, capsys, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("plan started a task/cloud process")

    monkeypatch.setattr(CreationTasks, "start", forbidden)
    assert helper.main(arguments(tmp_path)) == 0
    first = events(capsys)[0]
    assert first["type"] == "plan"
    assert first["agentId"].startswith("mi-") and len(first["agentId"]) == 27
    assert first["runtimeImage"].endswith("/mpa/mpa_agent:latest")
    assert first["workerImage"].endswith("/mpa/mpa_codex_worker:latest")
    assert first["cloudVerified"] is False
    assert helper.main(arguments(tmp_path)) == 0
    assert events(capsys)[0]["agentId"] == first["agentId"]
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize(
    "extra", [["--name", "中文"], ["--region", "cn-shanghai"], ["--request-id", "bad"]]
)
def test_invalid_plan_stops_before_state_or_cloud(helper, tmp_path, capsys, extra):
    assert helper.main(arguments(tmp_path, "plan", *extra)) != 0
    assert events(capsys)[0]["type"] == "error"
    assert not (tmp_path / "state").exists()


def test_missing_model_key_and_cloud_credentials_are_safe(
    helper, tmp_path, monkeypatch, capsys
):
    monkeypatch.delenv("VEADK_MPA_CONFIG_MODEL_AGENT_API_KEY")
    assert helper.main(arguments(tmp_path)) == 1
    output = events(capsys)
    assert "fixture-" not in str(output)
    monkeypatch.setenv("VEADK_MPA_CONFIG_MODEL_AGENT_API_KEY", "fixture-model-value")
    monkeypatch.delenv("VOLCENGINE_ACCESS_KEY")
    monkeypatch.delenv("VOLCENGINE_SECRET_KEY")
    monkeypatch.setattr(
        "veadk.integrations.mpa.managed.credentials.load_volcengine_credentials",
        lambda: (_ for _ in ()).throw(ValueError("do-not-echo")),
    )
    assert helper.main(arguments(tmp_path)) == 1
    assert "do-not-echo" not in str(events(capsys))


def test_create_requires_authorization_flag(helper, tmp_path):
    with pytest.raises(SystemExit) as error:
        helper.main(arguments(tmp_path, "create"))
    assert error.value.code == 2
    assert not (tmp_path / "state").exists()


def test_success_and_duplicate_use_one_task_and_private_nonsecret_state(
    helper, tmp_path, monkeypatch, capsys
):
    received = tmp_path / "received.json"
    fake_child(monkeypatch, received=received)
    assert helper.main(arguments(tmp_path, "create", "--yes")) == 0
    output = events(capsys)
    final = output[-1]
    assert final["state"] == "succeeded" and final["result"]["state"] == "ready"
    assert "private-sdk-output" not in str(output)
    data = json.loads(received.read_text())
    assert data["name"] == "Support-Agent" and data["owner"] == helper.OWNER
    snapshot = Path(data["config"])
    raw = json.loads(snapshot.read_text())
    assert raw["managed"]["postgres"]["bootstrap-path"] == str(
        tmp_path / "state/pg-bootstrap.sqlite3"
    )
    assert raw["model-api-key"] == "${VEADK_MPA_CONFIG_MODEL_AGENT_API_KEY}"
    state = tmp_path / "state"
    assert stat.S_IMODE(state.stat().st_mode) == 0o700
    for path in state.rglob("*"):
        if path.is_file():
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
            assert b"fixture-model-value" not in path.read_bytes()
            assert b"fixture-secret-value" not in path.read_bytes()
    assert helper.main(arguments(tmp_path, "create", "--yes")) == 0
    assert events(capsys)[-1]["taskId"] == final["taskId"]


def test_failed_retry_reuses_snapshot_images_input_and_reinjects_ov_key(
    helper, tmp_path, monkeypatch, capsys
):
    received = tmp_path / "received.json"
    monkeypatch.setenv("VEADK_MPA_SKILL_OPENVIKING_API_KEY", "fixture-ov-value")
    fake_child(monkeypatch, fail=True)
    extra = [
        "--yes",
        "--mpa-image",
        "example.com/mpa:fixed",
        "--openviking-url",
        "https://ov.example.com",
        "--openviking-resource-id",
        "ov-test",
    ]
    assert helper.main(arguments(tmp_path, "create", *extra)) == 1
    first = events(capsys)[-1]
    monkeypatch.delenv("VEADK_MPA_SKILL_OPENVIKING_API_KEY")
    assert (
        helper.main(arguments(tmp_path, "retry", "--task-id", first["taskId"], "--yes"))
        == 1
    )
    assert events(capsys)[-1]["type"] == "error"
    monkeypatch.setenv("VEADK_MPA_SKILL_OPENVIKING_API_KEY", "fixture-ov-value")
    fake_child(monkeypatch, received=received)
    assert (
        helper.main(arguments(tmp_path, "retry", "--task-id", first["taskId"], "--yes"))
        == 0
    )
    final = events(capsys)[-1]
    assert final["taskId"] == first["taskId"] and final["agentId"] == first["agentId"]
    assert final["images"]["runtimeImage"] == "example.com/mpa:fixed"
    data = json.loads(received.read_text())
    assert data["resources"]["openvikingApiKey"] == "fixture-ov-value"
    assert data["resources"]["openvikingUrl"] == "https://ov.example.com"
    for path in (tmp_path / "state").rglob("*"):
        if path.is_file():
            assert b"fixture-ov-value" not in path.read_bytes()
    assert "fixture-ov-value" not in str(final)


def test_status_does_not_require_model_or_cloud_credentials(
    helper, tmp_path, monkeypatch, capsys
):
    fake_child(monkeypatch, fail=True)
    assert helper.main(arguments(tmp_path, "create", "--yes")) == 1
    task = events(capsys)[-1]
    for key in (
        "VOLCENGINE_ACCESS_KEY",
        "VOLCENGINE_SECRET_KEY",
        "VEADK_MPA_CONFIG_MODEL_AGENT_API_KEY",
    ):
        monkeypatch.delenv(key)
    assert helper.main(arguments(tmp_path, "status", "--task-id", task["taskId"])) == 0
    assert events(capsys)[-1]["state"] == "failed"


def test_changed_request_and_missing_snapshot_do_not_start_child(
    helper, tmp_path, monkeypatch, capsys
):
    fake_child(monkeypatch, fail=True)
    assert helper.main(arguments(tmp_path, "create", "--yes")) == 1
    task = events(capsys)[-1]
    assert (
        helper.main(arguments(tmp_path, "create", "--yes", "--name", "Changed-Agent"))
        == 1
    )
    assert events(capsys)[-1]["type"] == "error"
    (tmp_path / f"state/profiles/{REQUEST}.json").unlink()
    assert (
        helper.main(arguments(tmp_path, "retry", "--task-id", task["taskId"], "--yes"))
        == 1
    )
    assert events(capsys)[-1]["type"] == "error"


@pytest.mark.parametrize("target", ["root", "database", "snapshot"])
def test_unsafe_state_symlinks_are_rejected(helper, tmp_path, capsys, target):
    state = tmp_path / "state"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(mode=0o700)
    if target == "root":
        state.symlink_to(elsewhere, target_is_directory=True)
    else:
        state.mkdir(mode=0o700)
        if target == "database":
            (state / "tasks.sqlite3").symlink_to(elsewhere / "db")
        else:
            (state / "profiles").mkdir(mode=0o700)
            (state / f"profiles/{REQUEST}.json").symlink_to(elsewhere / "profile")
    assert helper.main(arguments(tmp_path, "create", "--yes")) == 1
    assert events(capsys)[-1]["type"] == "error"
    assert not list(elsewhere.iterdir())


def test_running_task_is_reported_without_replacement(
    helper, tmp_path, monkeypatch, capsys
):
    fake_child(monkeypatch)
    assert helper.main(arguments(tmp_path, "create", "--yes")) == 0
    task = events(capsys)[-1]
    db = CreationTasks(tmp_path / "state/tasks.sqlite3")
    db._update(task["taskId"], state="running", supervisor=os.getpid())
    monkeypatch.setattr(
        CreationTasks, "command", lambda _: pytest.fail("spawned a duplicate")
    )
    assert (
        helper.main(arguments(tmp_path, "retry", "--task-id", task["taskId"], "--yes"))
        == 2
    )
    assert events(capsys)[-1]["state"] == "running"


def test_cancellation_closes_child_and_preserves_recovery_state(
    helper, tmp_path, monkeypatch
):
    pid_file = tmp_path / "pid"
    program = f"import os,time; from pathlib import Path; Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(60)"
    monkeypatch.setattr(
        CreationTasks, "command", lambda _: [sys.executable, "-c", program]
    )

    async def check():
        args = helper.parser().parse_args(arguments(tmp_path, "create", "--yes"))
        task = asyncio.create_task(helper.execute(args))
        while not pid_file.exists() or not pid_file.read_text():
            await asyncio.sleep(0.01)
        pid = int(pid_file.read_text())
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
        db = CreationTasks(tmp_path / "state/tasks.sqlite3")
        with db.db() as connection:
            row = connection.execute("SELECT state FROM tasks").fetchone()
        assert row["state"] == "cancelled"

    asyncio.run(check())


def test_retry_keeps_profile_when_builtin_defaults_change(
    helper, tmp_path, monkeypatch, capsys
):
    fake_child(monkeypatch, fail=True)
    assert helper.main(arguments(tmp_path, "create", "--yes")) == 1
    task = events(capsys)[-1]
    monkeypatch.setattr(
        "veadk.integrations.mpa.managed.config.studio_profile_values",
        lambda: pytest.fail("retry loaded new defaults instead of the snapshot"),
    )
    monkeypatch.setattr(
        "veadk.integrations.mpa.managed.studio_profile.studio_profile_values",
        lambda: pytest.fail("retry rewrote the saved profile"),
    )
    fake_child(monkeypatch)
    assert (
        helper.main(arguments(tmp_path, "retry", "--task-id", task["taskId"], "--yes"))
        == 0
    )
    final = events(capsys)[-1]
    assert final["images"] == task["images"]


@pytest.mark.parametrize(
    "extra",
    [
        ["--openviking-url", "https://ov.example.com"],
        [
            "--openviking-url",
            "http://ov.example.com",
            "--openviking-resource-id",
            "ov-test",
        ],
        ["--mpa-image", "not a valid image"],
        ["--description", "x" * 2049],
    ],
)
def test_invalid_optional_configuration_never_dispatches(
    helper, tmp_path, capsys, monkeypatch, extra
):
    monkeypatch.setenv("VEADK_MPA_SKILL_OPENVIKING_API_KEY", "fixture-ov-value")
    monkeypatch.setattr(
        CreationTasks,
        "start",
        lambda *a, **kw: pytest.fail("dispatched invalid inputs"),
    )
    assert helper.main(arguments(tmp_path, "plan", *extra)) == 1
    assert events(capsys)[-1]["type"] == "error"


def test_unused_ov_key_is_not_injected_and_new_plan_has_new_identity(
    helper, tmp_path, capsys, monkeypatch
):
    monkeypatch.setenv("VEADK_MPA_SKILL_OPENVIKING_API_KEY", "fixture-ov-value")
    args = arguments(tmp_path)
    args = args[:-2]
    assert helper.main(args) == 0
    first = events(capsys)[0]
    assert first["openvikingEnabled"] is False
    assert helper.resources({})["openvikingApiKey"] == ""
    assert helper.main(args) == 0
    assert events(capsys)[0]["agentId"] != first["agentId"]


def test_dead_supervisor_can_resume_without_new_request(
    helper, tmp_path, monkeypatch, capsys
):
    fake_child(monkeypatch, fail=True)
    assert helper.main(arguments(tmp_path, "create", "--yes")) == 1
    task = events(capsys)[-1]
    db = CreationTasks(tmp_path / "state/tasks.sqlite3")
    db._update(task["taskId"], state="running", supervisor=2**30)
    fake_child(monkeypatch)
    assert (
        helper.main(arguments(tmp_path, "retry", "--task-id", task["taskId"], "--yes"))
        == 0
    )
    final = events(capsys)[-1]
    assert final["taskId"] == task["taskId"] and final["agentId"] == task["agentId"]


def test_zip_is_accepted_by_studio_skill_archive_validator():
    import io
    import zipfile
    from frontend.server.skills.archive import validate_skill_archive

    root = SCRIPT.parent.parent
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(
                    path, (Path(root.name) / path.relative_to(root)).as_posix()
                )
    result = validate_skill_archive(data.getvalue())
    assert result.name == "mpa-agent-create"
    assert any(file["path"] == "scripts/create_mpa.py" for file in result.files)
