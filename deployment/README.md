# Email Reader App - Rocky Linux Deployment Guide

This guide provides step-by-step instructions for deploying the Email Reader FastAPI application on a Rocky Linux server.

## Prerequisites

- Rocky Linux 8 or 9 server with root or sudo access
- Python 3.8 or higher
- Internet connection for package installation
- Email files (.msg format) accessible on the server

## 1. System Preparation

### Update the system
```bash
sudo dnf update -y
```

### Install required system packages
```bash
sudo dnf install -y python3 python3-pip python3-venv git nginx
```

### Install development tools (required for some Python packages)
```bash
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y python3-devel
```

## 2. Create Application User

```bash
# Create a dedicated user for the application
sudo useradd -m -s /bin/bash emailreader
sudo usermod -aG wheel emailreader  # Optional: if you need sudo access
```

## 3. Application Setup

### Switch to application user
```bash
sudo su - emailreader
```

### Create application directory
```bash
mkdir -p /home/emailreader/email_reader_app
cd /home/emailreader/email_reader_app
```

### Upload your application files
```bash
# Option 1: Using git (if your code is in a repository)
git clone <your-repository-url> .

# Option 2: Using scp from your local machine
# From your local machine, run:
# scp -r /path/to/Email_reader_app/* user@server:/home/emailreader/email_reader_app/
```

### Create Python virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### Install Python dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Create environment configuration
```bash
cp .env.example .env
```

### Edit the environment file
```bash
nano .env
```

Update the configuration with your actual email folder path:
```env
# Replace with the actual path to your .msg files on the server
EMAIL_FOLDER_PATH=/var/emails
# Or wherever your .msg files are located, for example:
# EMAIL_FOLDER_PATH=/home/username/email_files
# EMAIL_FOLDER_PATH=/srv/company_emails

HOST=127.0.0.1
PORT=8000
DEBUG=False
MAX_DOWNLOAD_SIZE=104857600
DEFAULT_PAGE_SIZE=20
MAX_PAGE_SIZE=100
```

## 4. Create Systemd Service

### Exit from emailreader user
```bash
exit
```

### Create systemd service file
```bash
sudo nano /etc/systemd/system/email-reader.service
```

Add the following content:
```ini
[Unit]
Description=Email Reader FastAPI Application
After=network.target

[Service]
Type=simple
User=emailreader
Group=emailreader
WorkingDirectory=/home/emailreader/email_reader_app
Environment=PATH=/home/emailreader/email_reader_app/venv/bin
ExecStart=/home/emailreader/email_reader_app/venv/bin/python run.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### Enable and start the service
```bash
sudo systemctl daemon-reload
sudo systemctl enable email-reader
sudo systemctl start email-reader
```

### Check service status
```bash
sudo systemctl status email-reader
```

## 5. Configure Nginx Reverse Proxy

### Create Nginx configuration
```bash
sudo nano /etc/nginx/conf.d/email-reader.conf
```

Add the following content:
```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or server IP

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Static files (optional optimization)
    location /static/ {
        alias /home/emailreader/email_reader_app/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Test Nginx configuration
```bash
sudo nginx -t
```

### Enable and start Nginx
```bash
sudo systemctl enable nginx
sudo systemctl start nginx
```

### Configure firewall
```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https  # If using SSL
sudo firewall-cmd --reload
```

## 6. SSL Configuration (Optional but Recommended)

### Install Certbot
```bash
sudo dnf install -y certbot python3-certbot-nginx
```

### Obtain SSL certificate
```bash
sudo certbot --nginx -d your-domain.com
```

## 7. Email Folder Setup

### Create email directory (if needed)
```bash
sudo mkdir -p /var/emails
sudo chown emailreader:emailreader /var/emails
sudo chmod 755 /var/emails
```

### Copy your .msg files to the server
```bash
# Example: using scp
scp -r /local/path/to/msg/files/* user@server:/var/emails/
```

### Update permissions
```bash
sudo chown -R emailreader:emailreader /var/emails
sudo chmod -R 644 /var/emails/*.msg
```

## 8. Monitoring and Logs

### View application logs
```bash
sudo journalctl -u email-reader -f
```

### View Nginx logs
```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Check service status
```bash
sudo systemctl status email-reader
sudo systemctl status nginx
```

## 9. Maintenance Commands

### Restart the application
```bash
sudo systemctl restart email-reader
```

### Update the application
```bash
sudo su - emailreader
cd /home/emailreader/email_reader_app
source venv/bin/activate
git pull  # If using git
pip install -r requirements.txt
exit
sudo systemctl restart email-reader
```

### Backup configuration
```bash
sudo cp /etc/systemd/system/email-reader.service /backup/
sudo cp /etc/nginx/conf.d/email-reader.conf /backup/
sudo cp /home/emailreader/email_reader_app/.env /backup/
```

## 10. Troubleshooting

### Common Issues and Solutions

#### Service won't start
```bash
# Check logs
sudo journalctl -u email-reader -n 50

# Check if port is available
sudo netstat -tlnp | grep 8000

# Verify Python path
sudo su - emailreader
cd /home/emailreader/email_reader_app
source venv/bin/activate
python run.py  # Test manually
```

#### Permission issues
```bash
# Fix ownership
sudo chown -R emailreader:emailreader /home/emailreader/email_reader_app
sudo chown -R emailreader:emailreader /var/emails

# Check SELinux (if enabled)
sudo setsebool -P httpd_can_network_connect 1
sudo setsebool -P httpd_can_network_relay 1
```

#### Nginx issues
```bash
# Test configuration
sudo nginx -t

# Check if Nginx is running
sudo systemctl status nginx

# Restart Nginx
sudo systemctl restart nginx
```

## 11. Performance Optimization

### For production environments:

#### Use Gunicorn instead of Uvicorn
```bash
# Install Gunicorn
sudo su - emailreader
cd /home/emailreader/email_reader_app
source venv/bin/activate
pip install gunicorn
```

#### Update systemd service for Gunicorn
```bash
sudo nano /etc/systemd/system/email-reader.service
```

Replace ExecStart line with:
```ini
ExecStart=/home/emailreader/email_reader_app/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 app.main:app
```

#### Restart service
```bash
sudo systemctl daemon-reload
sudo systemctl restart email-reader
```

## 12. Security Considerations

1. **Firewall**: Only allow necessary ports (80, 443, SSH)
2. **User permissions**: Run application with minimal privileges
3. **File permissions**: Restrict access to email files
4. **SSL/TLS**: Always use HTTPS in production
5. **Updates**: Keep system and dependencies updated
6. **Backup**: Regular backups of configuration and data

## 13. Access Your Application

Once deployed, access your application at:
- HTTP: `http://your-server-ip/` or `http://your-domain.com/`
- HTTPS: `https://your-domain.com/` (if SSL configured)
- API Documentation: `https://your-domain.com/docs`

## Support

For issues or questions:
1. Check the application logs: `sudo journalctl -u email-reader -f`
2. Verify service status: `sudo systemctl status email-reader`
3. Test the API endpoints using the provided Postman collection
4. Check Nginx configuration and logs
