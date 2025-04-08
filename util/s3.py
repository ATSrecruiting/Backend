import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException # Make sure Depends is imported
import logging
from .app_config import config # Assuming config loads .env vars

logger = logging.getLogger(__name__)

# --- Dependency Function for S3 Client ---
def get_s3_client():
    """
    Dependency function to initialize and return a Boto3 S3 client.
    Reads configuration from config object or environment variables.
    Raises HTTPException if initialization fails.
    """
    s3_client = None
    try:
        # Try reading region from config object first
        aws_region = config.AWS_REGION
        if aws_region:
            logger.info(f"Initializing S3 client for region: {aws_region}")
            s3_client = boto3.client('s3', region_name=aws_region)
        else:
            # Attempt initialization without explicit region
            # Relies on default config (~/.aws/config) or IAM role if on EC2/ECS etc.
            logger.warning("AWS_REGION not configured, attempting default S3 client initialization.")
            s3_client = boto3.client('s3')
        

        return s3_client

    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to create Boto3 S3 client (Credentials/Config Error): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"S3 client initialization failed: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during S3 client initialization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error initializing S3 client.")