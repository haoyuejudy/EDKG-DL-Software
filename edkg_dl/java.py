"""Java runtime provisioning for PaDEL feature extraction."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path
from threading import Lock

from platformdirs import user_cache_dir

from .exceptions import AssetDownloadError


JAVA_MAJOR_VERSION = 17
TEMURIN_API_URL = (
    "https://api.adoptium.net/v3/binary/latest/"
    f"{JAVA_MAJOR_VERSION}/ga/{{os}}/{{architecture}}/jre/hotspot/normal/eclipse"
)

_INSTALL_LOCK = Lock()


def default_java_dir() -> Path:
    """Return the per-user cache directory used to store the Java runtime.

    Returns:
        Platform-appropriate cache path such as
        ``~/.cache/edkg-dl/java`` on Linux.
    """
    return Path(user_cache_dir("edkg-dl")) / "java"


def ensure_java(java_dir: str | Path | None = None) -> Path | None:
    """Guarantee that a ``java`` executable is available to the current process.

    Resolution order: an existing ``java`` on ``PATH`` is reused as-is;
    otherwise a Temurin JRE matching the current OS and architecture is
    downloaded into the cache directory and its ``bin`` directory is prepended
    to ``PATH`` so that PaDEL-Descriptor can invoke it. The installation is
    atomic (extraction happens in a temporary directory that is renamed on
    success), so an interrupted download never leaves a broken runtime behind.

    Args:
        java_dir: Target directory; defaults to the per-user cache dir.

    Returns:
        Absolute path of the Java home directory that was downloaded, or
        ``None`` when a system-wide Java was already available.

    Raises:
        AssetDownloadError: Raised when no matching runtime exists for the
            platform or the download, extraction, or verification fails.
    """
    if shutil.which("java"):
        return None

    with _INSTALL_LOCK:
        if shutil.which("java"):
            return None
        install_root = default_java_dir() if java_dir is None else Path(java_dir).expanduser()
        operating_system, architecture, slug = _adoptium_platform()
        runtime_dir = install_root / slug
        if _java_binary(runtime_dir) is None:
            runtime_dir = _install_runtime(install_root, operating_system, architecture, slug)
        _prepend_to_path(runtime_dir / "bin")
        return runtime_dir


def _adoptium_platform() -> tuple[str, str, str]:
    """Map the current machine onto Adoptium release identifiers.

    Returns:
        Triple of ``(operating_system, architecture, cache_slug)`` such as
        ``("linux", "x64", "linux-x64")``.

    Raises:
        AssetDownloadError: Raised when no Temurin JRE build matches the machine.
    """
    system = platform.system().lower()
    machine = platform.machine().lower()
    architecture = {
        "amd64": "x64",
        "x86_64": "x64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
    }.get(machine)
    operating_system = {"linux": "linux", "darwin": "mac", "windows": "windows"}.get(system)
    if system == "linux" and Path("/etc/alpine-release").exists():
        operating_system = "alpine-linux"
    if architecture is None or operating_system is None:
        raise AssetDownloadError(
            f"No Temurin JRE {JAVA_MAJOR_VERSION} build for {system}/{machine}; "
            "install a Java 8+ runtime manually and add it to PATH"
        )
    return operating_system, architecture, f"{operating_system}-{architecture}"


def _install_runtime(
    install_root: Path,
    operating_system: str,
    architecture: str,
    slug: str,
) -> Path:
    """Download and install a Temurin JRE into ``install_root``.

    Args:
        install_root: Cache directory that receives the extracted runtime.
        operating_system: Adoptium OS identifier (``linux``, ``mac``, ...).
        architecture: Adoptium architecture identifier (``x64``, ``aarch64``).
        slug: Cache directory name for this platform.

    Returns:
        Absolute path of the installed Java home directory.

    Raises:
        AssetDownloadError: Raised when the transfer, extraction, or runtime
            verification fails.
    """
    runtime_dir = install_root / slug
    if _java_binary(runtime_dir) is not None:
        return runtime_dir
    url = TEMURIN_API_URL.format(os=operating_system, architecture=architecture)
    install_root.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="edkg-dl-java-", dir=install_root) as temporary:
            workspace = Path(temporary)
            archive = workspace / ("jre.zip" if operating_system == "windows" else "jre.tar.gz")
            _download(url, archive)
            java_home = _extract(archive, workspace)
            _verify_runtime(java_home)
            java_home.replace(runtime_dir)
    except AssetDownloadError:
        raise
    except Exception as exc:
        raise AssetDownloadError(f"Failed to install Java runtime from {url}: {exc}") from exc
    return runtime_dir


def _download(url: str, archive: Path) -> None:
    """Stream a runtime archive from ``url`` into ``archive``.

    Args:
        url: Adoptium API endpoint serving the archive.
        archive: Destination file path.
    """
    import requests

    with requests.get(url, stream=True, allow_redirects=True, timeout=(10, 600)) as response:
        response.raise_for_status()
        with archive.open("wb") as stream:
            for block in response.iter_content(chunk_size=1024 * 1024):
                stream.write(block)


def _extract(archive: Path, workspace: Path) -> Path:
    """Extract a runtime archive and return its Java home directory.

    Args:
        archive: ``.tar.gz`` or ``.zip`` archive downloaded from Adoptium.
        workspace: Directory to extract into.

    Returns:
        Absolute path of the extracted directory containing ``bin/java``.

    Raises:
        AssetDownloadError: Raised when the archive layout is unexpected.
    """
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(workspace)
    else:
        with tarfile.open(archive) as bundle:
            bundle.extractall(workspace, filter="data")
    for entry in sorted(workspace.iterdir()):
        if entry.is_dir() and _java_binary(entry) is not None:
            return entry
    raise AssetDownloadError(f"Java runtime archive has an unexpected layout: {archive.name}")


def _verify_runtime(java_home: Path) -> None:
    """Confirm that the downloaded runtime can execute ``java -version``.

    Args:
        java_home: Extracted Java home directory.

    Raises:
        AssetDownloadError: Raised when the runtime fails to start.
    """
    try:
        completed = subprocess.run(
            [str(_java_binary(java_home)), "-version"],
            capture_output=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AssetDownloadError(f"Downloaded Java runtime failed to start: {exc}") from exc
    if completed.returncode != 0:
        details = completed.stderr.decode(errors="replace").strip()
        raise AssetDownloadError(
            f"Downloaded Java runtime failed to start: exit code {completed.returncode}: {details}"
        )


def _java_binary(java_home: Path) -> Path | None:
    """Return the ``java`` executable inside a Java home directory.

    Args:
        java_home: Candidate Java home directory.

    Returns:
        Path of the executable, or ``None`` when it is absent.
    """
    candidate = java_home / "bin" / ("java.exe" if os.name == "nt" else "java")
    return candidate if candidate.is_file() else None


def _prepend_to_path(bin_dir: Path) -> None:
    """Prepend a Java ``bin`` directory to the process ``PATH``.

    Args:
        bin_dir: Directory containing the ``java`` executable.
    """
    current = os.environ.get("PATH", "")
    if str(bin_dir) in current.split(os.pathsep):
        return
    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{current}" if current else str(bin_dir)
