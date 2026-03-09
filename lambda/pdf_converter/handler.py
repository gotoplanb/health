"""Lambda handler: converts a PDF from S3 to a cropped PNG and stores it back in S3."""

import os
import tempfile

import boto3
from pdf2image import convert_from_path
from PIL import Image

s3 = boto3.client("s3")


def crop_bottom_whitespace(img: Image.Image, threshold: int = 20) -> Image.Image:
    """Crop rows of near-black pixels from the bottom of the image.

    Scans upward from the bottom and trims rows where all pixel channels are <= threshold.
    """
    pixels = img.load()
    width, height = img.size

    last_content_row = height - 1
    for y in range(height - 1, -1, -1):
        for x in range(width):
            r, g, b = pixels[x, y][:3]
            if r > threshold or g > threshold or b > threshold:
                last_content_row = y
                break
        else:
            continue
        break

    # Add a small padding below the last content row
    crop_bottom = min(last_content_row + 10, height)
    return img.crop((0, 0, width, crop_bottom))


def handler(event, context):
    bucket = event["bucket"]
    pdf_key = event["pdf_key"]
    dashboard_name = event["dashboard_name"]
    timestamp = event["timestamp"]

    # Download PDF to temp file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        s3.download_fileobj(bucket, pdf_key, tmp_pdf)
        tmp_pdf_path = tmp_pdf.name

    # Convert PDF to images at 300 DPI
    images = convert_from_path(tmp_pdf_path, dpi=300)

    if not images:
        print(f"No pages found in PDF: {pdf_key}")
        return

    # Use first page (Sumo dashboards are typically single-page)
    img = images[0]

    # Crop bottom whitespace
    img = crop_bottom_whitespace(img)

    # Save PNG to temp file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_png:
        img.save(tmp_png, format="PNG")
        tmp_png_path = tmp_png.name

    # Upload to S3
    png_key = f"dashboards/{dashboard_name}/{timestamp}.png"
    s3.upload_file(
        tmp_png_path,
        bucket,
        png_key,
        ExtraArgs={
            "ContentType": "image/png",
            "Metadata": {
                "dashboard_name": dashboard_name,
                "timestamp": timestamp,
                "source_pdf_key": pdf_key,
            },
        },
    )

    print(f"Stored PNG: {png_key}")

    # Cleanup temp files
    os.unlink(tmp_pdf_path)
    os.unlink(tmp_png_path)

    return {"png_key": png_key}
