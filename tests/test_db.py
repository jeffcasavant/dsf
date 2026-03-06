from pathlib import Path

from dsf.db import TaskDb, TaskStatus


def test_create_and_get_task(tmp_path: Path) -> None:
    db = TaskDb(tmp_path / "tasks.db")
    petname = db.create_task(name="my-app", prompt="Build a web app", github_repo="jeff/my-app")
    task = db.get_task(petname)
    assert task is not None
    assert task["name"] == "my-app"
    assert task["prompt"] == "Build a web app"
    assert task["github_repo"] == "jeff/my-app"
    assert task["status"] == "submitted"


def test_list_tasks(tmp_path: Path) -> None:
    db = TaskDb(tmp_path / "tasks.db")
    db.create_task(name="app1", prompt="Build app 1", github_repo="jeff/app1")
    db.create_task(name="app2", prompt="Build app 2", github_repo="jeff/app2")
    tasks = db.list_tasks()
    assert len(tasks) == 2


def test_claim_next_task(tmp_path: Path) -> None:
    db = TaskDb(tmp_path / "tasks.db")
    db.create_task(name="app1", prompt="Build app 1", github_repo="jeff/app1")
    task = db.claim_next()
    assert task is not None
    assert task["status"] == "running"
    assert task["started_at"] is not None
    # No more tasks to claim
    assert db.claim_next() is None


def test_complete_task(tmp_path: Path) -> None:
    db = TaskDb(tmp_path / "tasks.db")
    petname = db.create_task(name="app1", prompt="Build app 1", github_repo="jeff/app1")
    db.claim_next()
    db.update_status(petname, TaskStatus.COMPLETED)
    task = db.get_task(petname)
    assert task is not None
    assert task["status"] == "completed"
    assert task["completed_at"] is not None


def test_fail_task(tmp_path: Path) -> None:
    db = TaskDb(tmp_path / "tasks.db")
    petname = db.create_task(name="app1", prompt="Build app 1", github_repo="jeff/app1")
    db.claim_next()
    db.update_status(petname, TaskStatus.FAILED, error="something broke")
    task = db.get_task(petname)
    assert task is not None
    assert task["status"] == "failed"
    assert task["error"] == "something broke"


def test_petnames_are_unique(tmp_path: Path) -> None:
    db = TaskDb(tmp_path / "tasks.db")
    petnames = set()
    for i in range(20):
        pn = db.create_task(name=f"app{i}", prompt=f"Build app {i}", github_repo=f"jeff/app{i}")
        petnames.add(pn)
    assert len(petnames) == 20
