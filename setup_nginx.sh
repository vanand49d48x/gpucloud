#!/bin/bash
# GPUCloud Nginx Setup Script

set -e

echo "🔧 Setting up Nginx for GPUCloud Production..."

# Colors
[Service]
Type=forking
User=paperspace
Group=paperspace
WorkingDirectory=/home/paperspace/NewMyPods/mypods
ExecStart=/home/paperspace/NewMyPods/mypods/start_production.sh
ExecReload=/bin/kill -HUP \$MAINPID33[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Install Nginx if not present
if ! command -v nginx &> /dev/null; then
    log "📦 Installing Nginx..."
    apt update
    apt install -y nginx
    log "✅ Nginx installed"
else
    log "✅ Nginx already installed"
fi

# Create SSL directory
log "🔐 Setting up SSL certificates..."
mkdir -p /etc/ssl/certs /etc/ssl/private

# Generate self-signed certificate (for development)
# In production, use Let's Encrypt or proper CA
if [ ! -f /etc/ssl/certs/gpucloud.crt ]; then
    log "🔑 Generating self-signed SSL certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/ssl/private/gpucloud.key \
        -out /etc/ssl/certs/gpucloud.crt \
        -subj "/C=US/ST=State/L=City/O=GPUCloud/CN=184.105.5.179"
    log "✅ SSL certificate generated"
else
    log "✅ SSL certificate already exists"
fi

# Copy Nginx configuration
log "📝 Installing Nginx configuration..."
cp nginx/gpucloud.conf /etc/nginx/sites-available/gpucloud

# Enable the site
if [ ! -L /etc/nginx/sites-enabled/gpucloud ]; then
    ln -s /etc/nginx/sites-available/gpucloud /etc/nginx/sites-enabled/
    log "✅ Site enabled"
fi

# Remove default site
if [ -L /etc/nginx/sites-enabled/default ]; then
    rm /etc/nginx/sites-enabled/default
    log "✅ Default site disabled"
fi

# Test Nginx configuration
log "🧪 Testing Nginx configuration..."
if nginx -t; then
    log "✅ Nginx configuration is valid"
else
    log "${RED}❌ Nginx configuration test failed${NC}"
    exit 1
fi

# Create log directory
mkdir -p /var/log/nginx

# Set proper permissions
chown -R www-data:www-data /var/log/nginx
chmod 755 /etc/ssl/private
chmod 644 /etc/ssl/certs/gpucloud.crt
chmod 600 /etc/ssl/private/gpucloud.key

# Restart Nginx
log "🔄 Restarting Nginx..."
systemctl restart nginx
systemctl enable nginx

# Check Nginx status
if systemctl is-active --quiet nginx; then
    log "${GREEN}✅ Nginx is running${NC}"
else
    log "${RED}❌ Nginx failed to start${NC}"
    systemctl status nginx
    exit 1
fi

# Configure firewall (if ufw is active)
if command -v ufw &> /dev/null && ufw status | grep -q "Status: active"; then
    log "🔥 Configuring firewall..."
    ufw allow 'Nginx Full'
    ufw allow 22/tcp  # SSH
    log "✅ Firewall configured"
fi

# Create systemd service for GPUCloud
log "⚙️  Creating systemd service..."
cat > /etc/systemd/system/gpucloud.service << EOF
[Unit]
Description=GPUCloud Production System
After=network.target postgresql.service redis.service nginx.service
Wants=postgresql.service redis.service nginx.service

[Service]
Type=forking
User=paperspace
Group=paperspace
WorkingDirectory=/home/paperspace/mypods
ExecStart=/home/paperspace/NewMyPods/mypods/start_production.sh
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable gpucloud.service

log "${GREEN}🎉 Nginx setup completed successfully!${NC}"
echo ""
echo "📋 Next steps:"
echo "  1. Update your domain DNS to point to 184.105.5.179"
echo "  2. Replace self-signed certificate with Let's Encrypt:"
echo "     sudo apt install certbot python3-certbot-nginx"
echo "     sudo certbot --nginx -d yourdomain.com"
echo "  3. Start GPUCloud service:"
echo "     sudo systemctl start gpucloud"
echo "  4. Check status:"
echo "     sudo systemctl status gpucloud"
echo ""
echo "🌐 Access URLs:"
echo "  Frontend: https://184.105.5.179"
echo "  API: https://184.105.5.179/v1/"
echo "  Health: https://184.105.5.179/health"
echo ""
echo "📊 Monitor logs:"
echo "  Nginx: sudo tail -f /var/log/nginx/gpucloud_*.log"
echo "  GPUCloud: sudo journalctl -u gpucloud -f"
