"""CDK stack for Sumo Dashboard Viewer infrastructure.

Resources: SES inbound, S3 buckets, Lambda processors, ECS Fargate service, CloudFront.
"""

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_ssm as ssm,
)
from constructs import Construct


class SumoDashboardViewerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ses_subdomain = self.node.try_get_context("ses_subdomain") or "sre.example.com"
        google_workspace_domain = self.node.try_get_context("google_workspace_domain") or "example.com"

        # --- S3: Raw Emails Bucket ---
        raw_emails_bucket = s3.Bucket(
            self,
            "RawEmailsBucket",
            bucket_name=f"sumo-dashboard-raw-emails-{self.account}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            lifecycle_rules=[
                s3.LifecycleRule(expiration=Duration.days(30)),
            ],
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # --- S3: Processed Images Bucket ---
        images_bucket = s3.Bucket(
            self,
            "ImagesBucket",
            bucket_name=f"sumo-dashboard-images-{self.account}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            lifecycle_rules=[
                s3.LifecycleRule(
                    prefix="dashboards/",
                    expiration=Duration.hours(3),
                ),
                s3.LifecycleRule(
                    prefix="pdfs/",
                    expiration=Duration.days(30),
                ),
            ],
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # --- Lambda: PDF Converter ---
        pdf_converter_fn = lambda_.Function(
            self,
            "PdfConverterFunction",
            function_name="sumo-pdf-converter",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset("lambda/pdf_converter"),
            timeout=Duration.minutes(5),
            memory_size=1024,
            environment={
                "IMAGES_BUCKET": images_bucket.bucket_name,
            },
        )
        images_bucket.grant_read_write(pdf_converter_fn)

        # --- Lambda: Email Processor ---
        email_processor_fn = lambda_.Function(
            self,
            "EmailProcessorFunction",
            function_name="sumo-email-processor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset("lambda/email_processor"),
            timeout=Duration.minutes(2),
            memory_size=256,
            environment={
                "IMAGES_BUCKET": images_bucket.bucket_name,
                "PDF_CONVERTER_FUNCTION": pdf_converter_fn.function_name,
            },
        )
        raw_emails_bucket.grant_read(email_processor_fn)
        images_bucket.grant_write(email_processor_fn)
        pdf_converter_fn.grant_invoke(email_processor_fn)

        # S3 event notification: trigger email processor on new objects
        raw_emails_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(email_processor_fn),
        )

        # --- SSM Parameter Store path (API keys provisioned manually) ---
        ssm_api_keys_prefix = "/sumo-viewer/api-keys/"

        # --- ECS Fargate: FastAPI App ---
        vpc = ec2.Vpc(self, "Vpc", max_azs=2)

        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)

        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "ViewerService",
            cluster=cluster,
            cpu=256,
            memory_limit_mib=512,
            desired_count=1,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset("."),
                container_port=8000,
                environment={
                    "S3_IMAGES_BUCKET": images_bucket.bucket_name,
                    "ALLOWED_DOMAIN": google_workspace_domain,
                    "SSM_API_KEYS_PREFIX": ssm_api_keys_prefix,
                    "STALE_THRESHOLD_MINUTES": "30",
                },
            ),
            public_load_balancer=True,
        )

        # Health check
        fargate_service.target_group.configure_health_check(path="/health")

        # Grant task role access to S3 and SSM
        images_bucket.grant_read(fargate_service.task_definition.task_role)
        fargate_service.task_definition.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParametersByPath"],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter{ssm_api_keys_prefix}*"
                ],
            )
        )
