"""Supply the Vulkan loader omitted by Electron's macOS distribution.

Chromium 151+ loads it dynamically even for its bundled SwiftShader driver.
Build official, digest-pinned sources instead of depending on system Vulkan.
"""
from pathlib import Path
import hashlib
import platform
import shutil
import subprocess
import tarfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.4.357.0"
SOURCES = {
    "Vulkan-Headers": "e87dce08116151f6b6d7de6b6faf41498e87e6cf848ff16fa3bd5402190ad4a3",
    "Vulkan-Loader": "54f2537df22313768da0317dda2abdaaab7711b4081c48c869a79db343d0ae70",
}


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def main():
    if platform.system() != "Darwin":
        return
    cache = ROOT / ".cache" / "vulkan"
    cache.mkdir(parents=True, exist_ok=True)
    sources = {}
    for name, digest in SOURCES.items():
        archive = cache / f"{name}-{VERSION}.tar.gz"
        if not archive.exists():
            url = f"https://github.com/KhronosGroup/{name}/archive/refs/tags/vulkan-sdk-{VERSION}.tar.gz"
            with urlopen(url, timeout=120) as response, archive.open("wb") as output:
                shutil.copyfileobj(response, output)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
            raise SystemExit(f"Digest mismatch for {name}; investigate the cached download")
        source = cache / f"{name}-vulkan-sdk-{VERSION}"
        if not source.exists():
            with tarfile.open(archive) as package:
                package.extractall(cache, filter="data")
        sources[name] = source
    prefix = cache / "installed"
    headers_build = cache / "headers-build"
    run("cmake", "-S", sources["Vulkan-Headers"], "-B", headers_build,
        f"-DCMAKE_INSTALL_PREFIX={prefix}", "-DVULKAN_HEADERS_ENABLE_TESTS=OFF")
    run("cmake", "--install", headers_build)
    build = cache / "loader-build"
    run("cmake", "-S", sources["Vulkan-Loader"], "-B", build,
        f"-DCMAKE_PREFIX_PATH={prefix}", "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=15.0", "-DBUILD_TESTS=OFF")
    run("cmake", "--build", build, "--parallel", "4")
    output = ROOT / "runtime" / "graphics"
    output.mkdir(parents=True, exist_ok=True)
    library = output / "libvulkan.dylib"
    shutil.copy2(build / "loader" / "libvulkan.dylib", library)
    # A relocatable install name, independent of the build directory.
    run("install_name_tool", "-id", "@rpath/libvulkan.dylib", library)
    run("codesign", "--force", "--sign", "-", library)
    dependencies = subprocess.check_output(["otool", "-L", library], text=True)
    if "/opt/homebrew/" in dependencies or "/usr/local/" in dependencies or str(cache) in dependencies:
        raise SystemExit(f"Vulkan loader has a non-relocatable dependency:\n{dependencies}")
    shutil.copytree(sources["Vulkan-Loader"] / "LICENSES", output / "LICENSES", dirs_exist_ok=True)
    (output / "SOURCE.txt").write_text(
        f"KhronosGroup/Vulkan-Loader vulkan-sdk-{VERSION}\n"
        + "\n".join(f"{name}: {digest}" for name, digest in SOURCES.items()) + "\n")
    # Electron 44 downloads its executable lazily on first require, not npm ci.
    subprocess.run(["node", "-e", "require('electron')"], cwd=ROOT, check=True)
    development = ROOT / "node_modules/electron/dist/Electron.app/Contents/Frameworks/Electron Framework.framework/Libraries"
    if not development.is_dir():
        raise SystemExit("Run npm ci before preparing macOS graphics")
    shutil.copy2(library, development / library.name)
    print("Relocatable macOS Vulkan loader prepared", flush=True)


if __name__ == "__main__":
    main()
