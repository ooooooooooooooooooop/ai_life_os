#!/bin/bash
set -e

echo "=== 安装 Nginx ==="
apt update -y
apt install -y nginx certbot python3-certbot-nginx

echo "=== 配置 SSH 允许远程转发 ==="
grep -q "GatewayPorts yes" /etc/ssh/sshd_config || echo "GatewayPorts yes" >> /etc/ssh/sshd_config
grep -q "ClientAliveInterval 30" /etc/ssh/sshd_config || echo "ClientAliveInterval 30" >> /etc/ssh/sshd_config
grep -q "ClientAliveCountMax 3" /etc/ssh/sshd_config || echo "ClientAliveCountMax 3" >> /etc/ssh/sshd_config
systemctl restart sshd
echo "SSH 配置完成"

echo "=== 创建 Nginx 配置 ==="
cat > /etc/nginx/sites-available/ailife << 'NGINXEOF'
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300;
    }
}
NGINXEOF

ln -sf /etc/nginx/sites-available/ailife /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ""
echo "=== VPS 基础配置完成 ==="
echo "域名买好后执行以下两条命令（替换 your.domain.com）："
echo "  sed -i 's/DOMAIN_PLACEHOLDER/your.domain.com/g' /etc/nginx/sites-available/ailife"
echo "  nginx -t && systemctl reload nginx"
echo "  certbot --nginx -d your.domain.com"
