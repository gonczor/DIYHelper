import asyncio

from google.cloud import storage as gcp_storage


class GCSStorage:
    def __init__(self, bucket: str, prefix: str = "") -> None:
        self._bucket_name = bucket
        self._prefix = prefix.strip("/")

    async def save(
        self,
        path: str,
        content: bytes,
        *,
        content_type: str | None = None,
    ) -> str:
        object_name = "/".join(part for part in (self._prefix, path.lstrip("/")) if part)
        await asyncio.to_thread(self._upload, object_name, content, content_type)
        return f"gs://{self._bucket_name}/{object_name}"

    def _upload(self, object_name: str, content: bytes, content_type: str | None) -> None:
        client = gcp_storage.Client()
        blob = client.bucket(self._bucket_name).blob(object_name)
        blob.upload_from_string(content, content_type=content_type)
