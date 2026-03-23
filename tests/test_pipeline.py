import io
from unittest.mock import patch, MagicMock, call

from django.test import TestCase, Client, override_settings
from django.core.files.base import ContentFile
from django.contrib.auth.models import User

from core.models import Task, TaskStatus, DataItem
from reference.models import (
    Workspace, Source, DataType, PluginRepo, Plugin, ProcessingStage,
    Consumer, Webhook, Team, TeamMember,
)


# ── Inline plugin sources ────────────────────────────────────────────────────

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
    s3 = boto3.client("s3", aws_access_key_id=AWS_ACCESS_KEY,
                      aws_secret_access_key=AWS_SECRET_KEY, region_name=S3_REGION)
    response.raw.decode_content = True
    s3.upload_fileobj(response.raw, S3_BUCKET, s3_key)
    output_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
    task.logging("INFO", f"Done! {output_url}")
    task.set_context({"output_url": output_url})
"""

RESIZE_PLUGIN_SOURCE = b"""
import io
import os
from urllib.parse import urlparse
import requests
from PIL import Image

def execute(task):
    url = task.meta.get("url")
    if not url:
        raise ValueError("No 'url' field in task meta")
    task.logging("INFO", f"Downloading image: {url}")
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    img = Image.open(io.BytesIO(response.content))
    original_size = f"{img.width}x{img.height}"
    new_w = max(1, img.width // 2)
    new_h = max(1, img.height // 2)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    filename = os.path.basename(urlparse(url).path) or "image.png"
    tmp_dir = task.context.get("tmp_dir", "/tmp")
    local_path = os.path.join(tmp_dir, f"resized_{filename}")
    resized.save(local_path)
    task.logging("INFO", f"Resized {original_size} -> {new_w}x{new_h}")
    task.set_context({"local_file": local_path, "resize_info": f"{original_size}->{new_w}x{new_h}",})
"""

UPLOAD_FROM_LOCAL_PLUGIN_SOURCE = b"""
import boto3
import os
from urllib.parse import urlparse

S3_BUCKET = "uddp-demo"
S3_REGION = "eu-west-3"
AWS_ACCESS_KEY = "test-key"
AWS_SECRET_KEY = "test-secret"

def execute(task):
    url = task.meta.get("url")
    filename = os.path.basename(urlparse(url).path) or "file"
    s3_key = f"uploads/{task.id}/{filename}"
    s3 = boto3.client("s3", aws_access_key_id=AWS_ACCESS_KEY,
                      aws_secret_access_key=AWS_SECRET_KEY, region_name=S3_REGION)
    local_file = task.context.get("local_file")
    if local_file and os.path.exists(local_file):
        task.logging("INFO", f"Uploading local file {local_file}")
        with open(local_file, "rb") as f:
            s3.upload_fileobj(f, S3_BUCKET, s3_key)
    else:
        import requests as req
        response = req.get(url, stream=True, timeout=60)
        response.raise_for_status()
        response.raw.decode_content = True
        s3.upload_fileobj(response.raw, S3_BUCKET, s3_key)
    output_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
    task.set_context({"output_url": output_url})
"""


def make_pipeline(source_code="file_upload", token="test-token", plugin_source=None):
    """Create workspace → source → plugin → data_type → stage fixture."""
    if plugin_source is None:
        plugin_source = UPLOAD_PLUGIN_SOURCE
    workspace = Workspace.objects.create(name=f"WS-{token}")
    source = Source.objects.create(name=f"Source-{token}", key=token, workspace=workspace)
    repo = PluginRepo.objects.create(name=f"Repo-{token}", url="http://localhost")
    plugin = Plugin.objects.create(name=f"Plugin-{token}", repo=repo)
    plugin.file.save("plugin.py", ContentFile(plugin_source), save=True)
    data_type = DataType.objects.create(
        name=source_code, source=source, workspace=workspace, source_code=source_code,
    )
    ProcessingStage.objects.create(
        data_type=data_type, step=1, plugin=plugin, active=True, workspace=workspace,
    )
    return workspace, source, data_type


# ── Model Tests ──────────────────────────────────────────────────────────────

class TaskModelTest(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(name="Test WS")
        self.source = Source.objects.create(name="Test Source", key="key123", workspace=self.workspace)
        self.task = Task.objects.create(source=self.source, context={}, status=TaskStatus.STATUS_PROGRESS)

    def test_str(self):
        self.assertEqual(str(self.task), f"Task #{self.task.id}")

    def test_logging_appends(self):
        self.task.logging("INFO", "first message")
        self.task.logging("INFO", "second message")
        task = Task.objects.get(id=self.task.id)
        self.assertIn("first message", task.log)
        self.assertIn("second message", task.log)
        self.assertEqual(task.last_log, "[INFO] second message")

    def test_logging_last_replaces_last_line(self):
        self.task.logging("INFO", "initial")
        self.task.logging_last("INFO", "updated")
        task = Task.objects.get(id=self.task.id)
        lines = task.log.strip().split("\n")
        self.assertEqual(lines[-1], "[INFO] updated")

    def test_logging_truncates_last_log(self):
        long_msg = "x" * 300
        self.task.logging("INFO", long_msg)
        task = Task.objects.get(id=self.task.id)
        self.assertLessEqual(len(task.last_log), 200)

    def test_set_error(self):
        self.task.set_error("something broke")
        task = Task.objects.get(id=self.task.id)
        self.assertEqual(task.status, TaskStatus.STATUS_ERROR)
        self.assertEqual(task.error_description, "something broke")
        self.assertIn("something broke", task.log)

    def test_set_context_merges(self):
        self.task.context = {"existing": "value"}
        self.task.save()
        self.task.set_context({"new_key": "new_value"})
        task = Task.objects.get(id=self.task.id)
        self.assertEqual(task.context["existing"], "value")
        self.assertEqual(task.context["new_key"], "new_value")


class ReferenceModelStrTest(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(name="My Workspace")
        self.source = Source.objects.create(name="My Source", key="k", workspace=self.workspace)
        self.repo = PluginRepo.objects.create(name="My Repo", url="http://example.com")
        self.plugin = Plugin.objects.create(name="My Plugin", repo=self.repo)

    def test_workspace_str(self):
        self.assertEqual(str(self.workspace), "My Workspace")

    def test_source_str(self):
        self.assertEqual(str(self.source), "My Source")

    def test_plugin_repo_str(self):
        self.assertEqual(str(self.repo), "My Repo")

    def test_plugin_str(self):
        self.assertEqual(str(self.plugin), "My Plugin")

    def test_data_type_str(self):
        dt = DataType.objects.create(name="My DT", source=self.source, workspace=self.workspace, source_code="x")
        self.assertIn("My DT", str(dt))

    def test_processing_stage_str(self):
        dt = DataType.objects.create(name="DT", source=self.source, workspace=self.workspace, source_code="y")
        stage = ProcessingStage.objects.create(data_type=dt, step=3, workspace=self.workspace, plugin=self.plugin)
        self.assertIn("3", str(stage))

    def test_team_str(self):
        team = Team.objects.create(workspace=self.workspace, name="Dev Team")
        self.assertIn("Dev Team", str(team))

    def test_team_member_str(self):
        team = Team.objects.create(workspace=self.workspace, name="Dev Team")
        user = User.objects.create_user("testuser", password="pass")
        member = TeamMember.objects.create(team=team, user=user, role=TeamMember.Roles.DEVELOPER)
        self.assertIn("testuser", str(member))

    def test_consumer_str(self):
        consumer = Consumer.objects.create(name="My Consumer", workspace=self.workspace)
        self.assertEqual(str(consumer), "My Consumer")

    def test_webhook_str(self):
        webhook = Webhook.objects.create(url="http://example.com/hook", workspace=self.workspace)
        self.assertIn("http://example.com/hook", str(webhook))

    def test_data_item_str(self):
        task = Task.objects.create(source=self.source, context={})
        item = DataItem.objects.create(source=self.source, task=task, workspace=self.workspace)
        s = str(item)
        self.assertIsNotNone(s)


# ── Auth Tests ───────────────────────────────────────────────────────────────

class PublishViewAuthTest(TestCase):
    def setUp(self):
        self.client = Client()
        make_pipeline()

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

    def test_malformed_authorization_header_returns_403(self):
        resp = self.client.post(
            "/publish/",
            data='{"type": "file_upload", "url": "http://example.com/a.png"}',
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer notright",
        )
        self.assertEqual(resp.status_code, 403)

    def test_unknown_type_returns_400(self):
        _, source, _ = make_pipeline(token="tok2")
        resp = self.client.post(
            "/publish/",
            data='{"type": "nonexistent", "url": "http://example.com/a.png"}',
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {source.key}",
        )
        self.assertEqual(resp.status_code, 400)

    def test_invalid_json_returns_400(self):
        _, source, _ = make_pipeline(token="tok3")
        resp = self.client.post(
            "/publish/",
            data="not-json",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {source.key}",
        )
        self.assertEqual(resp.status_code, 400)


# ── Status View Tests ────────────────────────────────────────────────────────

class StatusViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        _, self.source, self.dt = make_pipeline(token="status-tok")

    def _create_task(self, status=TaskStatus.STATUS_OK):
        task = Task.objects.create(
            source=self.source, data_type=self.dt,
            context={}, status=status, progress=100,
        )
        return task

    def test_status_ok(self):
        task = self._create_task(TaskStatus.STATUS_OK)
        resp = self.client.get(
            f"/publish/status/{task.id}/",
            HTTP_AUTHORIZATION=f"Token {self.source.key}",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["task"], task.id)
        self.assertEqual(data["status"], TaskStatus.STATUS_OK)

    def test_status_error(self):
        task = self._create_task(TaskStatus.STATUS_ERROR)
        task.error_description = "test error"
        task.save()
        resp = self.client.get(
            f"/publish/status/{task.id}/",
            HTTP_AUTHORIZATION=f"Token {self.source.key}",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], TaskStatus.STATUS_ERROR)
        self.assertEqual(data["error"], "test error")

    def test_status_invalid_token(self):
        task = self._create_task()
        resp = self.client.get(
            f"/publish/status/{task.id}/",
            HTTP_AUTHORIZATION="Token badtoken",
        )
        self.assertEqual(resp.status_code, 403)

    def test_status_not_found(self):
        resp = self.client.get(
            "/publish/status/99999/",
            HTTP_AUTHORIZATION=f"Token {self.source.key}",
        )
        self.assertEqual(resp.status_code, 400)

    def test_status_with_data_item(self):
        task = self._create_task(TaskStatus.STATUS_OK)
        DataItem.objects.create(
            type=self.dt, source=self.source, task=task,
            workspace=task.source.workspace,
        )
        resp = self.client.get(
            f"/publish/status/{task.id}/",
            HTTP_AUTHORIZATION=f"Token {self.source.key}",
        )
        self.assertEqual(resp.status_code, 200)


# ── Single-Stage Pipeline Tests ──────────────────────────────────────────────

@override_settings(DEBUG=True)
class SingleStagePipelineTest(TestCase):
    SOURCE_URL = "https://uddp-demo.s3.eu-west-3.amazonaws.com/source/rick.png"

    def setUp(self):
        self.client = Client()
        _, self.source, _ = make_pipeline(source_code="file_upload", token="single-tok")

    @patch("boto3.client")
    @patch("requests.get")
    def test_upload_image_success(self, mock_get, mock_boto3):
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.raw = MagicMock()
        fake_response.raw.decode_content = False
        mock_get.return_value = fake_response
        mock_boto3.return_value = MagicMock()

        resp = self.client.post(
            "/publish/",
            data=f'{{"type": "file_upload", "url": "{self.SOURCE_URL}"}}',
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.source.key}",
        )

        self.assertEqual(resp.status_code, 200)
        task_id = resp.json()["task"]
        task = Task.objects.get(id=task_id)
        self.assertEqual(task.status, TaskStatus.STATUS_OK, msg=f"Log: {task.log}")
        self.assertIn("uploads/", task.context.get("output_url", ""))
        self.assertIn("rick.png", task.context.get("output_url", ""))

    @patch("boto3.client")
    @patch("requests.get")
    def test_download_failure_marks_error(self, mock_get, mock_boto3):
        import requests as req_lib
        fake = MagicMock()
        fake.raise_for_status.side_effect = req_lib.exceptions.HTTPError("404")
        mock_get.return_value = fake

        resp = self.client.post(
            "/publish/",
            data=f'{{"type": "file_upload", "url": "{self.SOURCE_URL}"}}',
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.source.key}",
        )

        self.assertEqual(resp.status_code, 200)
        task = Task.objects.get(id=resp.json()["task"])
        self.assertEqual(task.status, TaskStatus.STATUS_ERROR)

    @patch("boto3.client")
    @patch("requests.get")
    def test_response_contains_task_id_and_code(self, mock_get, mock_boto3):
        fake = MagicMock()
        fake.raw = MagicMock()
        mock_get.return_value = fake
        mock_boto3.return_value = MagicMock()

        resp = self.client.post(
            "/publish/",
            data=f'{{"type": "file_upload", "url": "{self.SOURCE_URL}"}}',
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.source.key}",
        )

        data = resp.json()
        self.assertIn("task", data)
        self.assertEqual(data["code"], "file_upload")


# ── Two-Stage Pipeline Tests ─────────────────────────────────────────────────

@override_settings(DEBUG=True)
class TwoStagePipelineTest(TestCase):
    """Tests the resize → upload two-stage pipeline with mocked PIL and S3."""

    SOURCE_URL = "https://uddp-demo.s3.eu-west-3.amazonaws.com/source/rick.png"

    def setUp(self):
        self.client = Client()
        # Stage 1: resize
        self.workspace = Workspace.objects.create(name="Two-Stage WS")
        self.source = Source.objects.create(name="Two-Stage Source", key="two-stage-tok", workspace=self.workspace)
        repo = PluginRepo.objects.create(name="Two-Stage Repo", url="http://localhost")

        resize_plugin = Plugin.objects.create(name="Resize", repo=repo)
        resize_plugin.file.save("resize.py", ContentFile(RESIZE_PLUGIN_SOURCE), save=True)

        upload_plugin = Plugin.objects.create(name="Upload", repo=repo)
        upload_plugin.file.save("upload.py", ContentFile(UPLOAD_FROM_LOCAL_PLUGIN_SOURCE), save=True)

        self.data_type = DataType.objects.create(
            name="Image Resize", source=self.source,
            workspace=self.workspace, source_code="image_resize",
        )
        ProcessingStage.objects.create(
            data_type=self.data_type, step=1, plugin=resize_plugin,
            active=True, workspace=self.workspace,
        )
        ProcessingStage.objects.create(
            data_type=self.data_type, step=2, plugin=upload_plugin,
            active=True, workspace=self.workspace,
        )

    @patch("boto3.client")
    @patch("requests.get")
    def test_two_stage_resize_and_upload(self, mock_get, mock_boto3):
        """Full 2-stage: resize image 50% → upload to S3."""
        from PIL import Image as PilImage

        # Create a real 100x80 image in memory to return from requests.get
        img_bytes = io.BytesIO()
        PilImage.new("RGB", (100, 80), color="red").save(img_bytes, format="PNG")
        img_bytes.seek(0)

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.content = img_bytes.read()
        fake_response.raise_for_status = MagicMock()
        mock_get.return_value = fake_response

        mock_s3 = MagicMock()
        mock_boto3.return_value = mock_s3

        resp = self.client.post(
            "/publish/",
            data=f'{{"type": "image_resize", "url": "{self.SOURCE_URL}"}}',
            content_type="application/json",
            HTTP_AUTHORIZATION="Token two-stage-tok",
        )

        self.assertEqual(resp.status_code, 200)
        task_id = resp.json()["task"]
        task = Task.objects.get(id=task_id)

        self.assertEqual(task.status, TaskStatus.STATUS_OK, msg=f"Log:\n{task.log}")

        # Verify resize happened: resize_info should be set
        self.assertIn("resize_info", task.context)

        # Verify S3 upload was called
        mock_s3.upload_fileobj.assert_called_once()

        # Output URL should contain task id
        output_url = task.context.get("output_url", "")
        self.assertIn("uploads/", output_url)
        self.assertIn("rick.png", output_url)

    @patch("boto3.client")
    @patch("requests.get")
    def test_resize_stage_failure_marks_error(self, mock_get, mock_boto3):
        """If download fails in stage 1, task should be marked as error."""
        import requests as req_lib
        fake = MagicMock()
        fake.raise_for_status.side_effect = req_lib.exceptions.HTTPError("503")
        mock_get.return_value = fake

        resp = self.client.post(
            "/publish/",
            data=f'{{"type": "image_resize", "url": "{self.SOURCE_URL}"}}',
            content_type="application/json",
            HTTP_AUTHORIZATION="Token two-stage-tok",
        )

        self.assertEqual(resp.status_code, 200)
        task = Task.objects.get(id=resp.json()["task"])
        self.assertEqual(task.status, TaskStatus.STATUS_ERROR)


# ── Pipeline Edge Cases ──────────────────────────────────────────────────────

@override_settings(DEBUG=True)
class PipelineEdgeCaseTest(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("boto3.client")
    @patch("requests.get")
    def test_all_stages_disabled_completes_ok(self, mock_get, mock_boto3):
        """A data type with no active stages should still complete OK."""
        _, source, dt = make_pipeline(token="edge-tok")
        # Disable all stages
        dt.processing_stages.update(active=False)

        resp = self.client.post(
            "/publish/",
            data='{"type": "file_upload", "url": "http://example.com/x.png"}',
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {source.key}",
        )
        self.assertEqual(resp.status_code, 200)
        task = Task.objects.get(id=resp.json()["task"])
        self.assertEqual(task.status, TaskStatus.STATUS_OK)
