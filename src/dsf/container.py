from __future__ import annotations

import subprocess
from pathlib import Path

DEFAULT_IMAGE_PATH = Path("/var/lib/machines/dsf-factory")
CONTAINER_PACKAGES = ["base", "base-devel", "git", "github-cli", "nodejs", "npm"]


class ContainerManager:
    def __init__(
        self,
        image_path: Path = DEFAULT_IMAGE_PATH,
        container_name: str = "dsf-factory",
    ) -> None:
        self.image_path = image_path
        self.container_name = container_name

    def bootstrap(self) -> None:
        """Create the container rootfs with pacstrap."""
        self.image_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["pacstrap", "-c", str(self.image_path)] + CONTAINER_PACKAGES,
            check=True,
        )
        # Install Claude Code inside the container
        subprocess.run(
            [
                "systemd-nspawn",
                "-D",
                str(self.image_path),
                "npm",
                "install",
                "-g",
                "@anthropic-ai/claude-code",
            ],
            check=True,
        )
        # Create worker user
        subprocess.run(
            [
                "systemd-nspawn",
                "-D",
                str(self.image_path),
                "useradd",
                "-m",
                "-s",
                "/bin/bash",
                "worker",
            ],
            check=True,
        )

    def start(self, claude_dir: Path, workspace_dir: Path) -> None:
        """Boot the container with bind mounts."""
        workspace_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "systemd-nspawn",
                "--boot",
                "--machine",
                self.container_name,
                "-D",
                str(self.image_path),
                f"--bind-ro={claude_dir}:/home/worker/.claude",
                f"--bind={workspace_dir}:/workspace",
            ],
            check=True,
        )

    def stop(self) -> None:
        """Shutdown the container."""
        subprocess.run(
            ["machinectl", "terminate", self.container_name],
            check=True,
        )

    def is_running(self) -> bool:
        """Check if the container is currently running."""
        result = subprocess.run(
            ["machinectl", "list", "--no-legend", "--no-pager"],
            capture_output=True,
            text=True,
        )
        return self.container_name in result.stdout

    def run_claude(
        self,
        workspace: str,
        prompt: str,
        gh_token: str,
        log_path: Path,
    ) -> subprocess.CompletedProcess[str]:
        """Run Claude Code inside the container for a task."""
        cmd = [
            "machinectl",
            "shell",
            f"--setenv=GH_TOKEN={gh_token}",
            "--setenv=HOME=/home/worker",
            f"worker@{self.container_name}",
            "/usr/bin/bash",
            "-c",
            f"cd {workspace} && claude --dangerously-skip-permissions -p {_shell_quote(prompt)}",
        ]
        with open(log_path, "w") as log_file:
            result = subprocess.run(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )
        return result

    def exec_shell(self, command: str) -> subprocess.CompletedProcess[str]:
        """Run an arbitrary command in the container as worker."""
        return subprocess.run(
            [
                "machinectl",
                "shell",
                f"worker@{self.container_name}",
                "/usr/bin/bash",
                "-c",
                command,
            ],
            capture_output=True,
            text=True,
        )

    def destroy(self) -> None:
        """Remove the container image."""
        if self.is_running():
            self.stop()
        subprocess.run(["rm", "-rf", str(self.image_path)], check=True)


def _shell_quote(s: str) -> str:
    """Single-quote a string for shell use."""
    return "'" + s.replace("'", "'\\''") + "'"
