#!/usr/bin/env bash
# One-time hardening + Docker install on a fresh Ubuntu 24.04 VM (Oracle Cloud Ampere A1, ARM64).
# Clone the repo, READ this file, then run:  sudo scripts/vm-setup.sh   (never pipe a remote script into bash)
# What it does: OS updates (+ automatic security updates), Docker Engine from Docker's official repo, firewall
# with only 22/80/443, fail2ban for SSH, SSH key-only login, 4 GB swap, /opt/baixeai owned by the deploy user.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
DEPLOY_USER=${SUDO_USER:-ubuntu}

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get -y upgrade
DEBIAN_FRONTEND=noninteractive apt-get -y install ca-certificates curl git ufw fail2ban unattended-upgrades
dpkg-reconfigure -f noninteractive unattended-upgrades

# Docker Engine (official repository; https://docs.docker.com/engine/install/ubuntu/)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
usermod -aG docker "$DEPLOY_USER"

# Firewall. Oracle images ALSO ship iptables rules that only allow SSH: open 80/443 there too, and in the
# VCN Security List (console). Docker-published ports bypass ufw, so publish only Caddy's 80/443.
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable
if [ -f /etc/iptables/rules.v4 ]; then
  for port in 80 443; do
    iptables -C INPUT -p tcp --dport $port -j ACCEPT 2>/dev/null || iptables -I INPUT 5 -p tcp --dport $port -j ACCEPT
  done
  netfilter-persistent save || true
fi

# SSH: keys only
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/; s/^#\?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl reload ssh || systemctl reload sshd
systemctl enable --now fail2ban

# Swap (LibreOffice/ONNX peaks)
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

mkdir -p /opt/baixeai && chown "$DEPLOY_USER:$DEPLOY_USER" /opt/baixeai
echo "OK. Log out and back in (docker group), then follow docs/OPERACAO.md section 'Primeiro deploy'."
