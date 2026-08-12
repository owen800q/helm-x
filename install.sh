#!/usr/bin/env bash
# helm-x installer — macOS / Linux
#
#   curl -fsSL https://raw.githubusercontent.com/owen800q/helm-x/master/install.sh | bash
#
# Downloads the latest release binary and installs it. Files fetched with curl
# are never given macOS's com.apple.quarantine attribute, so the installed
# binary runs straight away — no `xattr -d com.apple.quarantine` needed. As a
# belt-and-braces measure the script also strips the attribute if it somehow
# ended up set (e.g. when re-running over a browser-downloaded copy).
set -euo pipefail

REPO="${HELMX_REPO:-owen800q/helm-x}"
VERSION="${HELMX_VERSION:-latest}"
INSTALL_DIR="${HELMX_INSTALL_DIR:-}"

err() { printf '\033[31m[error]\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m[helm-x]\033[0m %s\n' "$*"; }

# ---- pick the asset for this platform -------------------------------------
case "$(uname -s)" in
    Darwin) ASSET="helmx-macos-universal.tar.gz" ;;
    Linux)
        [ "$(uname -m)" = "x86_64" ] || err "unsupported architecture: $(uname -m) (only x86_64 Linux is published)"
        ASSET="helmx-linux-x86_64.tar.gz"
        ;;
    *) err "unsupported OS: $(uname -s) — on Windows download helmx-windows-x86_64.exe" ;;
esac

command -v curl >/dev/null 2>&1 || err "curl is required but not installed"
command -v tar  >/dev/null 2>&1 || err "tar is required but not installed"

# ---- resolve the download URL ---------------------------------------------
if [ "$VERSION" = "latest" ]; then
    URL="https://github.com/$REPO/releases/latest/download/$ASSET"
else
    URL="https://github.com/$REPO/releases/download/$VERSION/$ASSET"
fi

# ---- choose an install directory ------------------------------------------
if [ -z "$INSTALL_DIR" ]; then
    if [ -w /usr/local/bin ] 2>/dev/null; then
        INSTALL_DIR=/usr/local/bin
    else
        INSTALL_DIR="$HOME/.local/bin"
    fi
fi
mkdir -p "$INSTALL_DIR"

# ---- download + unpack -----------------------------------------------------
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

info "downloading $ASSET ($VERSION)"
curl -fsSL "$URL" -o "$TMP/helmx.tar.gz" \
    || err "download failed: $URL"

tar -xzf "$TMP/helmx.tar.gz" -C "$TMP"
[ -f "$TMP/helmx" ] || err "archive did not contain a helmx binary"

chmod +x "$TMP/helmx"

# Defensive: curl never sets the quarantine flag, but if this file came from
# somewhere that did, clear it so the user is not prompted by Gatekeeper.
if [ "$(uname -s)" = "Darwin" ] && command -v xattr >/dev/null 2>&1; then
    xattr -d com.apple.quarantine "$TMP/helmx" 2>/dev/null || true
fi

mv -f "$TMP/helmx" "$INSTALL_DIR/helmx"

info "installed to $INSTALL_DIR/helmx"

# ---- post-install notes ----------------------------------------------------
case ":$PATH:" in
    *":$INSTALL_DIR:"*) info "run: helmx" ;;
    *)
        info "$INSTALL_DIR is not on your PATH — add it with:"
        printf '    export PATH="%s:$PATH"\n' "$INSTALL_DIR"
        info "or run it directly: $INSTALL_DIR/helmx"
        ;;
esac
