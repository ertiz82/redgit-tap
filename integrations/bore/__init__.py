"""
Bore tunnel integration for RedGit.

Exposes local ports to the internet via bore.pub.
A simple, fast, and secure tunnel written in Rust.
"""

import os
import subprocess
import time
import re
from typing import Optional, Dict, Any

try:
    from redgit.integrations.base import TunnelBase, IntegrationType
except ImportError:
    from enum import Enum

    class IntegrationType(Enum):
        TUNNEL = "tunnel"

    class TunnelBase:
        integration_type = IntegrationType.TUNNEL

        def __init__(self):
            self.enabled = False

        def setup(self, config):
            pass

        def start_tunnel(self, port: int, **kwargs) -> Optional[str]:
            pass

        def stop_tunnel(self) -> bool:
            pass

        def get_public_url(self) -> Optional[str]:
            pass

        def is_running(self) -> bool:
            return False

        def get_status(self) -> Dict[str, Any]:
            return {"running": False}


class BoreIntegration(TunnelBase):
    """Bore tunnel integration for exposing local ports."""

    name = "bore"
    integration_type = IntegrationType.TUNNEL

    def __init__(self):
        super().__init__()
        self.server = "bore.pub"
        self.secret = ""
        self._process = None
        self._public_url = None
        self._remote_port = None

    def setup(self, config: dict):
        """Setup bore configuration."""
        self.server = config.get("server", "bore.pub")
        self.secret = config.get("secret", "")
        self.enabled = True

    def start_tunnel(self, port: int, **kwargs) -> Optional[str]:
        """
        Start a bore tunnel to expose a local port.

        Args:
            port: Local port to expose
            **kwargs: Additional options

        Returns:
            Public URL or None if failed
        """
        if not self.enabled:
            return None

        if not self._is_bore_installed():
            return None

        # Stop any existing tunnel
        self.stop_tunnel()

        try:
            # Build command
            cmd = ["bore", "local", str(port), "--to", self.server]

            if self.secret:
                cmd.extend(["--secret", self.secret])

            # Start bore process
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True
            )

            # Wait for URL in output
            url_info = self._wait_for_url(timeout=30)

            if url_info:
                self._public_url = url_info
                # Save state for persistence
                self._save_state(self._process.pid, self._public_url, port)
                return self._public_url

            # Failed
            if self._process:
                self._process.terminate()
                self._process = None
            return None

        except Exception:
            if self._process:
                self._process.terminate()
                self._process = None
            return None

    def _wait_for_url(self, timeout: int = 30) -> Optional[str]:
        """Wait for the tunnel info in bore output."""
        if not self._process:
            return None

        start_time = time.time()
        # bore outputs: "listening at bore.pub:XXXXX"
        port_pattern = re.compile(r'listening at ([^\s:]+):(\d+)')

        while time.time() - start_time < timeout:
            if self._process.poll() is not None:
                break

            line = self._process.stdout.readline()
            if line:
                match = port_pattern.search(line)
                if match:
                    host = match.group(1)
                    port = match.group(2)
                    self._remote_port = port
                    # bore uses TCP, construct URL
                    return f"http://{host}:{port}"

            time.sleep(0.1)

        return None

    def stop_tunnel(self) -> bool:
        """Stop the active tunnel."""
        stopped = False

        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
                stopped = True
            except Exception:
                try:
                    self._process.kill()
                    stopped = True
                except Exception:
                    pass
            self._process = None

        self._public_url = None
        self._remote_port = None

        # Check persisted state and kill that process too
        state = self._load_state()
        if state:
            pid = state.get("pid")
            if pid:
                try:
                    os.kill(pid, 15)  # SIGTERM
                    stopped = True
                except (OSError, ProcessLookupError):
                    pass

        # Clear persisted state
        self._clear_state()

        # Kill any other bore processes
        try:
            subprocess.run(
                ["pkill", "-f", "bore local"],
                capture_output=True,
                timeout=5
            )
            stopped = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return stopped

    def get_public_url(self) -> Optional[str]:
        """Get the current public URL if tunnel is active."""
        # Check in-memory state first
        if self._public_url and self._process and self._process.poll() is None:
            return self._public_url

        # Check persisted state
        state = self._load_state()
        if state:
            pid = state.get("pid")
            if pid and self._is_process_running(pid):
                return state.get("url")
            else:
                # Process died, clear state
                self._clear_state()

        return None

    def get_status(self) -> Dict[str, Any]:
        """Get detailed tunnel status."""
        url = self.get_public_url()
        status = {
            "running": url is not None,
            "url": url,
            "integration": self.name,
            "server": self.server,
            "remote_port": self._remote_port
        }

        # Add port info from persisted state
        state = self._load_state()
        if state:
            status["port"] = state.get("port")
            status["pid"] = state.get("pid")

        return status

    def _is_bore_installed(self) -> bool:
        """Check if bore is installed."""
        try:
            result = subprocess.run(
                ["bore", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def after_install(config_values: dict) -> dict:
        """Post-install hook to verify bore setup."""
        import typer

        try:
            result = subprocess.run(
                ["bore", "--version"],
                capture_output=True,
                timeout=5,
                text=True
            )
            if result.returncode == 0:
                typer.echo(f"\n   bore detected: {result.stdout.strip()}")
            else:
                raise FileNotFoundError()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            typer.secho("\n   Warning: bore not found.", fg=typer.colors.YELLOW)
            typer.echo("   Install with: cargo install bore-cli")
            typer.echo("   Or download from: https://github.com/ekzhang/bore/releases")

        return config_values