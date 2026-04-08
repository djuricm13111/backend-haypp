#!/bin/bash

# Set non-interactive frontend for Debian/Ubuntu
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_SUSPEND=1


# Install base packages
sudo apt-get -y update && \
  sudo apt-get -y upgrade && \
  sudo apt-get -y install \
    curl \
    wget \
    jq \
    unzip \
    docker.io \
    certbot \
    python3-certbot-nginx

# Docker compose setup
sudo usermod -aG docker ubuntu && \
  sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose && \
  sudo chmod +x /usr/local/bin/docker-compose

# This will allow docker containers to run on system boot due to docker-compose 'restart: always' parameter
sudo systemctl enable docker

# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
  unzip awscliv2.zip && \
  sudo ./aws/install && \
  rm awscliv2.zip && \
  rm -rf aws

# Fetch configuration from AWS Secrets Manager
SECRET_ID="dev/env_config"
ENV_CONFIG=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --query SecretString --output text)

if [ -z "$ENV_CONFIG" ]; then
    echo "Error: Failed to retrieve environment config from AWS Secrets Manager."
    exit 1
fi

echo "$ENV_CONFIG" > snusco-backend.env

SECRET_ID="gh_token"
GH_TOKEN=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --query SecretString --output text)

if [ -z "$GH_TOKEN" ]; then
    echo "Error: Failed to retrieve Github token from AWS Secrets Manager."
    exit 1
fi

# If you  need to use specific branch, add ?ref=BRANCH_NAME at the end of api.github.com endpoint

# Currently not supproted since directory architecture is not the same on dev
curl -H "Authorization: token $GH_TOKEN" \
     -H "Accept: application/vnd.github.v3.raw" \
     -o docker-compose.yml \
     https://api.github.com/repos/snusco-org/snus-backend/contents/docker/docker-compose.yml

# Place nginx.conf into subdirectory and rename it to default.conf:
#│── docker-compose.yml
#│── .nginx/
#│   ├── default.conf

# Currently not supproted since directory architecture is not the same on dev
mkdir nginx && curl -H "Authorization: token $GH_TOKEN" \
     -H "Accept: application/vnd.github.v3.raw" \
     -o nginx/default.conf \
     https://api.github.com/repos/snusco-org/snus-backend/contents/docker/nginx.conf

# Setup SSL for nginx and enables HTTPS
# sudo certbot --nginx -d BE_DOMAIN
# For debug: --register-unsafely-without-email and remove 'echo $EMAIL_ADDRESS |'
# For prod, enter email
#EMAIL_ADDRESS=""
#echo $EMAIL_ADDRESS | echo  "Y" | sudo certbot --nginx -d api.qmsstage.com
# sudo certbot certonly --standalone --non-interactive --agree-tos --register-unsafely-without-email -d api.qmsstage.com

# install amazon ecr credential helper
sudo apt install amazon-ecr-credential-helper -y
mkdir -p ~/.docker
cat > ~/.docker/config.json <<EOF
{
  "credHelpers": {
    "590183671695.dkr.ecr.eu-north-1.amazonaws.com": "ecr-login"
  }
}
EOF

