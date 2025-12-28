"""
Localtunnel integration for RedGit.

Exposes local ports to the internet via localtunnel.me.
No signup required - just install and use.
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


class LocaltunnelIntegration(TunnelBase):
    """Localtunnel integration for exposing local ports."""

    name = "localtunnel"
    integration_type = IntegrationType.TUNNEL

    def __init__(self):
        super().__init__()
        self.subdomain = ""
        self.host = "https://localtunnel.me"
        self._process = None
        self._public_url = None

    def setup(self, config: dict):
        """Setup localtunnel configuration."""
        self.subdomain = config.get("subdomain", "")
        self.host = config.get("host", "https://localtunnel.me")
        self.enabled = True

    def start_tunnel(self, port: int, **kwargs) -> Optional[str]:
        """
        Start a localtunnel to expose a local port.

        Args:
            port: Local port to expose
            **kwargs: Additional options (subdomain)

        Returns:
            Public URL or None if failed
        """
        if not self.enabled:
            return None

        # Check if lt is installed
        if not self._is_lt_installed():
            return None

        # Stop any existing tunnel
        self.stop_tunnel()

        # Get subdomain
        subdomain = kwargs.get("subdomain", self.subdomain)

        try:
            # Build command
            cmd = ["lt", "--port", str(port)]

            if subdomain:
                cmd.extend(["--subdomain", subdomain])

            if self.host != "https://localtunnel.me":
                cmd.extend(["--host", self.host])

            # Start lt process
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
        """Wait for the tunnel URL to appear in lt output."""
        if not self._process:
            return None

        start_time = time.time()
        url_pattern = re.compile(r'https://[a-z0-9-]+\.loca\.lt')

        while time.time() - start_time < timeout:
            if self._process.poll() is not None:
                # Process ended
                break

            line = self._process.stdout.readline()
            if line:
                # localtunnel outputs: "your url is: https://xxx.loca.lt"
                match = url_pattern.search(line)
                if match:
                    return match.group(0)

                # Also check for custom host URLs
                if "your url is:" in line.lower():
                    url_match = re.search(r'https?://[^\s]+', line)
                    if url_match:
                        return url_match.group(0)

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
                    os.kill(pid, 15)  # SIGTERM
                    stopped = True
                except (OSError, ProcessLookupError):
                    pass

        # Clear persisted state
        self._clear_state()

        # Kill any other lt processes
        try:
            subprocess.run(
                ["pkill", "-f", "^lt --port"],
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

    def _is_lt_installed(self) -> bool:
        """Check if localtunnel (lt) is installed."""
        try:
            result = subprocess.run(
                ["lt", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Try with npx
            try:
                result = subprocess.run(
                    ["npx", "localtunnel", "--version"],
                    capture_output=True,
                    timeout=10
                )
                return result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return False

    @staticmethod
    def after_install(config_values: dict) -> dict:
        """Post-install hook to verify localtunnel setup."""
        import typer

        # Check if lt is installed
        try:
            result = subprocess.run(
                ["lt", "--version"],
                capture_output=True,
                timeout=5,
                text=True
            )
            if result.returncode == 0:
                typer.echo(f"\n   localtunnel detected: {result.stdout.strip()}")
            else:
                raise FileNotFoundError()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            typer.secho(
                "\n   Warning: localtunnel (lt) not found.",
                fg=typer.colors.YELLOW
            )
            typer.echo("   Install with: npm install -g localtunnel")
            typer.echo("   Or use with npx: npx localtunnel --port 8080")

        return config_values