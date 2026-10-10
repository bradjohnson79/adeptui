#!/bin/bash
# Inspect the macOS DMG that adeptui.org serves. Do not modify that file.
# Do not disable Gatekeeper. A quarantine attribute is applied only to a disposable copy.
set -u

url="https://github.com/bradjohnson79/adeptui/releases/download/v1.1.1/Adept.UI-1.1.1-mac-arm64.dmg"
root="$(cd "$(dirname "$0")/../.." && pwd)"
work="${RUNNER_TEMP:-/tmp}/adept-macos-dmg-diagnosis"
evidence="$root/electron/build/macos-dmg-diagnosis"
dmg="$work/Adept.UI-1.1.1-mac-arm64.dmg"
mount="$work/mount"
log="$evidence/diagnosis.txt"

mkdir -p "$work" "$evidence" "$mount"
: > "$log"

note() {
  printf '%s\n' "$*" | tee -a "$log"
}

run_to() {
  local name="$1"
  shift
  note ""
  note "===== $name ====="
  set +e
  "$@" >>"$log" 2>&1
  local status=$?
  set +e
  note "EXIT $name = $status"
  return 0
}

note "LIVE DMG DIAGNOSIS"
note "URL $url"
note "RUNNER $(uname -a)"
note "ARCH $(uname -m)"

if ! curl -fL --retry 3 --retry-delay 2 -o "$dmg" "$url"; then
  note "DOWNLOAD = FAIL"
  exit 1
fi
note "DOWNLOAD = PASS"

hash_before="$(shasum -a 256 "$dmg" | awk '{print $1}')"
size_before="$(stat -f '%z' "$dmg")"
note "SHA-256 $hash_before"
note "SIZE $size_before"
printf '%s  %s\n' "$hash_before" "$dmg" > "$evidence/sha256.txt"
printf '%s\n' "$size_before" > "$evidence/size.txt"

run_to "HDIUTIL VERIFY" hdiutil verify "$dmg"
run_to "HDIUTIL IMAGEINFO" hdiutil imageinfo "$dmg"

if ! hdiutil attach -readonly -nobrowse -mountpoint "$mount" "$dmg" >>"$log" 2>&1; then
  note "MOUNT = FAIL"
  exit 1
fi
note "MOUNT = PASS readonly"

app="$mount/Adept UI.app"
note "APP EXISTS $([ -d "$app" ] && echo yes || echo no)"
note "VOLUME LISTING"
ls -la "$mount" >>"$log" 2>&1 || true
if [ -L "$mount/Applications" ]; then
  note "APPLICATIONS SYMLINK = PRESENT $(readlink "$mount/Applications")"
else
  note "APPLICATIONS SYMLINK = ABSENT"
fi

if [ ! -d "$app" ]; then
  note "BUNDLE = ABSENT"
  hdiutil detach "$mount" >>"$log" 2>&1 || hdiutil detach -force "$mount" >>"$log" 2>&1 || true
  exit 1
fi

plist="$app/Contents/Info.plist"
exe="$app/Contents/MacOS/Adept UI"
note "PLIST"
plutil -p "$plist" >>"$log" 2>&1 || true
note "BUNDLE ID $(defaults read "$plist" CFBundleIdentifier 2>/dev/null || echo missing)"
note "BUNDLE NAME $(defaults read "$plist" CFBundleName 2>/dev/null || echo missing)"
note "DISPLAY NAME $(defaults read "$plist" CFBundleDisplayName 2>/dev/null || echo missing)"
note "ICON FILE $(defaults read "$plist" CFBundleIconFile 2>/dev/null || echo missing)"
note "COPYRIGHT $(defaults read "$plist" NSHumanReadableCopyright 2>/dev/null || echo missing)"

icon_name="$(defaults read "$plist" CFBundleIconFile 2>/dev/null || true)"
icon_path=""
if [ -n "$icon_name" ]; then
  if [ -f "$app/Contents/Resources/${icon_name}" ]; then
    icon_path="$app/Contents/Resources/${icon_name}"
  elif [ -f "$app/Contents/Resources/${icon_name}.icns" ]; then
    icon_path="$app/Contents/Resources/${icon_name}.icns"
  fi
fi
if [ -n "$icon_path" ]; then
  note "ICON PATH $icon_path"
  file "$icon_path" >>"$log" 2>&1 || true
else
  note "ICON PATH = ABSENT"
fi

run_to "EXECUTABLE FILE" file "$exe"
run_to "EXECUTABLE LIPO" lipo -info "$exe"
note "EXECUTABLE MODE $(stat -f '%Sp' "$exe")"

python=""
for candidate in \
  "$app/Contents/Resources/python/bin/python" \
  "$app/Contents/Resources/python/bin/python3"
do
  if [ -e "$candidate" ]; then
    python="$candidate"
    break
  fi
done
if [ -n "$python" ]; then
  note "PYTHON $python"
  note "PYTHON MODE $(stat -f '%Sp' "$python")"
  run_to "PYTHON FILE" file "$python"
  run_to "PYTHON LIPO" lipo -info "$python"
else
  note "PYTHON = ABSENT"
fi

note "HELPER MODES"
find "$app/Contents" -type f \( -name '*.dylib' -o -path '*/MacOS/*' -o -path '*/Helpers/*' \) -print 2>/dev/null | head -n 40 | while IFS= read -r helper; do
  printf '%s %s\n' "$(stat -f '%Sp' "$helper")" "$helper"
done >>"$log" 2>&1 || true

run_to "XATTR APP" xattr -lr "$app"
run_to "XATTR DMG" xattr -l "$dmg"
run_to "CODESIGN DISPLAY" codesign -dv --verbose=4 "$app"
run_to "CODESIGN VERIFY DEEP" codesign --verify --deep --strict --verbose=4 "$app"
run_to "CODESIGN ENTITLEMENTS" codesign -d --entitlements :- "$app"
run_to "SPCTL UNMODIFIED MOUNT" spctl --assess --type execute --verbose=4 "$app"
run_to "STAPLER APP" stapler validate "$app"
run_to "STAPLER DMG" stapler validate "$dmg"
run_to "SPCTL DMG" spctl --assess --type open --verbose=4 "$dmg"

note ""
note "===== UNSIGNED MACH-O CENSUS ====="
unsigned=0
checked=0
while IFS= read -r bin; do
  kind="$(file -b "$bin" 2>/dev/null || true)"
  case "$kind" in
    Mach-O*)
      checked=$((checked + 1))
      if ! codesign -v "$bin" >/dev/null 2>&1; then
        unsigned=$((unsigned + 1))
        if [ "$unsigned" -le 40 ]; then
          note "UNSIGNED $bin"
        fi
      fi
      ;;
  esac
done < <(find "$app" -type f \( -perm -111 -o -name '*.dylib' -o -name '*.so' \) -print)
note "MACH-O CHECKED $checked"
note "UNSIGNED MACH-O COUNT $unsigned"

note ""
note "===== QUARANTINE SIMULATION ON DISPOSABLE COPY ====="
note "The downloaded DMG stays mounted read-only and is not rewritten."
copy_root="$work/disposable-copy"
rm -rf "$copy_root"
mkdir -p "$copy_root"
if ditto "$app" "$copy_root/Adept UI.app"; then
  xattr -w com.apple.quarantine "0083;00000000;Safari;ADEPT_DIAGNOSTIC" "$copy_root/Adept UI.app"
  run_to "XATTR DISPOSABLE COPY" xattr -l "$copy_root/Adept UI.app"
  run_to "SPCTL QUARANTINED DISPOSABLE COPY" spctl --assess --type execute --verbose=4 "$copy_root/Adept UI.app"
else
  note "DISPOSABLE COPY = FAIL"
fi

hdiutil detach "$mount" >>"$log" 2>&1 || hdiutil detach -force "$mount" >>"$log" 2>&1 || true
hash_after="$(shasum -a 256 "$dmg" | awk '{print $1}')"
note "SHA-256 AFTER $hash_after"
if [ "$hash_before" = "$hash_after" ]; then
  note "DMG UNCHANGED = PASS"
else
  note "DMG UNCHANGED = FAIL"
  exit 1
fi
note "LIVE DMG DIAGNOSIS COMPLETE"
