"""
Ngrok tunnel integration for RedGit.

Exposes local ports to the internet via ngrok tunnels.
Used for webhook callbacks, planning poker sessions, and other remote access needs.
"""

import os
import json
import subprocess
import time
from typing import Optional, Dict, Any
from urllib.request import urlopen
from urllib.error import URLError

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


class NgrokIntegration(TunnelBase):
    """Ngrok tunnel integration for exposing local ports to the internet."""

    name = "ngrok"
    integration_type = IntegrationType.TUNNEL

    def __init__(self):
        super().__init__()
        self.auth_token = ""
        self.region = "us"
        self._process = None
        self._public_url = None

    def setup(self, config: dict):
        """Setup ngrok configuration."""
        self.auth_token = config.get("auth_token") or os.getenv("NGROK_AUTH_TOKEN", "")
        self.region = config.get("region", "us")

        # Ngrok can work without auth token for short sessions
        self.enabled = True

        # If auth token provided, configure it
        if self.auth_token:
            self._configure_auth()

    def _configure_auth(self) -> bool:
        """Configure ngrok auth token."""
        try:
            result = subprocess.run(
                ["ngrok", "config", "add-authtoken", self.auth_token],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def start_tunnel(self, port: int, **kwargs) -> Optional[str]:
        """
        Start a tunnel to expose a local port.

        Args:
            port: Local port to expose
            **kwargs: Additional options (region, subdomain)

        Returns:
            Public URL or None if failed
        """
        if not self.enabled:
            return None

        # Check if ngrok is installed
        if not self._is_ngrok_installed():
            return None

        # Stop any existing tunnel
        self.stop_tunnel()

        # Get options
        region = kwargs.get("region", self.region)

        # Build command
        cmd = ["ngrok", "http", str(port)]
        if region:
            cmd.extend(["--region", region])

        # Add log format for easier parsing
        cmd.extend(["--log=stdout", "--log-format=json"])

        try:
            # Start ngrok process
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

            # Wait for ngrok to start and get URL
            time.sleep(2)
            self._public_url = self._get_url_from_api()

            if self._public_url:
                return self._public_url

            # Ngrok might still be starting
            time.sleep(3)
            self._public_url = self._get_url_from_api()

            if self._public_url:
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
                pass
            self._process = None

        self._public_url = None

        # Also kill any other ngrok processes (cleanup)
        try:
            subprocess.run(
                ["pkill", "-f", "ngrok"],
                capture_output=True,
                timeout=5
            )
            stopped = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Try Windows method
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "ngrok.exe"],
                    capture_output=True,
                    timeout=5
                )
                stopped = True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        return stopped

    def get_public_url(self) -> Optional[str]:
        """Get the current public URL if tunnel is active."""
        if self._public_url:
            return self._public_url
        return self._get_url_from_api()

    def get_status(self) -> Dict[str, Any]:
        """Get detailed tunnel status."""
        url = self.get_public_url()
        status = {
            "running": url is not None,
            "url": url,
            "integration": self.name,
            "region": self.region,
            "has_auth": bool(self.auth_token)
        }

        # Try to get more details from ngrok API
        api_status = self._get_api_status()
        if api_status:
            status.update(api_status)

        return status

    def _is_ngrok_installed(self) -> bool:
        """Check if ngrok is installed and available."""
        try:
            result = subprocess.run(
                ["ngrok", "version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _get_url_from_api(self, retries: int = 3, delay: float = 1.0) -> Optional[str]:
        """Get the public URL from ngrok's local API."""
        api_url = "http://localhost:4040/api/tunnels"

        for attempt in range(retries):
            try:
                with urlopen(api_url, timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    tunnels = data.get("tunnels", [])

                    # Prefer HTTPS tunnel
                    for tunnel in tunnels:
                        if tunnel.get("proto") == "https":
                            return tunnel.get("public_url")

                    # Fall back to any tunnel
                    if tunnels:
                        return tunnels[0].get("public_url")

            except (URLError, json.JSONDecodeError):
                if attempt < retries - 1:
                    time.sleep(delay)

        return None

    def _get_api_status(self) -> Optional[Dict[str, Any]]:
        """Get detailed status from ngrok API."""
        try:
            with urlopen("http://localhost:4040/api/tunnels", timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                tunnels = data.get("tunnels", [])

                if tunnels:
                    tunnel = tunnels[0]
                    return {
                        "proto": tunnel.get("proto"),
                        "local_addr": tunnel.get("config", {}).get("addr"),
                        "metrics": tunnel.get("metrics", {})
                    }
        except (URLError, json.JSONDecodeError):
            pass

        return None

    @staticmethod
    def after_install(config_values: dict) -> dict:
        """Post-install hook to verify ngrok setup."""
        import typer

        # Check if ngrok is installed
        try:
            result = subprocess.run(
                ["ngrok", "version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.decode().strip()
                typer.echo(f"\n   Ngrok detected: {version}")
            else:
                typer.secho(
                    "\n   Warning: ngrok not found. Install from https://ngrok.com/download",
                    fg=typer.colors.YELLOW
                )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            typer.secho(
                "\n   Warning: ngrok not found. Install from https://ngrok.com/download",
                fg=typer.colors.YELLOW
            )

        # Configure auth token if provided
        auth_token = config_values.get("auth_token")
        if auth_token:
            try:
                result = subprocess.run(
                    ["ngrok", "config", "add-authtoken", auth_token],
                    capture_output=True,
                    timeout=10
                )
                if result.returncode == 0:
                    typer.secho("   Auth token configured!", fg=typer.colors.GREEN)
                else:
                    typer.secho("   Failed to configure auth token", fg=typer.colors.RED)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                typer.secho("   Could not configure auth token", fg=typer.colors.YELLOW)

        return config_values