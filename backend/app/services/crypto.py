"""Cryptographic Hashing Utility for Video Evidence Tamper Protection.

Provides deterministic SHA-256 calculation for uploaded image evidence bytes
and files on disk, ensuring chain-of-custody verification.
"""

import hashlib
import os
from typing import Union


def hash_image_bytes(image_bytes: bytes) -> str:
    """Calculate the SHA-256 hexadecimal digest for raw image bytes.

    Args:
        image_bytes: Raw binary content of the image.

    Returns:
        A 64-character lowercase hexadecimal string representing the SHA-256 hash.

    Raises:
        ValueError: If image_bytes is None or empty.
    """
    if not isinstance(image_bytes, (bytes, bytearray)):
        raise TypeError(f"Expected bytes or bytearray, got {type(image_bytes).__name__}")
    if len(image_bytes) == 0:
        raise ValueError("Cannot calculate hash of empty byte sequence.")

    hasher = hashlib.sha256()
    hasher.update(image_bytes)
    return hasher.hexdigest()


def hash_file(file_path: Union[str, os.PathLike], chunk_size: int = 65536) -> str:
    """Calculate the SHA-256 hexadecimal digest for a file stored on disk.

    Uses streaming chunks to maintain low memory footprint even with high-resolution
    evidence captures.

    Args:
        file_path: Absolute or relative path to the image file.
        chunk_size: Buffer read size in bytes (default: 64KB).

    Returns:
        A 64-character lowercase hexadecimal string representing the SHA-256 hash.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If the file is empty.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Evidence file not found: {file_path}")

    hasher = hashlib.sha256()
    bytes_read = 0
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
            bytes_read += len(chunk)

    if bytes_read == 0:
        raise ValueError(f"Evidence file is empty: {file_path}")

    return hasher.hexdigest()
