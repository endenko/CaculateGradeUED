#!/bin/bash
# Bootstrap one EC2 instance (Ubuntu or Amazon Linux 2023) for the UED grade app.
# Installs a 1 GB swapfile, clones the branch, and serves gunicorn on port 80.
# Docker is the default runtime (--restart=always). Set UED_RUNTIME=python to
# skip Docker and use a virtualenv plus a systemd unit with Restart=always.
set -euo pipefail
umask 022

LOG=/var/log/ued-bootstrap.log
mkdir -p /var/log
exec > >(tee -a "$LOG") 2>&1
echo "=== UED bootstrap $(date -Is 2>/dev/null || date) ==="

REPO_URL="${REPO_URL:-https://github.com/endenko/CaculateGradeUED}"
BRANCH="${BRANCH:-feature/vietocr-all-faculties-ued-ui}"
APP_DIR="${APP_DIR:-/opt/ued-grade}"
PORT="${UED_PORT:-80}"
RUNTIME="${UED_RUNTIME:-docker}"
IMAGE="${UED_IMAGE:-ued-grade:light}"

ensure_swap() {
    if [[ "${UED_SKIP_SWAP:-0}" == "1" ]]; then
        echo "swap: skipped by UED_SKIP_SWAP"
        return 0
    fi
    if swapon --show 2>/dev/null | grep -q '/swapfile'; then
        echo "swap: already active"
        return 0
    fi
    if [[ ! -f /swapfile ]]; then
        if ! fallocate -l 1G /swapfile 2>/dev/null; then
            dd if=/dev/zero of=/swapfile bs=1M count=1024 status=none
        fi
        chmod 600 /swapfile
        mkswap /swapfile
    fi
    if swapon /swapfile; then
        grep -qE '^/swapfile[[:space:]]' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
        echo "swap: 1G /swapfile enabled"
    else
        echo "WARNING: swapon failed; continuing without swap"
    fi
}

os_id() {
    # shellcheck disable=SC1091
    . /etc/os-release
    printf '%s' "${ID:-unknown}"
}

docker_ready() {
    docker info >/dev/null 2>&1
}

start_dockerd_if_needed() {
    if docker_ready; then
        return 0
    fi
    if command -v systemctl >/dev/null && [[ -d /run/systemd/system ]]; then
        systemctl enable --now docker
        return 0
    fi
    if ! pgrep -x dockerd >/dev/null 2>&1; then
        dockerd >/var/log/dockerd.log 2>&1 &
    fi
    local i
    for i in $(seq 1 40); do
        docker_ready && return 0
        sleep 1
    done
    return 1
}

install_docker() {
    local id="$1"
    if [[ "$id" == "amzn" ]]; then
        dnf install -y docker git tar
    else
        export DEBIAN_FRONTEND=noninteractive
        apt-get update
        apt-get install -y ca-certificates curl git tar docker.io
    fi
    start_dockerd_if_needed || echo "WARNING: docker daemon did not become ready"
}

install_python_packages() {
    local id="$1"
    if [[ "$id" == "amzn" ]]; then
        dnf install -y git tar glib2 libgomp mesa-libGL
        if ! dnf install -y python3.12; then
            dnf install -y python3.11 || dnf install -y python3
        fi
    else
        export DEBIAN_FRONTEND=noninteractive
        apt-get update
        apt-get install -y --no-install-recommends python3 python3-venv python3-pip git tar \
            libglib2.0-0 libgomp1 libgl1 ca-certificates
    fi
}

python_bin() {
    if command -v python3.12 >/dev/null 2>&1; then
        echo python3.12
    elif command -v python3.13 >/dev/null 2>&1; then
        echo python3.13
    elif command -v python3.11 >/dev/null 2>&1; then
        echo python3.11
    else
        echo python3
    fi
}

fetch_app() {
    mkdir -p "$APP_DIR"
    if [[ -n "${UED_SOURCE:-}" ]]; then
        echo "source: copy $UED_SOURCE -> $APP_DIR"
        tar -C "$UED_SOURCE" \
            --exclude .git --exclude .venv --exclude __pycache__ --exclude uploads \
            --exclude grade.db -cf - . | tar -C "$APP_DIR" -xf -
        return 0
    fi
    if [[ ! -d "$APP_DIR/.git" ]]; then
        git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$APP_DIR"
    else
        git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
        git -C "$APP_DIR" checkout "$BRANCH"
        git -C "$APP_DIR" reset --hard "origin/$BRANCH"
    fi
}

start_docker_app() {
    docker build -f "$APP_DIR/deploy/aws/Dockerfile" -t "$IMAGE" "$APP_DIR"
    docker rm -f ued-grade >/dev/null 2>&1 || true
    docker run -d --name ued-grade --restart=always \
        -p "${PORT}:8000" \
        -e OCR_LIGHT=1 \
        -e OMP_NUM_THREADS=1 \
        -e MALLOC_ARENA_MAX=2 \
        -e RAPID_LIMIT_SIDE=960 \
        "$IMAGE"
    docker ps --filter name=ued-grade
}

write_systemd_unit() {
    local py="$1"
    mkdir -p /etc/systemd/system
    cat > /etc/systemd/system/ued-grade.service <<EOF
[Unit]
Description=UED grade calculator
After=network.target

[Service]
WorkingDirectory=$APP_DIR
Environment=OCR_LIGHT=1
Environment=OMP_NUM_THREADS=1
Environment=MALLOC_ARENA_MAX=2
Environment=RAPID_LIMIT_SIDE=960
ExecStart=$py --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
}

start_python_app() {
    local py
    py="$(python_bin)"
    echo "python: $py"
    "$py" -m venv "$APP_DIR/.venv"
    "$APP_DIR/.venv/bin/pip" install --upgrade pip
    "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
    (cd "$APP_DIR" && OCR_LIGHT=1 "$APP_DIR/.venv/bin/python" seed_db.py)
    write_systemd_unit "$APP_DIR/.venv/bin/gunicorn"
    if [[ "${UED_FOREGROUND:-0}" == "1" ]]; then
        cd "$APP_DIR"
        exec env OCR_LIGHT=1 OMP_NUM_THREADS=1 MALLOC_ARENA_MAX=2 RAPID_LIMIT_SIDE=960 \
            "$APP_DIR/.venv/bin/gunicorn" --bind "0.0.0.0:${PORT}" --workers 1 --threads 2 --timeout 120 app:app
    fi
    if command -v systemctl >/dev/null && [[ -d /run/systemd/system ]]; then
        systemctl daemon-reload
        systemctl enable --now ued-grade.service
    else
        cd "$APP_DIR"
        nohup env OCR_LIGHT=1 OMP_NUM_THREADS=1 MALLOC_ARENA_MAX=2 RAPID_LIMIT_SIDE=960 \
            "$APP_DIR/.venv/bin/gunicorn" --bind "0.0.0.0:${PORT}" --workers 1 --threads 2 --timeout 120 app:app \
            >> /var/log/ued-gunicorn.log 2>&1 &
        echo $! > /var/run/ued-grade.pid
        echo "gunicorn pid $(cat /var/run/ued-grade.pid) (no systemd; Restart=always unit is installed for the next boot)"
    fi
}

ensure_swap
if [[ "${UED_ONLY_SWAP:-0}" == "1" ]]; then
    swapon --show || true
    exit 0
fi
ID="$(os_id)"
echo "os=$ID runtime=$RUNTIME port=$PORT"

if [[ "$RUNTIME" == "python" ]]; then
    install_python_packages "$ID"
    fetch_app
    start_python_app
else
    install_docker "$ID"
    fetch_app
    if docker_ready; then
        start_docker_app
    else
        echo "Docker unavailable; installing Python and serving with gunicorn"
        install_python_packages "$ID"
        start_python_app
    fi
fi

echo "=== bootstrap finished ==="
