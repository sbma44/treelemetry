# Email Alerting Guide

MQTT Logger can send email alerts when disk space or database size thresholds are exceeded. This is particularly useful for unattended Raspberry Pi deployments.

## Features

- **Database Size Monitoring**: Alert when the database file grows beyond a specified size
- **Disk Space Monitoring**: Alert when free disk space drops below a threshold
- **Rate Limiting**: Configurable cooldown period to prevent alert spam
- **Startup Notifications**: Automatic email on successful startup showing actual config values
- **Zero External Dependencies**: Uses `msmtp` directly (no mail wrapper needed)

## Configuration

All alerting is **optional and disabled by default**. Enable it by adding an `[alerting]` section to your config:

```toml
[alerting]
# Email address to send alerts to (required to enable alerting)
email_to = "admin@example.com"

# Alert when database file exceeds this size in MB (optional)
db_size_threshold_mb = 1000  # Alert when DB > 1GB

# Alert when free disk space drops below this in MB (optional)
free_space_threshold_mb = 500  # Alert when < 500MB free

# Hours to wait between repeat alerts (default: 24)
alert_cooldown_hours = 24
```

### Disabling Alerting

To disable all alerting, simply leave `email_to` empty or omit the entire `[alerting]` section:

```toml
[alerting]
email_to = ""  # Disabled
```

### Selective Alerting

You can enable only specific alerts:

```toml
[alerting]
email_to = "admin@example.com"
db_size_threshold_mb = 1000           # DB size alerts enabled
# free_space_threshold_mb not set      # Disk space alerts disabled
```

## Setting Up Email with msmtp

MQTT Logger uses the system `mail` command to send emails. The easiest way to configure this on Raspberry Pi is with `msmtp`.

### Install msmtp

```bash
sudo apt update
sudo apt install msmtp msmtp-mta
```

### Configure msmtp

Create `~/.msmtprc` (or `/opt/mqtt-logger/.msmtprc` for the service user):

```bash
# Gmail example
account default
host smtp.gmail.com
port 587
from your-email@gmail.com
user your-email@gmail.com
password your-app-password
auth on
tls on
tls_trust_file /etc/ssl/certs/ca-certificates.crt
logfile ~/.msmtp.log
```

**For Gmail:**
1. Enable 2-factor authentication
2. Create an [App Password](https://myaccount.google.com/apppasswords)
3. Use the app password (not your regular password)

**For other providers:**
- **Outlook/Office365**: `smtp.office365.com:587`
- **Yahoo**: `smtp.mail.yahoo.com:587`
- **Custom SMTP**: Use your provider's SMTP settings

### Set Permissions

```bash
chmod 600 ~/.msmtprc
```

For systemd service:
```bash
sudo -u mqtt-logger mkdir -p /opt/mqtt-logger
sudo -u mqtt-logger nano /opt/mqtt-logger/.msmtprc
sudo chmod 600 /opt/mqtt-logger/.msmtprc
```

### Test Email

```bash
echo "Test message" | mail -s "Test Subject" admin@example.com
```

Check logs if it fails:
```bash
tail -f ~/.msmtp.log
```

## Alert Behavior

### When Alerts Are Checked

Alerts are checked during the periodic database flush cycle (every `flush_interval` seconds, default 300s for SD cards).

### Alert Content

**Database Size Alert:**
```
Subject: MQTT Logger: Database Size Alert

Database size has exceeded the threshold.

Database: /opt/mqtt-logger/data/mqtt_logs.db
Current size: 1234.56 MB
Threshold: 1000 MB

Consider:
- Archiving old data
- Increasing the threshold
- Adding data retention policies
```

**Low Disk Space Alert:**
```
Subject: MQTT Logger: Low Disk Space Alert

Free disk space has fallen below the threshold.

Path: /opt/mqtt-logger/data
Free space: 456.78 MB (14.3%)
Used space: 2543.22 MB (85.7%)
Total space: 3000.00 MB
Threshold: 500 MB

Consider:
- Deleting old data
- Expanding storage
- Archiving to external storage
```

### Rate Limiting (Cooldown)

To prevent alert spam, each alert type has a cooldown period (default: 24 hours). Once an alert is sent, the same alert won't be sent again until the cooldown expires, even if the condition persists.

**Example:**
- Database exceeds threshold at 10:00 AM → Alert sent
- Database still over threshold at 2:00 PM → No alert (cooldown)
- Database still over threshold tomorrow at 11:00 AM → Alert sent

You can adjust this:
```toml
alert_cooldown_hours = 12  # More frequent alerts
```

## Recommended Thresholds

### For 32GB SD Card (Raspberry Pi)

```toml
[alerting]
email_to = "admin@example.com"
db_size_threshold_mb = 10000        # 10GB (31% of 32GB)
free_space_threshold_mb = 2000      # 2GB free space minimum
alert_cooldown_hours = 24
```

### For 64GB SD Card

```toml
[alerting]
email_to = "admin@example.com"
db_size_threshold_mb = 20000        # 20GB
free_space_threshold_mb = 5000      # 5GB free space minimum
alert_cooldown_hours = 24
```

### For Network Storage

```toml
[alerting]
email_to = "admin@example.com"
db_size_threshold_mb = 100000       # 100GB
free_space_threshold_mb = 10000     # 10GB free space minimum
alert_cooldown_hours = 24
```

## Troubleshooting

### No Alerts Received

1. **Check if alerting is enabled:**
   ```bash
   sudo journalctl -u mqtt-logger | grep -i alert
   ```
   Should show: `Alerting enabled to admin@example.com`

2. **Test mail command:**
   ```bash
   echo "Test" | mail -s "Test" admin@example.com
   ```

3. **Check msmtp logs:**
   ```bash
   tail -f ~/.msmtp.log
   # or for service user
   sudo tail -f /opt/mqtt-logger/.msmtp.log
   ```

4. **Verify threshold exceeded:**
   ```bash
   # Check database size
   ls -lh /opt/mqtt-logger/data/mqtt_logs.db
   
   # Check free space
   df -h /opt/mqtt-logger/data
   ```

### Alert Spam

If you're receiving too many alerts:

1. **Increase cooldown period:**
   ```toml
   alert_cooldown_hours = 48  # 2 days
   ```

2. **Adjust thresholds:**
   ```toml
   db_size_threshold_mb = 5000  # Higher threshold
   ```

3. **Disable specific alerts:**
   ```toml
   [alerting]
   email_to = "admin@example.com"
   # Comment out the alert you don't want
   # db_size_threshold_mb = 1000
   free_space_threshold_mb = 500  # Only keep this one
   ```

### Permission Errors

If the service can't send mail:

```bash
# Ensure mqtt-logger user can access msmtp config
sudo ls -la /opt/mqtt-logger/.msmtprc
# Should show: -rw------- 1 mqtt-logger mqtt-logger

# Test as service user
sudo -u mqtt-logger bash
echo "Test" | mail -s "Test" admin@example.com
exit
```

### Gmail Not Working

Common Gmail issues:

1. **"Username and Password not accepted"**
   - Enable 2-factor authentication
   - Use an App Password (not your regular password)

2. **"Could not authenticate"**
   - Check that "Less secure app access" is NOT required (use App Passwords instead)
   - Verify SMTP settings: `smtp.gmail.com:587`

3. **TLS Errors**
   ```bash
   # Update CA certificates
   sudo apt update
   sudo apt install ca-certificates
   ```

## Integration with Monitoring Systems

You can forward these alerts to other systems:

### To Slack

Use a mail-to-Slack gateway or configure msmtp to send to your Slack email integration.

### To SMS

Use email-to-SMS gateways:
- Verizon: `phonenumber@vtext.com`
- AT&T: `phonenumber@txt.att.net`
- T-Mobile: `phonenumber@tmomail.net`

```toml
[alerting]
email_to = "5551234567@vtext.com"
```

### To Multiple Recipients

Configure multiple email aliases in your mail system or use comma-separated addresses (depends on your mail command implementation).

## Security Considerations

1. **Protect msmtp config:**
   ```bash
   chmod 600 ~/.msmtprc
   ```
   The file contains your email password!

2. **Use App Passwords:**
   Never use your main email password. Use provider-specific app passwords.

3. **Monitor alert logs:**
   ```bash
   sudo journalctl -u mqtt-logger | grep -i alert
   ```

4. **Test regularly:**
   Ensure alerts are still working by periodically triggering them manually.

## Performance Impact

Alerting has minimal performance impact:
- Checks run only during periodic flushes (every 5 minutes by default)
- File size check: ~1ms
- Disk space check: ~5ms
- Email sending: ~1-2 seconds (async, doesn't block message processing)

Total overhead: < 0.1% of CPU time

## Examples

### Production Setup for Raspberry Pi

```toml
[database]
path = "data/mqtt_logs.db"
batch_size = 5000
flush_interval = 300  # 5 minutes

[alerting]
email_to = "ops@example.com"
db_size_threshold_mb = 15000      # Alert at 15GB
free_space_threshold_mb = 3000    # Alert at 3GB free
alert_cooldown_hours = 24
```

### Development/Testing Setup

```toml
[database]
path = "data/mqtt_logs.db"
batch_size = 100
flush_interval = 30

[alerting]
email_to = "dev@example.com"
db_size_threshold_mb = 100        # Alert at 100MB for testing
free_space_threshold_mb = 1000
alert_cooldown_hours = 1          # More frequent for testing
```

### Disabled Alerting (Default)

```toml
# No [alerting] section = alerting disabled
# OR
[alerting]
email_to = ""  # Explicitly disabled
```

## Summary

- **Optional**: Disabled by default, no impact if not configured
- **Simple Setup**: Just configure msmtp and set thresholds
- **Reliable**: Uses standard Unix mail command
- **Rate Limited**: Won't spam you with alerts
- **Informative**: Detailed alert messages with actionable suggestions
- **Flexible**: Enable only the alerts you need

