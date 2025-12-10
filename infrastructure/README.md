# Treelemetry Infrastructure

AWS CDK infrastructure for provisioning S3 bucket and IAM credentials.

## Overview

This component provisions AWS resources for the Treelemetry pipeline:

```
MQTT Logger → DuckDB → Uploader → S3 (this) → Static Site
```

The infrastructure creates:
- S3 bucket for storing aggregated data
- IAM user and credentials for the uploader to write to S3

## Prerequisites

- Python 3.11+ with `uv` installed
- Node.js 18+ with npm (for running CDK via `npx`)
- AWS CLI configured with appropriate permissions

## Setup

Install Python dependencies using `uv`:

```bash
uv sync
```

No need to install the CDK CLI globally - we use `npx aws-cdk` which downloads it automatically.

## Deployment

Bootstrap CDK (first time only):

```bash
npx aws-cdk bootstrap
```

Deploy the stack:

```bash
npx aws-cdk deploy
```

Note: Using `npx` runs the CDK CLI without requiring a global install.

The deployment will output:
- S3 bucket name
- Public data URL
- AWS access key ID
- AWS secret access key

**Important:** Store the credentials securely! You'll need them for the uploader.

## Bucket Configuration

The stack uses a fixed bucket name: `treelemetry-sbma44-water-data`

This bucket name is hardcoded across all three components (infrastructure, uploader, static site), so no configuration updates are needed after deployment.

## Stack Resources

The CDK stack creates:

- **S3 Bucket**: Public-read bucket with CORS enabled for the static site
- **IAM User**: `treelemetry-uploader` with minimal permissions
- **IAM Policy**: Scoped to only allow `PutObject` and `PutObjectAcl` on the bucket
- **Access Key**: Credentials for the uploader

## Cleanup

To delete all resources:

```bash
npx aws-cdk destroy
```

Note: The S3 bucket has a `RETAIN` removal policy, so it won't be deleted automatically. Delete it manually if needed.

