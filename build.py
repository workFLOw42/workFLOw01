"""Build script for workFLOw watchface AAB.

Usage: python build.py
"""
import os
import shutil
import subprocess
import sys
import zipfile

# Paths
SDK = r"c:\Users\flori\AppData\Local\Android\Sdk"
AAPT2 = os.path.join(SDK, "build-tools", "34.0.0", "aapt2.exe")
ANDROID_JAR = os.path.join(SDK, "platforms", "android-34", "android.jar")
JARSIGNER = r"c:\Program Files\Android\Android Studio\jbr\bin\jarsigner.exe"
KEYSTORE = r"c:\Users\flori\WatchFaceStudio\keystore\keystore.jks"
KEY_ALIAS = "key0"
KEY_PASS = "Flo61215"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(SCRIPT_DIR, "src")
BUILD = os.path.join(SCRIPT_DIR, "build")
OUT = os.path.join(SCRIPT_DIR, "out")


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
         "--target-sdk-version", "34",
         "--version-code", "10000005",
         "--version-name", "1.3.0",
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
    print(f"\n=== Build complete ===")
    print(f"Output: {signed_aab}")
    print(f"Size: {size:,} bytes")
    print(f"Version: 1.3.0 (10000005)")
    print(f"\nUpload this file to Google Play Console.")


if __name__ == "__main__":
    main()
