#!/usr/bin/env bash
#
# AIroom installer
# Installs AIroom via pipx from a pinned GitHub release.
#

set -euo pipefail

REPO="zero-0o0o/airoom"
BINARY_NAME="airoom"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

check_os() {
    case "$(uname -s)" in
        Darwin|Linux)
            log_info "Operating system: $(uname -s)"
            ;;
        *)
            log_error "Unsupported operating system: $(uname -s). AIroom supports macOS and Linux."
            exit 1
            ;;
    esac
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed. Please install Python 3.10 or later."
        exit 1
    fi

    local version
    version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    log_info "Python version: $version"

    # Check version >= 3.10
    if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
        log_error "Python 3.10 or later is required. Found $version."
        exit 1
    fi
}

check_pipx() {
    if ! command -v pipx &> /dev/null; then
        log_error "pipx is not installed. Please install pipx first:"
        echo "  macOS: brew install pipx"
        echo "  Linux: https://pipx.pypa.io/stable/installation/"
        exit 1
    fi
    log_info "pipx found: $(pipx --version)"
}

install_airoom() {
    local version="${1:-v0.1.0}"
    local install_spec

    if [[ ! "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.]+)?$ ]]; then
        log_error "Invalid release tag '$version'. Expected a pinned tag such as v0.1.0."
        exit 1
    fi
    install_spec="git+https://github.com/${REPO}.git@${version}"

    log_info "Installing AIroom ${version} via pipx..."
    pipx install "$install_spec" --force

    log_info "AIroom installed successfully!"
}

verify_installation() {
    if command -v "$BINARY_NAME" &> /dev/null; then
        local version
        version=$("$BINARY_NAME" --version 2>&1 || echo "unknown")
        log_info "Verification successful: $BINARY_NAME $version"
    else
        log_error "Installation verification failed: $BINARY_NAME not found in PATH"
        log_warn "You may need to restart your shell or run: pipx ensurepath"
        exit 1
    fi
}

main() {
    log_info "AIroom Installer"
    log_info "================="

    check_os
    check_python
    check_pipx

    # Use a pinned stable tag by default; allow an explicit tag override.
    local version="${AIROOM_VERSION:-v0.1.0}"
    install_airoom "$version"
    verify_installation

    log_info ""
    log_info "Next steps:"
    log_info "  cd your-project"
    log_info "  airoom init"
}

main "$@"
