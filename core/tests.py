from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.core.files.base import ContentFile

from core.models import Task, TaskStatus
from reference.models import Workspace, Source, DataType, PluginRepo, Plugin, ProcessingStage


# Minimal upload_to_s3 plugin source used in tests
UPLOAD_PLUGIN_SOURCE = b"""
import boto3
import requests
import os
from urllib.parse import urlparse

S3_BUCKET = "uddp-demo"
S3_REGION = "eu-west-3"
AWS_ACCESS_KEY = "test-key"
AWS_SECRET_KEY = "test-secret"

def execute(task):
    url = task.meta.get("url")
    if not url:
        raise ValueError("No 'url' field in task meta")
    task.logging("INFO", f"Downloading file from: {url}")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    filename = os.path.basename(urlparse(url).path) or "file"
    s3_key = f"uploads/{task.id}/{filename}"
    task.logging("INFO", f"Uploading to s3://{S3_BUCKET}/{s3_key}")
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=S3_REGION,
    )
    response.raw.decode_content = True
    s3.upload_fileobj(response.raw, S3_BUCKET, s3_key)
    output_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
    task.logging("INFO", f"Done! File available at: {output_url}")
    task.set_context({"output_url": output_url})
"""


def make_demo_pipeline():
    """Create a minimal pipeline fixture: Workspace → Source → Plugin → DataType → Stage."""
    workspace = Workspace.objects.create(name="Test Workspace")
    source = Source.objects.create(name="Test Source", key="test-token-abc", workspace=workspace)
    repo = PluginRepo.objects.create(name="Test Repo", url="http://localhost")
    plugin = Plugin.objects.create(name="Upload to S3", repo=repo)
    plugin.file.save("upload_to_s3.py", ContentFile(UPLOAD_PLUGIN_SOURCE), save=True)
    data_type = DataType.objects.create(
        name="File Upload",
        source=source,
        workspace=workspace,
        source_code="file_upload",
    )
    ProcessingStage.objects.create(
        data_type=data_type,
        step=1,
        plugin=plugin,
        active=True,
        workspace=workspace,
    )
    return workspace, source, data_type


class PublishViewAuthTest(TestCase):
    def setUp(self):
        self.client = Client()
        make_demo_pipeline()

    def test_missing_token_returns_403(self):
        resp = self.client.post(
            "/publish/",
            data='{"type": "file_upload", "url": "http://example.com/a.png"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_invalid_token_returns_403(self):
        resp = self.client.post(
            "/publish/",
            data='{"type": "file_upload", "url": "http://example.com/a.png"}',
            content_type="application/json",
            HTTP_AUTHORIZATION="Token wrong-token",
        )
        self.assertEqual(resp.status_code, 403)

    def test_unknown_type_returns_400(self):
        resp = self.client.post(
            "/publish/",
            data='{"type": "nonexistent_type", "url": "http://example.com/a.png"}',
            content_type="application/json",
            HTTP_AUTHORIZATION="Token test-token-abc",
        )
        self.assertEqual(resp.status_code, 400)


@override_settings(DEBUG=True)
class PublishPipelineTest(TestCase):
    """
    Integration-style test for the full publish → process pipeline.
    Mocks HTTP download and S3 upload to avoid external calls.
    """

    SOURCE_URL = "https://uddp-demo.s3.eu-west-3.amazonaws.com/source/rick.png"

    def setUp(self):
        self.client = Client()
        _, self.source, _ = make_demo_pipeline()

    @patch("boto3.client")
    @patch("requests.get")
    def test_publish_image_end_to_end(self, mock_get, mock_boto3):
        """
        POST /publish/ with a PNG URL:
        - pipeline should complete with STATUS_OK
        - output_url should be set in task context pointing to uploads/
        - S3 upload_fileobj should be called exactly once
        """
        # Mock HTTP response — simulate downloading rick.png
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.raw = MagicMock()
        fake_response.raw.decode_content = False
        mock_get.return_value = fake_response

        # Mock S3 client
        mock_s3 = MagicMock()
        mock_boto3.return_value = mock_s3

        resp = self.client.post(
            "/publish/",
            data=f'{{"type": "file_upload", "url": "{self.SOURCE_URL}"}}',
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.source.key}",
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["code"], "file_upload")
        task_id = data["task"]

        # Verify task completed successfully
        task = Task.objects.get(id=task_id)
        self.assertEqual(task.status, TaskStatus.STATUS_OK, msg=f"Task failed: {task.error_description}")

        # Verify output URL is set and points to uploads/
        output_url = task.context.get("output_url", "")
        self.assertIn("uploads/", output_url)
        self.assertIn("rick.png", output_url)

        # Verify S3 upload was called
        mock_s3.upload_fileobj.assert_called_once()
        call_args = mock_s3.upload_fileobj.call_args
        s3_key = call_args[0][2]  # positional: fileobj, bucket, key
        self.assertTrue(s3_key.startswith(f"uploads/{task_id}/"))
        self.assertIn("rick.png", s3_key)

    @patch("boto3.client")
    @patch("requests.get")
    def test_publish_failed_download_marks_task_error(self, mock_get, mock_boto3):
        """If the download returns a 404, the task should be marked as error."""
        import requests as req_lib

        fake_response = MagicMock()
        fake_response.status_code = 404
        fake_response.raise_for_status.side_effect = req_lib.exceptions.HTTPError("404")
        mock_get.return_value = fake_response

        resp = self.client.post(
            "/publish/",
            data=f'{{"type": "file_upload", "url": "{self.SOURCE_URL}"}}',
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.source.key}",
        )

        self.assertEqual(resp.status_code, 200)
        task = Task.objects.get(id=resp.json()["task"])
        self.assertEqual(task.status, TaskStatus.STATUS_ERROR)
        self.assertIsNotNone(task.error_description)
