"""Build script for workFLOw watchface AAB.

Usage: python build.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

# Paths
SDK = r"c:\Users\flori\AppData\Local\Android\Sdk"
AAPT2 = os.path.join(SDK, "build-tools", "36.0.0", "aapt2.exe")
ANDROID_JAR = os.path.join(SDK, "platforms", "android-36", "android.jar")
JARSIGNER = r"c:\Program Files\Android\Android Studio\jbr\bin\jarsigner.exe"
KEYSTORE = r"c:\Users\flori\WatchFaceStudio\keystore\keystore.jks"
KEY_ALIAS = "key0"
KEY_PASS = "Flo61215"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(SCRIPT_DIR, "src")

# The project directory is synced by Google Drive, which locks directory
# creation and causes intermittent WinError 2/5. To avoid this, all build
# artifacts are created in a local TEMP working directory and only the final
# signed AAB is copied back into the project's "out" folder.
WORK = os.path.join(tempfile.gettempdir(), "workFLOw_build")
BUILD = os.path.join(WORK, "build")
OUT = os.path.join(WORK, "out")

# Final destination for the signed AAB. The project's "out" subfolder cannot
# be created because Google Drive locks directory creation in the synced
# project tree, so the finished AAB is written to the project root instead
# (where the previous AAB already lives). Copying a single file works fine.
FINAL_OUT = SCRIPT_DIR


def run(cmd, **kwargs):
    """Run a command and print output."""
    print(f"  > {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        print(f"ERROR: {result.stderr.strip()}")
        sys.exit(1)
    return result


import time


def ensure_dir(path):
    """Create a directory, working around Google Drive locking the synced
    project folder (where os.makedirs may raise WinError 2/5)."""
    if os.path.isdir(path):
        return
    last_err = None
    for _ in range(5):
        try:
            os.makedirs(path, exist_ok=True)
            return
        except OSError as e:
            last_err = e
            # Fall back to the OS mkdir which succeeds on Drive folders.
            subprocess.run(["cmd", "/c", "mkdir", path],
                           capture_output=True, text=True)
            if os.path.isdir(path):
                return
            time.sleep(1)
    if not os.path.isdir(path):
        raise last_err


def main():
    print("=== workFLOw Watchface Build ===\n")

    # Clean and create dirs
    for d in [BUILD, OUT]:
        if os.path.exists(d):
            # Windows: remove read-only attributes before deleting
            for root, dirs, files in os.walk(d):
                for f in files:
                    fp = os.path.join(root, f)
                    os.chmod(fp, 0o777)
                for dd in dirs:
                    dp = os.path.join(root, dd)
                    os.chmod(dp, 0o777)
            shutil.rmtree(d, ignore_errors=True)
    for d in [
        os.path.join(BUILD, "compiled"),
        os.path.join(BUILD, "aab_struct", "base", "manifest"),
        os.path.join(BUILD, "aab_struct", "base", "res"),
        os.path.join(BUILD, "aab_extract"),
        OUT,
    ]:
        os.makedirs(d, exist_ok=True)

    # Step 1: Compile resources with aapt2
    print("[1/5] Compiling resources...")
    compiled_dir = os.path.join(BUILD, "compiled")

    # Compile drawables
    for f in os.listdir(os.path.join(SRC, "drawable-nodpi-v4")):
        if f.endswith(".png"):
            run([AAPT2, "compile",
                 os.path.join(SRC, "drawable-nodpi-v4", f),
                 "-o", compiled_dir])

    # Compile xml resources
    for f in os.listdir(os.path.join(SRC, "xml")):
        if f.endswith(".xml"):
            run([AAPT2, "compile",
                 os.path.join(SRC, "xml", f),
                 "-o", compiled_dir])

    # Compile raw resource (watchface.xml)
    run([AAPT2, "compile",
         os.path.join(SRC, "raw", "watchface.xml"),
         "-o", compiled_dir])

    # Compile values (strings) resources
    for values_dir in ["values", "values-de"]:
        vdir = os.path.join(SRC, values_dir)
        if os.path.isdir(vdir):
            for f in os.listdir(vdir):
                if f.endswith(".xml"):
                    run([AAPT2, "compile",
                         os.path.join(vdir, f),
                         "-o", compiled_dir])

    # Step 2: Link into proto-format APK
    print("\n[2/5] Linking resources...")
    base_apk = os.path.join(BUILD, "base.apk")
    flat_files = [os.path.join(compiled_dir, f)
                  for f in os.listdir(compiled_dir) if f.endswith(".flat")]

    run([AAPT2, "link",
         "--proto-format",
         "-o", base_apk,
         "-I", ANDROID_JAR,
         "--manifest", os.path.join(SRC, "AndroidManifest.xml"),
         "--min-sdk-version", "34",
         "--target-sdk-version", "36",
         "--version-code", "10000011",
         "--version-name", "1.3.6",
         ] + flat_files)

    # Step 3: Repackage as AAB
    print("\n[3/5] Repackaging as AAB...")
    extract_dir = os.path.join(BUILD, "aab_extract")
    aab_dir = os.path.join(BUILD, "aab_struct")

    # Extract the proto-format APK
    with zipfile.ZipFile(base_apk, "r") as z:
        z.extractall(extract_dir)

    # Move manifest
    shutil.copy2(
        os.path.join(extract_dir, "AndroidManifest.xml"),
        os.path.join(aab_dir, "base", "manifest", "AndroidManifest.xml"))

    # Move resources.pb
    shutil.copy2(
        os.path.join(extract_dir, "resources.pb"),
        os.path.join(aab_dir, "base", "resources.pb"))

    # Move res directory
    src_res = os.path.join(extract_dir, "res")
    dst_res = os.path.join(aab_dir, "base", "res")
    if os.path.exists(src_res):
        shutil.copytree(src_res, dst_res, dirs_exist_ok=True)

    # Copy BundleConfig.pb from original AAB
    orig_aab = os.path.join(SCRIPT_DIR, "com.watchfacestudio.workFLOw.aab")
    with zipfile.ZipFile(orig_aab, "r") as z:
        z.extract("BundleConfig.pb", aab_dir)

    # Step 4: Create AAB zip
    print("\n[4/5] Creating AAB archive...")
    unsigned_aab = os.path.join(BUILD, "unsigned.aab")
    with zipfile.ZipFile(unsigned_aab, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(aab_dir):
            for f in files:
                filepath = os.path.join(root, f)
                arcname = os.path.relpath(filepath, aab_dir)
                z.write(filepath, arcname)

    # Step 5: Sign
    print("\n[5/5] Signing AAB...")
    signed_aab = os.path.join(OUT, "com.watchfacestudio.workFLOw.aab")
    run([JARSIGNER,
         "-keystore", KEYSTORE,
         "-storepass", KEY_PASS,
         "-keypass", KEY_PASS,
         "-signedjar", signed_aab,
         unsigned_aab,
         KEY_ALIAS])

    # Verify
    result = subprocess.run(
        [JARSIGNER, "-verify", signed_aab],
        capture_output=True, text=True)
    print(result.stdout.strip())

    size = os.path.getsize(signed_aab)

    # Copy the finished AAB back into the synced project folder.
    #
    # IMPORTANT: The project folder is synced by Google Drive. Python's
    # shutil.copy2 and 'cmd copy' can silently FAIL to overwrite an existing,
    # Drive-locked file (reporting success while the old file remains). Only
    # PowerShell's 'Copy-Item -Force' reliably overwrites it, so we use that
    # and then VERIFY the destination size matches the freshly built AAB.
    final_aab = os.path.join(FINAL_OUT, "com.watchfacestudio.workFLOw.aab")
    ensure_dir(FINAL_OUT)

    copied = False
    for _ in range(5):
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Copy-Item -LiteralPath", f"'{signed_aab}'",
             "-Destination", f"'{final_aab}'", "-Force"],
            capture_output=True, text=True)
        # Verify the copy actually landed (same size as the source).
        if (os.path.exists(final_aab)
                and os.path.getsize(final_aab) == size):
            copied = True
            break
        time.sleep(1)

    if not copied:
        print("WARNING: could not reliably write the AAB to the project "
              "folder (Google Drive may be locking it).")
        print(f"The signed AAB is available here instead:\n  {signed_aab}")
        final_aab = signed_aab

    print(f"\n=== Build complete ===")
    print(f"Output: {final_aab}")
    print(f"Work dir: {WORK}")
    print(f"Size: {size:,} bytes")
    print(f"Version: 1.3.6 (10000011)")
    print(f"\nUpload this file to Google Play Console.")


if __name__ == "__main__":
    main()
