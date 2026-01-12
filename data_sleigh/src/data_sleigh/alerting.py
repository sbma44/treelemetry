"""Alerting system for disk space and database size monitoring."""

import logging
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AlertManager:
    """Manage alerts for disk space and database size.
    
    Sends email alerts when thresholds are exceeded. Implements rate limiting
    to avoid alert spam.
    
    Example:
        >>> config = AlertingConfig(
        ...     email_to="admin@example.com",
        ...     db_size_threshold_mb=1000,
        ...     free_space_threshold_mb=500
        ... )
        >>> manager = AlertManager(config)
        >>> manager.check_db_size("/path/to/db.duckdb")
        >>> manager.check_free_space("/path/to/db.duckdb")
    """
    
    def __init__(
        self,
        email_to: str | None,
        db_size_threshold_mb: int | None,
        free_space_threshold_mb: int | None,
        alert_cooldown_hours: int = 24,
    ):
        """Initialize the alert manager.
        
        Args:
            email_to: Email address to send alerts to (None = disabled)
            db_size_threshold_mb: Database size threshold in MB (None = disabled)
            free_space_threshold_mb: Free space threshold in MB (None = disabled)
            alert_cooldown_hours: Hours to wait between repeat alerts
        """
        self.email_to = email_to
        self.db_size_threshold_mb = db_size_threshold_mb
        self.free_space_threshold_mb = free_space_threshold_mb
        self.alert_cooldown = timedelta(hours=alert_cooldown_hours)
        
        # Track last alert times to prevent spam
        self._last_alerts: dict[str, datetime] = {}
        
        self.enabled = email_to is not None
        
        if self.enabled:
            logger.info(
                f"Alerting enabled to {email_to} "
                f"(DB threshold: {db_size_threshold_mb}MB, "
                f"Free space threshold: {free_space_threshold_mb}MB)"
            )
        else:
            logger.debug("Alerting disabled (no email configured)")
    
    def check_db_size(self, db_path: Path | str) -> None:
        """Check database size and alert if threshold exceeded.
        
        Args:
            db_path: Path to the database file
        """
        if not self.enabled or self.db_size_threshold_mb is None:
            return
        
        db_path = Path(db_path)
        
        if not db_path.exists():
            return
        
        try:
            # Get database size in MB
            size_bytes = db_path.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            
            if size_mb > self.db_size_threshold_mb:
                alert_key = f"db_size_{db_path}"
                
                if self._should_send_alert(alert_key):
                    self._send_alert(
                        subject="MQTT Logger: Database Size Alert",
                        body=(
                            f"Database size has exceeded the threshold.\n\n"
                            f"Database: {db_path}\n"
                            f"Current size: {size_mb:.2f} MB\n"
                            f"Threshold: {self.db_size_threshold_mb} MB\n\n"
                            f"Consider:\n"
                            f"- Archiving old data\n"
                            f"- Increasing the threshold\n"
                            f"- Adding data retention policies\n"
                        ),
                    )
                    self._last_alerts[alert_key] = datetime.now()
                    logger.warning(
                        f"Database size alert sent: {size_mb:.2f}MB > "
                        f"{self.db_size_threshold_mb}MB"
                    )
        except Exception as e:
            logger.error(f"Failed to check database size: {e}")
    
    def check_free_space(self, path: Path | str) -> None:
        """Check free disk space and alert if below threshold.
        
        Args:
            path: Path to check (typically database directory)
        """
        if not self.enabled or self.free_space_threshold_mb is None:
            return
        
        path = Path(path)
        
        # Get the directory, not the file
        if path.is_file():
            path = path.parent
        
        try:
            # Get disk usage statistics
            stat = shutil.disk_usage(path)
            free_mb = stat.free / (1024 * 1024)
            total_mb = stat.total / (1024 * 1024)
            used_mb = stat.used / (1024 * 1024)
            percent_used = (stat.used / stat.total) * 100
            
            if free_mb < self.free_space_threshold_mb:
                alert_key = f"free_space_{path}"
                
                if self._should_send_alert(alert_key):
                    self._send_alert(
                        subject="MQTT Logger: Low Disk Space Alert",
                        body=(
                            f"Free disk space has fallen below the threshold.\n\n"
                            f"Path: {path}\n"
                            f"Free space: {free_mb:.2f} MB ({100-percent_used:.1f}%)\n"
                            f"Used space: {used_mb:.2f} MB ({percent_used:.1f}%)\n"
                            f"Total space: {total_mb:.2f} MB\n"
                            f"Threshold: {self.free_space_threshold_mb} MB\n\n"
                            f"Consider:\n"
                            f"- Deleting old data\n"
                            f"- Expanding storage\n"
                            f"- Archiving to external storage\n"
                        ),
                    )
                    self._last_alerts[alert_key] = datetime.now()
                    logger.warning(
                        f"Low disk space alert sent: {free_mb:.2f}MB < "
                        f"{self.free_space_threshold_mb}MB"
                    )
        except Exception as e:
            logger.error(f"Failed to check free disk space: {e}")
    
    def _should_send_alert(self, alert_key: str) -> bool:
        """Check if enough time has passed since last alert.
        
        Args:
            alert_key: Unique identifier for this alert type
            
        Returns:
            True if alert should be sent
        """
        if alert_key not in self._last_alerts:
            return True
        
        time_since_last = datetime.now() - self._last_alerts[alert_key]
        return time_since_last >= self.alert_cooldown
    
    def _send_alert(self, subject: str, body: str) -> None:
        """Send an email alert using msmtp.
        
        Args:
            subject: Email subject line
            body: Email body text
        """
        if not self.email_to:
            return
        
        try:
            # Format email with headers for msmtp
            email_message = f"""To: {self.email_to}
Subject: {subject}

{body}
"""
            
            # Use msmtp directly (works in Docker and on systems with msmtp)
            # Try msmtp first, fall back to sendmail
            msmtp_paths = ["/usr/bin/msmtp", "/usr/local/bin/msmtp", "msmtp"]
            
            msmtp_cmd = None
            for path in msmtp_paths:
                try:
                    # Check if command exists
                    subprocess.run(
                        [path, "--version"],
                        capture_output=True,
                        timeout=1,
                    )
                    msmtp_cmd = path
                    break
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
            
            if not msmtp_cmd:
                logger.error(
                    "msmtp command not found. Install msmtp or configure system mail."
                )
                return
            
            # Check if msmtp config exists
            import os
            msmtprc_path = "/root/.msmtprc"
            if not os.path.exists(msmtprc_path):
                logger.error(
                    f"msmtp config not found at {msmtprc_path}. "
                    "Rebuild Docker image with SMTP build arguments: "
                    "--build-arg SMTP_SERVER=... --build-arg SMTP_PASSWORD=..."
                )
                return
            
            # Specify config file location explicitly
            process = subprocess.Popen(
                [msmtp_cmd, "-C", msmtprc_path, "-t"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            
            stdout, stderr = process.communicate(input=email_message, timeout=30)
            
            if process.returncode == 0:
                logger.info(f"Alert email sent to {self.email_to}: {subject}")
            else:
                logger.error(
                    f"Failed to send alert email: {stderr or 'Unknown error'}"
                )
        except subprocess.TimeoutExpired:
            logger.error("Timeout sending alert email")
            try:
                process.kill()
            except Exception:
                pass
        except FileNotFoundError:
            logger.error(
                "msmtp command not found. Install msmtp or configure system mail."
            )
        except Exception as e:
            logger.error(f"Error sending alert email: {e}")
    
    def check_all(self, db_path: Path | str) -> None:
        """Run all configured checks.
        
        Args:
            db_path: Path to the database file
        """
        if not self.enabled:
            return
        
        self.check_db_size(db_path)
        self.check_free_space(db_path)

