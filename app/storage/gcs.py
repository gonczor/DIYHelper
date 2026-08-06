import asyncio

from google.cloud import storage as gcp_storage

from app.storage.base import Storage


class GCSStorage(Storage):
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

    async def load(self, path: str) -> bytes:
        object_name = self._object_name(path)
        return await asyncio.to_thread(self._download, object_name)

    async def list_items(self, prefix: str) -> list[str]:
        object_prefix = self._object_name(prefix)
        paths = await asyncio.to_thread(self._list, object_prefix)
        storage_prefix = f"{self._prefix}/" if self._prefix else ""
        return sorted(path.removeprefix(storage_prefix) for path in paths)

    def _object_name(self, path: str) -> str:
        return "/".join(part for part in (self._prefix, path.lstrip("/")) if part)

    def _download(self, object_name: str) -> bytes:
        client = gcp_storage.Client()
        return client.bucket(self._bucket_name).blob(object_name).download_as_bytes()

    def _list(self, prefix: str) -> list[str]:
        client = gcp_storage.Client()
        return [blob.name for blob in client.list_blobs(self._bucket_name, prefix=prefix)]
