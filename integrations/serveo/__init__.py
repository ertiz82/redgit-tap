"""
Serveo tunnel integration for RedGit.

Exposes local ports to the internet via serveo.net.
Uses SSH for tunneling - no installation required, just SSH.
"""

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


class ServeoIntegration(TunnelBase):
    """Serveo tunnel integration using SSH."""

    name = "serveo"
    integration_type = IntegrationType.TUNNEL

    def __init__(self):
        super().__init__()
        self.subdomain = ""
        self._process = None
        self._public_url = None

    def setup(self, config: dict):
        """Setup serveo configuration."""
        self.subdomain = config.get("subdomain", "")
        self.enabled = True

    def start_tunnel(self, port: int, **kwargs) -> Optional[str]:
        """
        Start a serveo tunnel via SSH.

        Args:
            port: Local port to expose
            **kwargs: Additional options (subdomain)

        Returns:
            Public URL or None if failed
        """
        if not self.enabled:
            return None

        # Stop any existing tunnel
        self.stop_tunnel()

        subdomain = kwargs.get("subdomain", self.subdomain)

        try:
            # Build SSH command
            # ssh -R [subdomain:]80:localhost:PORT serveo.net
            if subdomain:
                remote_spec = f"{subdomain}:80:localhost:{port}"
            else:
                remote_spec = f"80:localhost:{port}"

            cmd = [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "ServerAliveInterval=60",
                "-R", remote_spec,
                "serveo.net"
            ]

            # Start SSH process
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True
            )

            # Wait for URL in output
            self._public_url = self._wait_for_url(timeout=30)

            if self._public_url:
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
        """Wait for the tunnel URL in SSH output."""
        if not self._process:
            return None

        start_time = time.time()
        # serveo outputs: "Forwarding HTTP traffic from https://xxx.serveo.net"
        url_pattern = re.compile(r'https://[a-z0-9-]+\.serveo\.net')

        while time.time() - start_time < timeout:
            if self._process.poll() is not None:
                break

            line = self._process.stdout.readline()
            if line:
                match = url_pattern.search(line)
                if match:
                    return match.group(0)

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

        # Check persisted state and kill that process too
        state = self._load_state()
        if state:
            pid = state.get("pid")
            if pid:
                try:
                    import os
                    os.kill(pid, 15)  # SIGTERM
                    stopped = True
                except (OSError, ProcessLookupError):
                    pass

        # Clear persisted state
        self._clear_state()

        # Kill any serveo SSH tunnels
        try:
            subprocess.run(
                ["pkill", "-f", "ssh.*serveo.net"],
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
            "subdomain": self.subdomain or "(random)"
        }

        # Add port info from persisted state
        state = self._load_state()
        if state:
            status["port"] = state.get("port")
            status["pid"] = state.get("pid")

        return status

    @staticmethod
    def after_install(config_values: dict) -> dict:
        """Post-install hook - no special setup needed for serveo."""
        import typer

        # Check if SSH is available
        try:
            result = subprocess.run(
                ["ssh", "-V"],
                capture_output=True,
                timeout=5
            )
            typer.echo("\n   SSH is available - serveo ready to use!")
            typer.echo("   Note: serveo.net uses SSH tunneling, no extra installation needed.")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            typer.secho("\n   Warning: SSH not found.", fg=typer.colors.YELLOW)

        return config_values