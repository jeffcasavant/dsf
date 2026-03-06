from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from dsf.config import DEFAULT_CONFIG_DIR, load_config
from dsf.container import ContainerManager
from dsf.db import TaskDb, TaskStatus

logger = logging.getLogger("dsf.worker")


def process_task(
    db: TaskDb,
    task: dict[str, Any],
    container: ContainerManager,
    log_dir: Path,
    workspace_dir: Path,
) -> None:
    """Process a single claimed task."""
    config = load_config()
    petname = task["petname"]
    name = task["name"]
    log_path = log_dir / f"task-{petname}.log"

    workspace = f"/workspace/{name}"
    host_workspace = workspace_dir / name
    host_workspace.mkdir(parents=True, exist_ok=True)

    try:
        # Init git repo and set remote
        container.exec_shell(f"mkdir -p {workspace} && cd {workspace} && git init")
        container.exec_shell(
            f"cd {workspace} && git remote add origin https://github.com/{task['github_repo']}.git"
        )

        # Run Claude Code
        result = container.run_claude(
            workspace=workspace,
            prompt=task["prompt"],
            gh_token=config.github_token,
            log_path=log_path,
        )

        if result.returncode != 0:
            db.update_status(
                petname, TaskStatus.FAILED, error=f"Claude exited with code {result.returncode}"
            )
            logger.error("Task %s failed: Claude exit code %d", petname, result.returncode)
            return

        # Push to GitHub
        db.update_status(petname, TaskStatus.PUSHING)
        container.exec_shell(
            f"cd {workspace} && git add -A && git commit -m 'DSF: {name}' --allow-empty"
        )
        push_result = container.exec_shell(f"cd {workspace} && git push -u origin HEAD")

        if push_result.returncode != 0:
            db.update_status(petname, TaskStatus.FAILED, error=f"Push failed: {push_result.stderr}")
            logger.error("Task %s push failed: %s", petname, push_result.stderr)
            return

        db.update_status(petname, TaskStatus.COMPLETED)
        logger.info("Task %s completed successfully", petname)

    except Exception as e:
        db.update_status(petname, TaskStatus.FAILED, error=str(e))
        logger.exception("Task %s failed with exception", petname)


def run_worker() -> None:
    """Main worker loop — polls DB for tasks and processes them."""
    config = load_config()
    log_dir = DEFAULT_CONFIG_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir = DEFAULT_CONFIG_DIR / "workspaces"

    logging.basicConfig(
        filename=str(log_dir / "worker.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db = TaskDb()
    container = ContainerManager(
        image_path=config.image_path,
        container_name=config.container_name,
    )

    if not container.is_running():
        logger.info("Starting container %s", config.container_name)
        container.start(
            claude_dir=Path.home() / ".claude",
            workspace_dir=workspace_dir,
        )

    logger.info("Worker started, polling every %ds", config.poll_interval)

    while True:
        task = db.claim_next()
        if task:
            logger.info("Claimed task %s (%s)", task["petname"], task["name"])
            process_task(
                db=db,
                task=task,
                container=container,
                log_dir=log_dir,
                workspace_dir=workspace_dir,
            )
        else:
            time.sleep(config.poll_interval)
