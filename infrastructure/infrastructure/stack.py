"""
Treelemetry CDK Stack

Creates:
- S3 bucket for storing water level JSON data
- IAM user with tightly scoped permissions for uploading
- Access keys for the IAM user
"""
from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_s3 as s3,
    aws_iam as iam,
)
from constructs import Construct


class TreelemetryStack(Stack):
    """CDK Stack for Treelemetry infrastructure."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create S3 bucket for water level data
        bucket = s3.Bucket(
            self,
            "DataBucket",
            bucket_name="treelemetry-sbma44-water-data",  # Fixed name for predictability
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=True,       # Block public ACLs (modern approach)
                block_public_policy=False,    # Allow public bucket policy
                ignore_public_acls=True,      # Ignore any public ACLs
                restrict_public_buckets=False # Allow this public bucket
            ),
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.GET],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    max_age=30,
                )
            ],
            removal_policy=RemovalPolicy.RETAIN,  # Keep data if stack is deleted
        )

        # Add bucket policy for public read access
        bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.AnyPrincipal()],
                actions=["s3:GetObject"],
                resources=[f"{bucket.bucket_arn}/*"],
            )
        )

        # Create IAM user for the uploader
        uploader_user = iam.User(
            self,
            "UploaderUser",
            user_name="treelemetry-uploader",
        )

        # Create tightly scoped policy for uploading to the bucket
        upload_policy = iam.Policy(
            self,
            "UploaderPolicy",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:PutObject",
                        # Note: PutObjectAcl not needed - bucket policy handles public access
                    ],
                    resources=[
                        f"{bucket.bucket_arn}/*",
                    ],
                ),
            ],
        )

        uploader_user.attach_inline_policy(upload_policy)

        # Create access key for the user
        access_key = iam.CfnAccessKey(
            self,
            "UploaderAccessKey",
            user_name=uploader_user.user_name,
        )

        # Outputs
        CfnOutput(
            self,
            "BucketName",
            value=bucket.bucket_name,
            description="S3 bucket name for water level data",
            export_name="TreelemetryBucketName",
        )

        CfnOutput(
            self,
            "BucketUrl",
            value=bucket.bucket_regional_domain_name,
            description="S3 bucket URL",
        )

        CfnOutput(
            self,
            "DataUrl",
            value=f"https://{bucket.bucket_regional_domain_name}/water-level.json",
            description="Public URL for water level JSON data",
        )

        CfnOutput(
            self,
            "AccessKeyId",
            value=access_key.ref,
            description="AWS Access Key ID for uploader (store securely!)",
        )

        CfnOutput(
            self,
            "SecretAccessKey",
            value=access_key.attr_secret_access_key,
            description="AWS Secret Access Key for uploader (store securely!)",
        )

