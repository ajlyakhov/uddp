import os
import subprocess
import traceback
import zipfile
import time
from pathlib import Path
from typing import Optional, Dict, Generator
from PIL import Image
import boto3
import requests
import structlog
from boto3.s3.transfer import TransferConfig
from django.conf import settings
from stream_unzip import stream_unzip, UnzipError, TruncatedDataError
from enum import Enum
from requests import Response
from bulkboto3 import BulkBoto3
import math
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from core.models import Task
from botocore.config import Config
import psutil


logger = structlog.get_logger(__name__)
boto3_session = boto3.session.Session()
# config = Config(connect_timeout=10, read_timeout=30)
s3_client = boto3_session.client(
    service_name='s3',
    aws_access_key_id=settings.S3_ID,
    aws_secret_access_key=settings.S3_KEY,
    endpoint_url=settings.S3_HOST,
)
s3_public_client = boto3_session.client(
    service_name='s3',
    aws_access_key_id=settings.S3_ID,
    aws_secret_access_key=settings.S3_KEY,
    endpoint_url=settings.S3_HOST,
    config=Config(s3={'addressing_style': 'virtual'})
)
s3_resource = boto3_session.resource(
    service_name='s3',
    aws_access_key_id=settings.S3_ID,
    aws_secret_access_key=settings.S3_KEY,
    endpoint_url=settings.S3_HOST,
)

NUM_TRANSFER_THREADS = 50
TRANSFER_VERBOSITY = False
bulkboto_agent = BulkBoto3(
    resource_type="s3",
    endpoint_url=settings.S3_HOST,
    aws_access_key_id=settings.S3_ID,
    aws_secret_access_key=settings.S3_KEY,
    max_pool_connections=300,
    verbose=TRANSFER_VERBOSITY,
)

ext_to_content_type = {
    "epub": "application/epub+zip",
    "json": "application/json",
    "mp3": "audio/mpeg",
    "pdf": "application/pdf",
    "png": "image/png",
    "svg": "image/svg+xml",
    "html": "text/html",
    "xhtml": "text/html",
    "js": "application/javascript",
    "css": "text/css",
    "ico": "image/x-icon",
}


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"


def pretty_file_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])


def streaming_download_and_unzip_archive(
        task: Task,
        dir_path: Path,
        url: str,
        http_method: str = HTTPMethod.GET,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None,
        max_retries: int = 3,
        enable_resume: bool = True,
) -> None:
    retry_count = 0
    last_error = None
    temp_file_path = None
    
    if enable_resume:
        temp_file_path = dir_path / f"temp_download_{task.id}.zip"
    
    while retry_count <= max_retries:
        try:
            task.logging(f"{__name__}", f"Download attempt {retry_count + 1}/{max_retries + 1}")
            
            if enable_resume and temp_file_path and temp_file_path.exists():
                task.logging(f"{__name__}", "Attempting resume via temporary file")
                _download_to_temp_with_resume(task, url, temp_file_path, http_method, data, json)
                
                with open(temp_file_path, 'rb') as temp_file:
                    for file_name, file_size, unzipped_chunks in stream_unzip(temp_file):
                        file_name = file_name.decode("utf-8")
                        file_path = dir_path / file_name
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        if file_size == 0:
                            file_path.mkdir()
                            for _ in unzipped_chunks:
                                pass
                        else:
                            with open(file_path, "wb") as f:
                                for chunk in unzipped_chunks:
                                    f.write(chunk)
                
                # Deleting temporary file after successful unzip
                temp_file_path.unlink()
                
            else:
                for file_name, file_size, unzipped_chunks in stream_unzip(
                        _streaming_download(task=task, url=url, http_method=http_method, data=data, json=json)
                ):
                    file_name = file_name.decode("utf-8")
                    file_path = dir_path / file_name
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    if file_size == 0:
                        file_path.mkdir()
                        for _ in unzipped_chunks:
                            pass
                    else:
                        with open(file_path, "wb") as f:
                            for chunk in unzipped_chunks:
                                f.write(chunk)
            
            # If reached here - download successfully completed
            task.logging(f"{__name__}", f"Download successfully completed on attempt {retry_count + 1}")
            return
            
        except (requests.exceptions.RequestException, requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout, TruncatedDataError) as e:
            last_error = e
            retry_count += 1
            
            if retry_count <= max_retries:
                wait_time = min(2 ** retry_count, 30)  # Exponential backoff, max 30 sec
                task.logging(f"{__name__}", f"Download error: {str(e)}. Retrying in {wait_time} sec...")
                
                import time
                time.sleep(wait_time)
                continue
            else:
                break
                
        except UnzipError as e:
            logger.exception("Error unzipping archive downloaded from url", url=url, task_id=task.id)
            raise Exception(f"Archive unzip error: {str(e)}") from e
    
    if temp_file_path and temp_file_path.exists():
        temp_file_path.unlink()
    
    if isinstance(last_error, requests.exceptions.RequestException):
        response_error = ""
        if hasattr(last_error, "response") and hasattr(last_error.response, "content"):
            response_error = last_error.response.content.decode("utf-8")
        
        logger.exception(
            "Error downloading from url after all retries",
            url=url,
            response_error=response_error,
            task_id=task.id,
            retry_count=retry_count,
        )
        raise Exception(f"Failed to download package after {max_retries + 1} attempts: {response_error}") from last_error
    
    elif isinstance(last_error, TruncatedDataError):
        logger.exception("Truncated ZIP archive after all retries", url=url, task_id=task.id, retry_count=retry_count)
        raise Exception(f"ZIP archive corrupted or incomplete after {max_retries + 1} attempts: {str(last_error)}") from last_error
    
    else:
        raise Exception(f"Unexpected error after {max_retries + 1} attempts: {str(last_error)}") from last_error


def _download_to_temp_with_resume(
        task: Task,
        url: str,
        temp_file_path: Path,
        http_method: str = HTTPMethod.GET,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None,
) -> None:
    """Download to temporary file with resume support"""
    downloaded_size = 0
    
    # Checking existing file size
    if temp_file_path.exists():
        downloaded_size = temp_file_path.stat().st_size
        task.logging(f"{__name__}", f"Found partially downloaded file of size {pretty_file_size(downloaded_size)}")
    
    response = _get_response_with_range(task, url, http_method, data, json, downloaded_size)
    
    try:
        response.raise_for_status()
        
        # Opening file for appending
        mode = 'ab' if downloaded_size > 0 else 'wb'
        with open(temp_file_path, mode) as f:
            for chunk in response.iter_content(chunk_size=1024*1024*10):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    task.logging_last(f"{__name__}", f"---> downloaded {pretty_file_size(downloaded_size)}")
    
    finally:
        response.close()


def _streaming_download_with_resume(
        task: Task,
        url: str,
        http_method: str = HTTPMethod.GET,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None,
        temp_file_path: Optional[Path] = None,
) -> Generator[None, None, None]:
    """Download with resume capability on connection drop"""
    downloaded_size = 0
    
    # If temporary file exists, check its size
    if temp_file_path and temp_file_path.exists():
        downloaded_size = temp_file_path.stat().st_size
        task.logging(f"{__name__}", f"Found partially downloaded file of size {pretty_file_size(downloaded_size)}")
    
    response = _get_response_with_range(task, url, http_method, data, json, downloaded_size)
    
    try:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", None)
        if not content_type or content_type == "application/json":
            raise Exception(f"Unsupported content type 'application/json'")

        total_length = response.headers.get("Content-Length", None)
        if total_length:
            total_size = int(total_length) + downloaded_size  # Including already downloaded size
        else:
            total_size = 0

        chunk_size = 1024 * 1024 * 10
        task.logging_last(f"{__name__}", f"---> downloaded {pretty_file_size(downloaded_size)}")
        
        for chunk in response.iter_content(chunk_size=chunk_size):
            if not chunk:  # Checking for empty chunks
                task.logging(f"{__name__}", "WARNING: Received empty data chunk")
                continue
                
            downloaded_size += len(chunk)
            task.logging_last(f"{__name__}", f"---> downloaded {pretty_file_size(downloaded_size)}")
            
            # Checking if enough data downloaded
            if total_size and downloaded_size >= total_size:
                task.logging(f"{__name__}", f"Download completed: {pretty_file_size(downloaded_size)}")

            yield chunk
        
        # Final size check
        if total_size and downloaded_size < total_size:
            task.logging(f"{__name__}", f"WARNING: Downloaded less than expected size: {pretty_file_size(downloaded_size)} of {pretty_file_size(total_size)}")

    finally:
        response.close()


def _streaming_download(
        task: Task,
        url: str,
        http_method: str = HTTPMethod.GET,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None,
) -> Generator[None, None, None]:
    response = _get_response(task, url, http_method, data, json)

    try:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", None)
        if not content_type or content_type == "application/json":
            raise Exception(f"Unsupported content type 'application/json'")

        total_length = response.headers.get("Content-Length", None)
        if total_length:
            total_size = int(total_length)
        else:
            total_size = 0

        downloaded_size = 0
        chunk_size = 1024 * 1024 * 10
        task.logging_last(f"{__name__}", f"---> downloaded {pretty_file_size(downloaded_size)}")
        
        for chunk in response.iter_content(chunk_size=chunk_size):
            if not chunk:  # Checking for empty chunks
                task.logging(f"{__name__}", "WARNING: Received empty data chunk")
                continue
                
            downloaded_size += len(chunk)
            task.logging_last(f"{__name__}", f"---> downloaded {pretty_file_size(downloaded_size)}")
            
            # Checking if enough data downloaded
            if total_size and downloaded_size >= total_size:
                task.logging(f"{__name__}", f"Download completed: {pretty_file_size(downloaded_size)}")

            yield chunk
        
        # Final size check
        if total_size and downloaded_size < total_size:
            task.logging(f"{__name__}", f"WARNING: Downloaded less than expected size: {pretty_file_size(downloaded_size)} of {pretty_file_size(total_size)}")

    finally:
        response.close()


def _get_response_with_range(
        task: Task,
        url: str,
        http_method: str = HTTPMethod.GET,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None,
        resume_from: int = 0,
) -> Response:
    """HTTP request with Range support for resume"""
    task.logging(f"{__name__}", f"Downloading package {'(resume)' if resume_from > 0 else ''}")
    
    headers = {}
    if resume_from > 0:
        headers['Range'] = f'bytes={resume_from}-'
        task.logging(f"{__name__}", f"Resume request from position {resume_from}")
    
    try:
        if http_method == HTTPMethod.GET:
            response = requests.get(url, stream=True, timeout=300, headers=headers)
        else:
            response = requests.post(url, data=data, json=json, stream=True, timeout=300, headers=headers)
        
        task.logging(f"{__name__}", f"Source URL: {url}")
        task.logging(f"{__name__}", f" -- Response code: {response.status_code}")
        task.logging(f"{__name__}", f" -- Content-type: {response.headers.get('Content-Type')}")
        task.logging(f"{__name__}", f" -- Content-Length: {response.headers.get('Content-Length', 'unknown')}")
        task.logging(f"{__name__}", f" -- Content-Range: {response.headers.get('Content-Range', 'unknown')}")
        
        return response
    except requests.exceptions.Timeout:
        task.logging(f"{__name__}", f"ERROR: Timeout downloading from {url}")
        raise Exception(f"Timeout downloading package from {url}")
    except requests.exceptions.ConnectionError as e:
        task.logging(f"{__name__}", f"ERROR: Connection error with {url}: {str(e)}")
        raise Exception(f"Connection error downloading package: {str(e)}")
    except Exception as e:
        task.logging(f"{__name__}", f"ERROR: Unexpected error downloading: {str(e)}")
        raise


def _get_response(
        task: Task,
        url: str,
        http_method: str = HTTPMethod.GET,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None,
) -> Response:
    task.logging(f"{__name__}", "Downloading package")
    try:
        if http_method == HTTPMethod.GET:
            response = requests.get(url, stream=True, timeout=300, verify=settings.SSL_VERIFY)  # 5 minute timeout
        else:
            response = requests.post(url, data=data, json=json, stream=True, timeout=300, verify=settings.SSL_VERIFY)
        
        task.logging(f"{__name__}", f"Source URL: {url}")
        task.logging(f"{__name__}", f" -- Response code: {response.status_code}")
        task.logging(f"{__name__}", f" -- Content-type: {response.headers.get('Content-Type')}")
        task.logging(f"{__name__}", f" -- Content-Length: {response.headers.get('Content-Length', 'unknown')}")
        
        return response
    except requests.exceptions.Timeout:
        task.logging(f"{__name__}", f"ERROR: Timeout downloading from {url}")
        raise Exception(f"Timeout downloading package from {url}")
    except requests.exceptions.ConnectionError as e:
        task.logging(f"{__name__}", f"ERROR: Connection error with {url}: {str(e)}")
        raise Exception(f"Connection error downloading package: {str(e)}")
    except Exception as e:
        task.logging(f"{__name__}", f"ERROR: Unexpected error downloading: {str(e)}")
        raise


def multithreaded_sync_to_s3(local_folder, bucket_name, destination_folder):
    bulkboto_agent.upload_dir_to_storage(
        bucket_name=bucket_name,
        local_dir=local_folder,
        storage_dir=destination_folder,
        n_threads=NUM_TRANSFER_THREADS,
    )


def sync_to_s3(local_folder, bucket_name, destination_folder):
    multithreaded_sync_to_s3(local_folder, bucket_name, destination_folder)
    # for subdir, dirs, files in os.walk(local_folder):
    #     for file in files:
    #         full_path = os.path.join(subdir, file)
    #         with open(full_path, 'rb') as data:
    #             s3_path = f"{prefix}{full_path[len(local_folder)+1:]}"
    #             s3_client.upload_fileobj(data, bucket_name, s3_path)
    #             print(f"---> upload to {s3_path}")


def count_files_and_size(directory):
    file_count = 0
    total_size = 0
    for root, _, files in os.walk(directory):
        file_count += len(files)
        total_size += sum(os.path.getsize(os.path.join(root, file)) for file in files)
    return file_count, total_size


def memory_usage():
    """Returns the memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)


def _upload_single_file(file_info, bucket_name, error_lock, first_error):
    """Worker for uploading single file to S3"""
    full_path, s3_path, content_type = file_info
    
    try:
        with open(full_path, 'rb') as data:
            s3_client.upload_fileobj(data, bucket_name, s3_path, ExtraArgs={"ContentType": content_type})
        return None
    except Exception as e:
        with error_lock:
            if first_error[0] is None:
                first_error[0] = (s3_path, e, traceback.format_exc())
        return e


def sync_to_s3_with_content_type(local_folder, bucket_name, destination_folder, task=None):
    start_time = time.time()
    
    # Collecting list of all files for upload
    files_to_upload = []
    for subdir, dirs, files in os.walk(local_folder):
        for file in files:
            full_path = os.path.join(subdir, file)
            s3_path = f"{destination_folder}{full_path[len(local_folder)+1:]}"
            ext = full_path.split(".")[-1]
            content_type = ext_to_content_type.get(ext, "application/octet-stream")
            files_to_upload.append((full_path, s3_path, content_type))
    
    total_files = len(files_to_upload)
    total_size = sum(os.path.getsize(f[0]) for f in files_to_upload)
    
    if total_files == 0:
        if task:
            task.logging(f"{__name__}", "S3 - no files to upload")
        return
    
    # Thread-safe variables for error tracking
    error_lock = Lock()
    first_error = [None]  # Using list for pass-by-reference
    
    # Parallel upload via ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=20) as executor:
        # Submitting all tasks for execution
        futures = {executor.submit(_upload_single_file, file_info, bucket_name, error_lock, first_error): file_info 
                   for file_info in files_to_upload}
        
        # Processing task completion
        for future in as_completed(futures):
            error = future.result()
            
            # If error occurred, stopping all tasks
            if error is not None:
                # Cancelling all remaining tasks
                for f in futures:
                    if not f.done():
                        f.cancel()
                # Exiting loop, shutdown will happen automatically on context exit
                break
        
        # If there was an error, raising exception
        if first_error[0] is not None:
            s3_path, exc, tb = first_error[0]
            error_msg = f"S3 - error uploading file {s3_path}: {exc}"
            if task:
                task.logging(f"{__name__}", f"[ERROR] {error_msg}, traceback: {tb}")
            raise Exception(error_msg) from exc
    
    # Final logging
    elapsed_time = time.time() - start_time
    total_size_mb = total_size / (1024 * 1024)
    
    if task:
        task.logging(
            f"{__name__}",
            f"S3 - upload completed successfully: {total_files} files, "
            f"{total_size_mb:.2f} MB, time: {elapsed_time:.2f} sec, "
            f"speed: {total_size_mb / elapsed_time:.2f} MB/sec"
        )


def cover_to_s3(cover_path, prefix, cover_name=None):
    with open(cover_path, 'rb') as data:
        if cover_name:
            s3_path = f"{prefix}/{cover_name}"
        else:
            s3_path = f"{prefix}/{cover_path.split('/')[-1]}"
        s3_client.upload_fileobj(data, settings.S3_BUCKET_COVER, s3_path, ExtraArgs={"ContentType": "image/jpeg"})


def zip_to_s3(offline_s3, bucket, key, task=None):
    config = TransferConfig(multipart_threshold=1024 * 25, max_concurrency=10,
                            multipart_chunksize=1024 * 25, use_threads=True)

    try:
        content_type = ext_to_content_type[key.split('.')[-1]]
    except:
        content_type = 'application/zip'

    s3_client.upload_file(offline_s3, bucket, key,
                          ExtraArgs={'ContentType': content_type},
                          Config=config
                          )

    if task:
        task.logging(f"{__name__}", f"zip_to_s3 > bucket: {bucket}, key: {key}")
        task.inc_uploaded_files()

file_to_s3 = zip_to_s3


def upload_stream_to_s3(stream, bucket, key, content_type=None, task=None):
    """Upload to S3 with content-type"""
    extra_args = {"ContentType": content_type} if content_type else None
    try:
        if extra_args:
            s3_client.upload_fileobj(stream, bucket, key, ExtraArgs=extra_args)
        else:
            s3_client.upload_fileobj(stream, bucket, key)
        if task:
            task.logging(f"{__name__}", f"upload_stream_to_s3 > bucket: {bucket}, key: {key}, content_type: {content_type}")
            task.inc_uploaded_files()
    except Exception as e:
        if task:
            task.logging(f"{__name__}", f"[ERROR] S3 - {e}, traceback: {traceback.format_exc()}")
        else:
            pass


def detect_cover_ext(path):
    if os.path.exists("{}/cover.png".format(path)):
        return os.path.join(path, "cover.png")
    if os.path.exists("{}/cover.jpg".format(path)):
        return os.path.join(path, "cover.jpg")


def optimize_image_file(path, filename):
    def get_proportional_height(width, initial_size):
        initial_width = initial_size[0]
        initial_height = initial_size[1]
        koeff = float(initial_width / initial_height)
        return int(width / koeff)

    img = Image.open(path)
    if img.width > settings.COVER_WIDTH:
        img = img.resize((settings.COVER_WIDTH,
                          get_proportional_height(settings.COVER_WIDTH, img.size)), Image.LANCZOS)

    original_filename = path
    file_name = original_filename.split('/')[-1]
    name, ext = file_name.split('.')

    if ext == "png":
        img = img.convert('RGB')

    file_path = '/'.join(path.split('/')[:-1])
    new_file_name = "{}/{}".format(file_path, filename)
    img.save(new_file_name, format="JPEG", optimize=True, quality=95)

    return new_file_name


def process_audio_file(tmp_path, audio_file):
    source_file_name = audio_file.split('/')[-1]
    dest_dir = os.path.dirname(audio_file)
    file_name = source_file_name.split(".")[0]
    file_name_m3u8 = f"{dest_dir}/{file_name}/{file_name}.m3u8"
    os.mkdir(f"{dest_dir}/{file_name}/")
    cmd = f"ffmpeg -y -i {audio_file} -c:a libmp3lame -q:a 0 -map 0:0 -f segment -segment_time 10 -segment_list {file_name_m3u8} -segment_format mpegts {dest_dir}/{file_name}/audio%03d.ts"
    subprocess.check_output(cmd.split(' '))
    os.remove(audio_file)

    return file_name_m3u8


def replace_text_in_file(filename, find_str, replace_str):
    with open(filename, 'r') as file:
        filedata = file.read()
    filedata = filedata.replace(find_str, replace_str)
    with open(filename, 'w') as file:
        file.write(filedata)


def encrypt_content(content, key):
    key_bytes = key.encode('utf-8')[:16].ljust(16)
    iv = os.urandom(16)
    cipher = Cipher(
        algorithms.AES(key_bytes),
        modes.CBC(iv),
        backend=default_backend()
    )
    
    encryptor = cipher.encryptor()
    content_bytes = content.encode('utf-8')
    padding_length = 16 - (len(content_bytes) % 16)
    content_bytes += bytes([padding_length] * padding_length)
    
    return iv + encryptor.update(content_bytes) + encryptor.finalize()


def count_files_in_zip_folder(zip_file_path, folder_name=None) -> int:
    count = 0
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        # List all files in the zip
        for file_info in zip_ref.infolist():
            # Check if the file is inside the desired folder
            if folder_name and file_info.filename.startswith(folder_name+"/"):
                count += 1
            else:
                count += 1

    return count
