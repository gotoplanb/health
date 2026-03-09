"""Lambda handler: parses SES-delivered raw emails from S3, extracts PDF attachments,
stores them in the processed-images bucket, and invokes the PDF converter Lambda."""

import email
import json
import os
import re
from datetime import datetime, timezone
from email import policy

import boto3

s3 = boto3.client("s3")
lambda_client = boto3.client("lambda")

IMAGES_BUCKET = os.environ["IMAGES_BUCKET"]
PDF_CONVERTER_FUNCTION = os.environ["PDF_CONVERTER_FUNCTION"]


def slugify(name: str) -> str:
    """Convert a dashboard display name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def handler(event, context):
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]

        # Download raw email
        response = s3.get_object(Bucket=bucket, Key=key)
        raw_email = response["Body"].read()

        # Parse email
        msg = email.message_from_bytes(raw_email, policy=policy.default)

        # Extract dashboard name from subject
        subject = msg["Subject"] or "unknown-dashboard"
        dashboard_name = slugify(subject)

        # Parse timestamp from email Date header, fall back to now
        email_date = msg["Date"]
        if email_date:
            timestamp = email_date.datetime.astimezone(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)
        ts_str = timestamp.strftime("%Y-%m-%dT%H-%M-%SZ")

        # Find PDF attachment
        pdf_data = None
        for part in msg.walk():
            if part.get_content_type() == "application/pdf":
                pdf_data = part.get_content()
                break

        if pdf_data is None:
            print(f"No PDF attachment found in email: {key}")
            return

        # Upload PDF to processed-images bucket
        pdf_key = f"pdfs/{dashboard_name}/{ts_str}.pdf"
        s3.put_object(Bucket=IMAGES_BUCKET, Key=pdf_key, Body=pdf_data)

        # Invoke PDF converter
        payload = {
            "bucket": IMAGES_BUCKET,
            "pdf_key": pdf_key,
            "dashboard_name": dashboard_name,
            "timestamp": ts_str,
        }
        lambda_client.invoke(
            FunctionName=PDF_CONVERTER_FUNCTION,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        print(f"Processed email for dashboard '{dashboard_name}' at {ts_str}")
