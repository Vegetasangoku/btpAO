"""
Storage Service: S3 / MinIO / Local Sandboxed Storage with Tenant Isolation
All objects are partitioned strictly under /tenants/{tenant_id}/...
"""
import io
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Optional, Union
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from app.core.config import settings


class StorageService:
    def __init__(self):
        self.bucket_name = settings.S3_BUCKET_NAME
        self.local_storage_dir = Path("./local_storage")
        self.local_storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.s3_client = None
        try:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=settings.S3_REGION,
                config=Config(
                    signature_version="s3v4",
                    connect_timeout=0.5,
                    read_timeout=0.5,
                    retries={"max_attempts": 0},
                ),
                use_ssl=settings.S3_USE_SSL,
            )
            # Ensure bucket exists or fall back to local
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
            except Exception:
                try:
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                except Exception:
                    self.s3_client = None
        except Exception as e:
            self.s3_client = None
            print(f"[StorageService] S3 initialization notice (fallback to local folder): {e}")

    def build_tenant_path(self, tenant_id: str, subpath: str) -> str:
        """
        Guarantees strict tenant path prefix: tenants/{tenant_id}/{clean_subpath}
        """
        clean_subpath = subpath.lstrip("/")
        return f"tenants/{tenant_id}/{clean_subpath}"

    def upload_file(
        self,
        tenant_id: str,
        subpath: str,
        file_obj: Union[BinaryIO, bytes, io.BytesIO],
        content_type: str = "application/octet-stream",
    ) -> str:
        s3_key = self.build_tenant_path(tenant_id, subpath)

        # Normalise to raw bytes so we can always re-create a fresh stream
        if isinstance(file_obj, (bytes, bytearray)):
            raw_bytes = bytes(file_obj)
        elif isinstance(file_obj, io.BytesIO):
            file_obj.seek(0)
            raw_bytes = file_obj.read()
        else:
            # Generic file-like object
            raw_bytes = file_obj.read()

        # 1. Try S3 upload
        if self.s3_client:
            try:
                self.s3_client.upload_fileobj(
                    io.BytesIO(raw_bytes),
                    self.bucket_name,
                    s3_key,
                    ExtraArgs={"ContentType": content_type},
                )
                return s3_key
            except Exception as e:
                print(f"[StorageService] S3 upload error, saving to local: {e}")

        # 2. Local File System Fallback — always use a fresh BytesIO
        local_path = self.local_storage_dir / s3_key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(raw_bytes)

        return s3_key

    def download_file(self, tenant_id: str, s3_key: str) -> bytes:
        # Validate tenant prefix
        expected_prefix = f"tenants/{tenant_id}/"
        if not s3_key.startswith(expected_prefix) and not s3_key.startswith(f"/{expected_prefix}"):
            raise ValueError(f"Unauthorized storage access: {s3_key} does not belong to tenant {tenant_id}")

        clean_key = s3_key.lstrip("/")

        # 1. Try S3
        if self.s3_client:
            try:
                buffer = io.BytesIO()
                self.s3_client.download_fileobj(self.bucket_name, clean_key, buffer)
                buffer.seek(0)
                return buffer.read()
            except Exception as e:
                print(f"[StorageService] S3 download error, checking local: {e}")

        # 2. Local Fallback
        local_path = self.local_storage_dir / clean_key
        if local_path.exists():
            with open(local_path, "rb") as f:
                return f.read()

        raise FileNotFoundError(f"File not found in storage: {s3_key}")

    def get_presigned_url(self, tenant_id: str, s3_key: str, expires_in: int = 3600) -> str:
        clean_key = s3_key.lstrip("/")
        if self.s3_client:
            try:
                return self.s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": clean_key},
                    ExpiresIn=expires_in,
                )
            except Exception:
                pass
        return f"/api/storage/files/{clean_key}"


storage_service = StorageService()
