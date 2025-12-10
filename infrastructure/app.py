#!/usr/bin/env python3
"""
Treelemetry Infrastructure

AWS CDK app for provisioning S3 bucket and IAM credentials for the uploader.
"""
import os
from aws_cdk import App, Environment
from infrastructure.stack import TreelemetryStack

app = App()

# Get AWS account and region from environment or use defaults
account = os.environ.get("CDK_DEFAULT_ACCOUNT")
region = os.environ.get("CDK_DEFAULT_REGION", "us-east-1")

env = Environment(account=account, region=region) if account else None

TreelemetryStack(
    app,
    "TreelemetryStack",
    env=env,
    description="Infrastructure for Treelemetry - Christmas tree water level monitoring",
)

app.synth()

