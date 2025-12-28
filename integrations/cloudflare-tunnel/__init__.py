"""
Cloudflare Tunnel integration for RedGit.

Exposes local ports to the internet via Cloudflare Tunnels (cloudflared).
Provides secure, fast tunnels with Cloudflare's global network.
"""

import os
import json
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


class CloudflareTunnelIntegration(TunnelBase):
    """Cloudflare Tunnel integration for exposing local ports."""

    name = "cloudflare-tunnel"
    integration_type = IntegrationType.TUNNEL

    def __init__(self):
        super().__init__()
        self.tunnel_id = ""
        self._process = None
        self._public_url = None

    def setup(self, config: dict):
        """Setup Cloudflare Tunnel configuration."""
        self.tunnel_id = config.get("tunnel_id", "")

        # cloudflared can work without pre-configuration (quick tunnels)
        self.enabled = True

    def start_tunnel(self, port: int, **kwargs) -> Optional[str]:
        """
        Start a Cloudflare Tunnel to expose a local port.

        Uses 'cloudflared tunnel --url' for quick tunnels (no account needed)
        or named tunnels if tunnel_id is configured.

        Args:
            port: Local port to expose
            **kwargs: Additional options

        Returns:
            Public URL or None if failed
        """
        if not self.enabled:
            return None

        # Check if cloudflared is installed
        if not self._is_cloudflared_installed():
            return None

        # Stop any existing tunnel
        self.stop_tunnel()

        try:
            # Use quick tunnel (no account required)
            cmd = ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"]

            # Start cloudflared process
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

            # Failed to get URL
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
        """Wait for the tunnel URL to appear in cloudflared output."""
        if not self._process:
            return None

        start_time = time.time()
        url_pattern = re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com')

        while time.time() - start_time < timeout:
            if self._process.poll() is not None:
                # Process ended
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

        # Terminate our process if running
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
                    os.kill(pid, 15)  # SIGTERM
                    stopped = True
                except (OSError, ProcessLookupError):
                    pass

        # Clear persisted state
        self._clear_state()

        # Also kill any other cloudflared tunnel processes
        try:
            subprocess.run(
                ["pkill", "-f", "cloudflared tunnel"],
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
            "tunnel_id": self.tunnel_id or "(quick tunnel)"
        }

        # Add port info from persisted state
        state = self._load_state()
        if state:
            status["port"] = state.get("port")
            status["pid"] = state.get("pid")

        return status

    def _is_cloudflared_installed(self) -> bool:
        """Check if cloudflared is installed and available."""
        try:
            result = subprocess.run(
                ["cloudflared", "version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def after_install(config_values: dict) -> dict:
        """Post-install hook to verify cloudflared setup."""
        import typer

        # Check if cloudflared is installed
        try:
            result = subprocess.run(
                ["cloudflared", "version"],
                capture_output=True,
                timeout=5,
                text=True
            )
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                typer.echo(f"\n   cloudflared detected: {version}")
            else:
                typer.secho(
                    "\n   Warning: cloudflared not found.",
                    fg=typer.colors.YELLOW
                )
                typer.echo("   Install from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            typer.secho(
                "\n   Warning: cloudflared not found.",
                fg=typer.colors.YELLOW
            )
            typer.echo("   Install from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")

        return config_values