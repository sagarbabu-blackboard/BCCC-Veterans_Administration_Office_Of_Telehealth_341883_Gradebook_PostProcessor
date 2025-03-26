import logging
import os
import csv
import json
import time
import boto3
import pysftp
import base64
import requests


#console log statement start
log_level = logging.INFO
# Configure the logger
logging.basicConfig(
    level=log_level,  # Set the minimum logging level (INFO, DEBUG, etc.)
    format="%(asctime)s - %(levelname)s - %(message)s"  # Log format
)
logger = logging.getLogger(__name__)
#console log statement end


#logger = logging.getLogger()
#logger.setLevel(logging.DEBUG)

class S3Config:
    def __init__(self, region, bucket, prefix):
        self.region           = region
        self.bucket           = bucket
        self.prefix           = prefix

class SFTPConfig:
    def __init__(self, host, port, username, password, remote_directory):
        self.host             = host
        self.port             = port
        self.username         = username
        self.password         = password
        self.remote_directory = remote_directory
            

def lambda_handler():
    try:
        logger.info("Started Lambda")
        logger.info("get environment variables: S3")
        s3_config = S3Config(
            'us-east-2',
            'icm-sandbox1',
            'sagar_test/'
        )

        logger.info("get environment variables: SFTP")
        sftp_config = SFTPConfig(
            '3.14.12.204',
            '22',
            'sftpuser1',
            'pHK7HYYndKAma0bYPLwX',
            '/files/temp/'
        )
        logger.info("download client input report (learning history report) from S3")
        local_file_path, filename, file_key = download_latest_file_from_s3(s3_config)
        process_file(local_file_path,sftp_config, filename)
        delete_file_from_s3(s3_config, file_key)

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Success"}),
            "headers": {
                "Content-Type": "application/json"
            }
        }
    except Exception as e:
        logger.info(str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
        
        
# Function to download the latest file containing 'FAA_Learning_History' from S3 bucket
def download_latest_file_from_s3(s3_config):
    try:
        # AWS S3 Configuration
        print("main report lambda_handler() definision execution got started")
        s3 = boto3.client("s3")
        #s3_bucket = "icm-reportingframework-auxiliaries"
        #s3_prefix = "customers/332050_tcsg/instances/{s3_bucket_name}/main/"
        s3_bucket = s3_config.bucket
        s3_prefix = s3_config.prefix
        region = s3_config.region
        s3_client = boto3.client("s3", region_name=region)
        response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=s3_prefix)
        files = response['Contents']
        
        # Find the file with the latest modification date
        latest_file = max(files, key=lambda x: x['LastModified'])
        latest_file_key = latest_file['Key']
        last_modified_date = latest_file['LastModified']
        print("Latest file:", latest_file_key)
        print("Last modified date:", last_modified_date)
        
        # Check if the key corresponds to a folder
        if latest_file_key.endswith('/'):
            print("No file present. Only folder setting is updated. Skipping deletion.")
            return '', '', ''
        
        # Extract the filename from the key
        filename = latest_file_key.split('/')[-1]
        
        # AWS S3 download
        local_file_path = f'/tmp/{filename}'  # Use the same filename as S3
        print("Downloading the latest file from S3:", latest_file_key)
        s3.download_file(s3_bucket, latest_file_key, local_file_path)
        print("Latest file downloaded:", latest_file_key)
        return local_file_path, filename, latest_file_key
    except Exception as e:
        message = f"Download the client input report from S3 failed: bucket={s3_config.bucket}, error: {str(e)}"
        logger.error(message)
        raise Exception(message) from e
        
# Function to delete file from S3 bucket
def delete_file_from_s3(s3_config, file_key):
    try:
        s3 = boto3.client("s3", region_name=s3_config.region)
        s3.delete_object(Bucket=s3_config.bucket, Key=file_key)
        logger.info(f"Original File was deleted from the S3 bucket location: {file_key}")
    except Exception as e:
        message = f"delete file from s3 failed: bucket={s3_config.bucket}, file={file_key}"
        logger.warning(message)
        raise Exception(message) from e
        
def process_file(local_file_path,sftp_config, filename):
    if local_file_path !='':
        # Rename the file
        print(f"local_file_path = {local_file_path}")
        new_filename = remove_extension(filename)  # Example: Add a prefix to the filename
        #new_local_file_path = f'/tmp/{new_filename}'
        #os.rename(local_file_path, new_local_file_path)
        remote_file_path = f"{sftp_config.remote_directory}/{new_filename}"
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None
        print("File renamed to:", new_filename)
        
        # SFTP upload
        print("Uploading file to SFTP...")
        try: 
            with pysftp.Connection(host=sftp_config.host, port=int(sftp_config.port), username=sftp_config.username, password=sftp_config.password, cnopts=cnopts) as sftp:
                sftp.cwd(sftp_config.remote_directory)
                # Use the put method to upload the CSV file to the remote directory
                try:
                    logger.info("Client SFTP file transfer got started ...")        
                    sftp.put(local_file_path, remote_file_path)
                    logger.info("Client SFTP file transfer got completed")
                    status_code=200
                except Exception as e:
                    logger.error(f"Client SFTP file transfer failed: {e}", exc_info=True)
                    status_code = 500  # Failure status code
               
                finally:
                    # Ensure file cleanup regardless of success or failure
                    try:
                        if os.path.exists(local_file_path):
                            os.remove(local_file_path)
                            print(f"Temporary file {local_file_path} deleted successfully.")                        
                    except Exception as e:
                        logger.warning(f"Unable to delete the client temp SFTP file from location: {local_file_path}. Exception: {e}")

        except Exception as e:
            message = f"Download from S3 or upload to SFTP failed: {str(e)}"
            print(message)
            raise
    else: 
        logger.info("No file available in the S3 bucket so, SFTP file transfer cancelled...")
    
    
def remove_extension(filename):
    # Split the filename at the last dot and take the first part
    name_without_extension = filename.rsplit('.', 1)[0]
    return name_without_extension



        
lambda_handler()