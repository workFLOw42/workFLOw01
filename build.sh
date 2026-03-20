#!/bin/bash
# Build script for workFLOw watchface AAB
# Usage: ./build.sh

set -e

# Paths
SDK="/c/Users/flori/AppData/Local/Android/Sdk"
AAPT2="$SDK/build-tools/34.0.0/aapt2.exe"
ZIPALIGN="$SDK/build-tools/34.0.0/zipalign.exe"
ANDROID_JAR="$SDK/platforms/android-34/android.jar"
JARSIGNER="/c/Program Files/Android/Android Studio/jbr/bin/jarsigner.exe"
KEYSTORE="/c/Users/flori/AppData/Local/Programs/WatchFaceStudio/tools/common/key/debug.keystore"
KEY_ALIAS="androiddebugkey"
KEY_PASS="android"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR/src"
BUILD="$SCRIPT_DIR/build"
OUT="$SCRIPT_DIR/out"

echo "=== workFLOw Watchface Build ==="

# Clean
rm -rf "$BUILD" "$OUT"
mkdir -p "$BUILD/compiled" "$BUILD/base" "$OUT"

# Step 1: Compile resources with aapt2
echo "[1/5] Compiling resources..."
for png in "$SRC/drawable-nodpi-v4/"*.png; do
    "$AAPT2" compile "$png" -o "$BUILD/compiled/" 2>&1
done
for xml in "$SRC/xml/"*.xml; do
    "$AAPT2" compile "$xml" -o "$BUILD/compiled/" 2>&1
done
# Raw resources (watchface.xml) - compile as raw
"$AAPT2" compile --dir "$SRC" -o "$BUILD/compiled/" 2>&1 || true
# Manually compile raw resource
"$AAPT2" compile "$SRC/raw/watchface.xml" -o "$BUILD/compiled/" 2>&1

echo "[2/5] Linking APK..."
# Step 2: Link into base APK
"$AAPT2" link \
    --proto-format \
    -o "$BUILD/base.apk" \
    -I "$ANDROID_JAR" \
    --manifest "$SRC/AndroidManifest.xml" \
    --min-sdk-version 34 \
    --target-sdk-version 34 \
    --version-code 10000003 \
    --version-name "1.1.0" \
    "$BUILD/compiled/"*.flat 2>&1

echo "[3/5] Repackaging as AAB..."
# Step 3: Extract and repackage as AAB structure
cd "$BUILD"
mkdir -p aab_struct/base
cd "$BUILD/base.apk" 2>/dev/null || true

# Unzip the proto APK
unzip -o "$BUILD/base.apk" -d "$BUILD/aab_extract" > /dev/null 2>&1

# Create AAB structure
mkdir -p "$BUILD/aab_struct/base/manifest"
mkdir -p "$BUILD/aab_struct/base/res"

# Move manifest
mv "$BUILD/aab_extract/AndroidManifest.xml" "$BUILD/aab_struct/base/manifest/"

# Move resources.pb
mv "$BUILD/aab_extract/resources.pb" "$BUILD/aab_struct/base/"

# Move res directory
cp -r "$BUILD/aab_extract/res/"* "$BUILD/aab_struct/base/res/" 2>/dev/null || true

# Create BundleConfig.pb (minimal)
printf '\x0a\x08\x0a\x04\x08\x01\x10\x01\x12\x00' > "$BUILD/aab_struct/BundleConfig.pb"

echo "[4/5] Creating AAB archive..."
# Step 4: Zip into AAB
cd "$BUILD/aab_struct"
zip -r "$BUILD/unsigned.aab" . > /dev/null 2>&1

echo "[5/5] Signing AAB..."
# Step 5: Sign
"$JARSIGNER" \
    -keystore "$KEYSTORE" \
    -storepass "$KEY_PASS" \
    -keypass "$KEY_PASS" \
    -signedjar "$OUT/com.watchfacestudio.workFLOw.aab" \
    "$BUILD/unsigned.aab" \
    "$KEY_ALIAS" 2>&1

# Verify
"$JARSIGNER" -verify "$OUT/com.watchfacestudio.workFLOw.aab" 2>&1 | head -3

echo ""
echo "=== Build complete ==="
ls -la "$OUT/com.watchfacestudio.workFLOw.aab"
echo ""
echo "Upload this file to Google Play Console."
