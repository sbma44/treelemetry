"""Monthly DuckDB backup manager for off-season data archival."""

import logging
from datetime import datetime
from pathlib import Path

import boto3

from .config import BackupConfig, S3Config

logger = logging.getLogger(__name__)


class BackupManager:
    """Handle monthly DuckDB backups during off-season.

    Backs up the database to S3 and starts fresh to free disk space.
    """

    def __init__(
        self,
        backup_config: BackupConfig,
        s3_config: S3Config,
    ):
        """Initialize the backup manager.

        Args:
            backup_config: Backup configuration
            s3_config: S3 configuration
        """
        self.backup_config = backup_config
        self.s3_config = s3_config
        self.last_backup_month: tuple[int, int] | None = None

        # Initialize S3 client
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=s3_config.aws_access_key_id,
            aws_secret_access_key=s3_config.aws_secret_access_key,
        )

        logger.info("Backup manager initialized")

    def should_backup(self) -> bool:
        """Check if backup is due.

        Returns:
            True if backup should be performed now
        """
        now = datetime.now()
        target_day = self.backup_config.day_of_month
        target_hour = self.backup_config.hour

        # Check if we're on the right day and hour
        if now.day == target_day and now.hour == target_hour:
            current_month = (now.year, now.month)
            if current_month != self.last_backup_month:
                return True

        return False

    def backup_database(self, db_path: Path, storage) -> Path:
        """Backup DuckDB to S3 and prepare for fresh start.

        Args:
            db_path: Path to the DuckDB database file
            storage: MessageStore instance to close/reinitialize

        Returns:
            Path to the new (fresh) database file

        Raises:
            Exception: If backup fails
        """
        now = datetime.now()

        # Generate backup filename with year-month timestamp
        backup_name = f"mqtt_logs_backup_{now.strftime('%Y-%m')}.duckdb"
        s3_key = f"{self.s3_config.backup_prefix}{backup_name}"

        logger.info(f"Starting monthly backup: {backup_name}")

        try:
            # Close current DB connection
            logger.info("Closing database connection...")
            storage.close()

            # Check if database file exists
            if not db_path.exists():
                logger.warning(f"Database file not found: {db_path}")
                return db_path

            # Get file size for logging
            db_size_mb = db_path.stat().st_size / (1024 * 1024)
            logger.info(f"Database size: {db_size_mb:.2f} MB")

            # Upload to S3
            logger.info(f"Uploading to s3://{self.s3_config.bucket}/{s3_key}")
            self.s3_client.upload_file(
                Filename=str(db_path),
                Bucket=self.s3_config.bucket,
                Key=s3_key,
            )

            logger.info(f"Backup uploaded successfully: s3://{self.s3_config.bucket}/{s3_key}")

            # Archive old file locally (move to archive subdirectory)
            archive_dir = db_path.parent / "archive"
            archive_dir.mkdir(exist_ok=True)
            archive_path = archive_dir / backup_name

            logger.info(f"Archiving old database to {archive_path}")
            db_path.rename(archive_path)

            # Record that we've done this month's backup
            self.last_backup_month = (now.year, now.month)

            logger.info(f"Backup complete. Fresh database will be created at {db_path}")

            return db_path

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            raise

    def list_backups(self) -> list[dict[str, str]]:
        """List all backups in S3.

        Returns:
            List of backup information dictionaries
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.s3_config.bucket,
                Prefix=self.s3_config.backup_prefix,
            )

            backups = []
            for obj in response.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".duckdb"):
                    backups.append({
                        "key": key,
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                    })

            return backups

        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []

    def restore_backup(self, backup_key: str, target_path: Path) -> None:
        """Restore a backup from S3.

        Args:
            backup_key: S3 key of the backup to restore
            target_path: Local path to restore to

        Raises:
            Exception: If restore fails
        """
        try:
            logger.info(f"Restoring backup from s3://{self.s3_config.bucket}/{backup_key}")

            self.s3_client.download_file(
                Bucket=self.s3_config.bucket,
                Key=backup_key,
                Filename=str(target_path),
            )

            logger.info(f"Backup restored to {target_path}")

        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            raise



