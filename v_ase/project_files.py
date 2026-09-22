"""Private, session-bound project file targets with conflict-safe replacement."""

from __future__ import annotations

import hashlib
import errno
import os
import stat
import tempfile
import uuid
from pathlib import Path
from typing import Any


def _version(path: Path) -> str:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("The project target is no longer a regular file.")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"{info.st_dev}:{info.st_ino}:{info.st_size}:{info.st_mtime_ns}:{digest.hexdigest()}"


def bind_project_source(session: Any, source: str | Path, format: str) -> dict[str, str]:
    """Authorize exactly the successfully opened project, never its directory."""
    if format not in {"vase", "html"}:
        raise ValueError("Only editable project files may be bound for Save.")
    path = Path(source).resolve(strict=True)
    version = _version(path)
    binding = {
        "id": uuid.uuid4().hex,
        "path": str(path),
        "format": format,
        "version": version,
    }
    session.project_file_binding = binding
    return {"id": binding["id"], "version": version, "format": format}


def current_project_binding(session: Any) -> dict[str, str] | None:
    binding = getattr(session, "project_file_binding", None)
    if not binding:
        return None
    return {
        "id": binding["id"],
        "version": binding["version"],
        "format": binding["format"],
        "filename": Path(binding["path"]).name,
    }


def replace_bound_project(
    session: Any,
    binding_id: str,
    expected_version: str,
    format: str,
    artifact: bytes | str | Path,
) -> dict[str, str]:
    """Atomically replace a bound source only if its exact prior bytes survive."""
    binding = getattr(session, "project_file_binding", None)
    if not binding or binding_id != binding["id"] or format != binding["format"]:
        raise PermissionError("This session has no matching writable project target.")
    if expected_version != binding["version"]:
        raise FileExistsError("The project binding changed. Reload or Save As.")
    target = Path(binding["path"])
    if _version(target) != expected_version:
        raise FileExistsError("The project was changed outside v_ase. Reload or Save As.")
    mode = stat.S_IMODE(target.stat().st_mode)
    staged_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{target.name}.vase-save-", suffix=".tmp",
            dir=target.parent, delete=False,
        ) as staged:
            staged_path = Path(staged.name)
            if isinstance(artifact, bytes):
                staged.write(artifact)
            else:
                with Path(artifact).open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        staged.write(chunk)
            staged.flush()
            os.fsync(staged.fileno())
        os.chmod(staged_path, mode)
        # Check again after potentially expensive rendering/serialization.
        if _version(target) != expected_version:
            raise FileExistsError("The project changed while saving. Reload or Save As.")
        os.replace(staged_path, target)
        staged_path = None
        try:
            # Windows and some mounted filesystems do not permit opening or
            # fsyncing a directory descriptor. The file itself was fsynced
            # before atomic replace; retain the new binding either way.
            if os.name != "nt":
                directory_fd = None
                try:
                    directory_fd = os.open(target.parent, os.O_RDONLY)
                    os.fsync(directory_fd)
                except OSError as exc:
                    if exc.errno not in {errno.EINVAL, errno.EBADF, errno.ENOTSUP,
                                         errno.EOPNOTSUPP, errno.EACCES, errno.EPERM}:
                        raise
                finally:
                    if directory_fd is not None:
                        os.close(directory_fd)
        finally:
            binding["version"] = _version(target)
        return current_project_binding(session)
    finally:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)
