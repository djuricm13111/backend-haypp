# DevOps Documentation

This repository contains infrastructure and deployment configurations that ensure a consistent and reliable setup for the project. All core DevOps files are located in the `./docker/` directory.

---

## DevOps Files

### `Dockerfile`

Defines the environment used to build the backend/frontend container. It includes:
- Installation of required packages and tools
- Download of necessary files
- Environment variable configuration

Every repository should include its own `Dockerfile` to define its setup.

### `docker-entrypoint.sh`

Executed each time a container is created.  
Used for:
- Running pre-start commands (e.g., Django database migrations)

In this project, it handles migration setup before launching the Django server.

### `docker-compose.yml`

Defines how containers are created and networked.  
Features:
- Pulls images from AWS Elastic Container Registry (ECR)
- Starts service containers for frontend, backend, and NGINX
- Manages internal communication between services
- Handles EC2-level traffic via NGINX

### `nginx.conf`

NGINX configuration used for:
- Routing between frontend and backend
- Enabling HTTPS with SSL
- Managing inbound/outbound traffic on the EC2 instance

### `ec2-setup.sh`

Setup script for initializing a new EC2 instance.

Responsibilities:
- Installing system dependencies and tools
- Setting up environment variables and configurations
- Acting as the central place to update system-level requirements
- Fetch Github token and download required files (docker-compose.yml and nginx.conf) via that token
- Register domains and install certificates to enable SSL

Once the setup is complete, the system can be launched via:

```bash
docker compose up
```

from the `./docker/ directory.`

---

## GitHub Workflows

The repository uses several GitHub Actions workflows to automate the CI/CD pipeline. All workflow files are located in `.github/workflows/`.

### Github Workflows Secrets

- AWS_ACCESS_KEY_ID - AWS access key with access to ec2 and ecr
- AWS_SECRET_ACCESS_KEY - AWS secret access key 
- EC2_HOST - ec2 host instance, could be public ip assigned to ec2 (elasticip)
- EC2_HOST_MACHINE - elastic ip assigned to your ec2 or ec2 public ip
- EC2_SSH_KEY - contents of pem file of your ssh key assigned to your ec2 instance
- EC2_USER - ec2 username for accessing ec2, usually ubuntu
- ECR_REGISTRY - ecr registry to which our repo is deploying newly built docker images

### `increase-version.yml`

This repository uses a GitHub Action to automatically **bump the project version** and create a **Git tag and release** based on the pull request title.

**Purpose:**  
Automatically increments the project version number.

**Trigger:**  
The workflow triggers only on pull requests targeting the `main` branch that are **not marked as drafts**.

### ⚙️ How It Works

When you open or update a pull request against `main`, the action reads the `VERSION` file and:

1. **Determines the type of version bump** based on the pull request title:
   - `BREAKING CHANGE` or `!` → **Major**
   - Title starting with `feat:` → **Minor**
   - Anything else → **Patch** (default)

2. **Increments the version** accordingly:
   - `1.2.3` → `2.0.0` (major)
   - `1.2.3` → `1.3.0` (minor)
   - `1.2.3` → `1.2.4` (patch)

3. **Commits** the new version to the branch
4. **Pushes** the change to GitHub
5. **Creates a Git tag and release** (e.g., `v1.2.4`)

### `build-image-and-push-to-ecr.yml`

**Purpose:**  
Builds the Docker image from the latest source code and pushes it to AWS Elastic Container Registry (ECR).

**Steps involved:**
1. Check out code.
2. Log in to AWS using GitHub credentials.
3. Build the Docker image using the `Dockerfile`.
4. Tag and push the image to ECR.

**Trigger:**  
Automatically on push to `main` branch

### `manual-deploy.yml`

**Purpose:**  
Manually deploys the latest Docker image (of this specific repository) to the EC2 instance.

**What it does:**
1. Connects to the EC2 instance via SSH.
2. Pulls the latest image from ECR.
3. Runs `docker compose down` (optional, if needed).
4. Runs `docker compose up -d` to restart services with the new image.

**Trigger:**
- Manually via GitHub Actions UI.

__Note__: To deploy a new version of each image, similar action should be executed on each respective repository

---

## AWS Infrastructure

This project is deployed on AWS and uses a set of managed services to support maintainable application architecture.

### EC2 (Elastic Compute Cloud)

**Purpose:**  
Hosts the Docker Compose-based application environment.

**Details:**
- All services (frontend, backend, NGINX) run as Docker containers on this instance.
- An **Elastic IP** is attached to the EC2 instance to ensure a consistent public IP for DNS mapping and access.
intiated- The EC2 instance is initiauled using the `ec2-setup.sh` script.
- Defined IAM role that grans access to rest of services needed for application functionalities (S3, Secrets Manager, RDS)
- Defined security group (`sg-029b627d9a776d3c9 - snuswe-backend`) to allow inbound and outbound communication via various ports to allow SSH / HTTPS communication.
  - Ports allowed for application level: `8080, 8000, 3000`
  - Ports allowed for SSH connection: `22`
  - Ports allowed for HTTP / HTTPS communication: `80, 443`

### RDS (Relational Database Service)

**Purpose:**  
Provides a managed PostgreSQL database instance.

Database credentials are stored in secrets manager under `rds/user`.

All migrations are handled by the backend services.

**Details:**
- Used by the backend application for data persistence.
- Secured within a private subnet and only accessible by the backend container.

### Secrets Manager

**Purpose:**  
Stores sensitive environment configuration and credentials.

**Stored Secrets:**
- `dev/env_config`: JSON object containing all environment variables for the backend container.
- `gh_token`: GitHub personal access token used by the EC2 instance to pull code and interact with the repository.

**Usage:**
- Secrets are fetched during initialization of EC2 (`ec2-setup.sh`) and injected into the backend container environment.

### ECR (Elastic Container Registry)

**Purpose:**  
Stores versioned Docker images built from the repository.

**Details:**
- Docker images are built via GitHub Actions.
- EC2 instance pulls the latest version from ECR during deployment.
- Enables reproducible and version-controlled deployments.

---

# How to setup new ec2 instance for backend services

# 🚀 Setting Up an EC2 Instance on AWS

This guide walks you through the steps needed to launch a new EC2 instance on AWS to serve as the infrastructure for deploying your application.

---

## ✅ Prerequisites

- An AWS account with access credentials configured via `aws configure`
- A pre-created security group, key pair, and VPC
- Your public IP whitelisted in the security group for SSH access

---

## 📦 Step 1: Launch the EC2 Instance

You can launch an EC2 instance either via the AWS Console or the CLI.

---

### Option 1: AWS Console (Web Interface)

1. Go to [https://console.aws.amazon.com](https://console.aws.amazon.com) and navigate to **EC2**
2. Click **"Launch instance"**
3. Choose:
   - **AMI**: Ubuntu Server 22.04 LTS
   - **Instance Type**: `t3.small` or another based on your needs
   - **Key Pair**: select your existing SSH key
   - **Network Settings**: select your existing VPC and security group
4. Click **"Launch instance"**

---

### Option 2: AWS CLI

If you prefer using the CLI, you can start a new instance with the following command:

```bash
aws ec2 run-instances \
  --image-id ami-xxxxxxxxxxxxxxxxx \
  --instance-type t3.small \
  --key-name my-keypair \
  --security-group-ids sg-xxxxxxxxxxxxxxxxx \
  --subnet-id subnet-xxxxxxxxxxxxxxxxx \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=my-project-ec2}]' \
  --region eu-north-1
  ```
For an example here is how your ec2 run-instance command should look:
```bash
aws ec2 run-instances \
  --image-id "ami-0c1ac8a41498c1a9c" \
  --instance-type "t3.small" \
  --key-name "ervins-key" \
  --block-device-mappings '{"DeviceName":"/dev/sda1","Ebs":{"Encrypted":false, "DeleteOnTermination":true,"Iops":3000,"SnapshotId":"snap-0b7078bceafe69fd4","VolumeSize":100,"VolumeType":"gp3","Throughput":125}}' \
  --network-interfaces '{"AssociatePublicIpAddress":true,"DeviceIndex":0,"Groups":["sg-029b627d9a776d3c9"]}' \
  --credit-specification '{"CpuCredits":"unlimited"}' \
  --tag-specifications '{"ResourceType":"instance","Tags":[{"Key":"Name","Value":"snuswe-backend"}]}' \
  --metadata-options '{"HttpEndpoint":"enabled","HttpPutResponseHopLimit":2,"HttpTokens":"required"}' \
  --private-dns-name-options '{"HostnameType":"ip-name","EnableResourceNameDnsARecord":true,"EnableResourceNameDnsAAAARecord":false}' \
  --iam-instance-profile Name=snuswe-server-role \
  --count "1"
```

## 🌐 Step 2: Assign an Elastic IP to the EC2 Instance

By default, an EC2 instance is assigned a dynamic public IP address, which can change every time the instance is stopped and started. To ensure consistent access (e.g., for SSH, deployments, or DNS records), it’s recommended to assign a static **Elastic IP (EIP)**.

You can assign an Elastic IP using either the AWS Console or the AWS CLI.

---

### Option 1: Using the AWS Console

1. Open the **EC2 Dashboard** in the [AWS Console](https://console.aws.amazon.com/ec2)
2. In the left-hand menu, click **“Elastic IPs”**
3. Click **“Allocate Elastic IP address”**
   - Leave the default settings (Amazon pool)
   - Click **“Allocate”**
4. After allocation, select the new Elastic IP
5. Click **“Actions” → “Associate Elastic IP address”**
6. Choose:
   - **Instance**: select the instance you launched in Step 1
   - **Private IP**: leave as default (usually auto-selected)
7. Click **“Associate”**

You’ve now attached a static IP address to your EC2 instance.

---

### Option 2: Using the AWS CLI

### 1. Allocate a new Elastic IP

```bash
aws ec2 allocate-address --domain vpc --region eu-north-1
```

### 2. Associate the Elastic IP with your instance

This step is enough if you already have an elastic ip ready for your ec2 instance
```bash
aws ec2 associate-address \
  --instance-id EC2_INSTANCE_ID \
  --allocation-id ELASTIC_IP_ID \
```

For example this is how your associate-address should look like

```bash
aws ec2 associate-address --instance-id i-02bcee510f83c1e6c --allocation-id eipalloc-048ce194ac4f934b9 --allow-reassociation
```

## ✅ Result

Your EC2 instance now has a **static public IP** that will persist across restarts. You can use this Elastic IP for:

- ✅ **SSH connections** (consistent address, even after reboot)
- ✅ **Application access** (via browser, API clients, etc.)
- ✅ **DNS records** (e.g., pointing `api.example.com` to your instance)

> ⚠️ **Reminder:** AWS charges for Elastic IPs that are **allocated but not associated** with a running instance. Make sure to release unused Elastic IPs to avoid unnecessary charges.

## 🌍 Step 3: Associate a DNS Record with the EC2 Instance

To make your backend services accessible via a custom domain (e.g., `api.example.com`), you need to associate your domain’s DNS with the Elastic IP of your EC2 instance.

You can use either **Amazon Route 53** (if your domain is managed in AWS) or an **external DNS provider** like Cloudflare, Namecheap, GoDaddy, etc.

---

### Option 1: Using Amazon Route 53

1. Go to the [Route 53 Console](https://console.aws.amazon.com/route53)
2. Open your hosted zone (e.g., `example.com`)
3. Click **“Create record”**
4. Enter the following details:

   - **Record name**: `api` (this will result in `api.example.com`)
   - **Record type**: `A – IPv4 address`
   - **Value**: enter the **Elastic IP** of your EC2 instance
   - **TTL**: keep default or lower (e.g., 300 seconds)
   - **Routing policy**: Simple routing (default)

5. Click **“Create records”**

It may take a few minutes for DNS changes to propagate globally.

---

### Option 2: Using an External DNS Provider

If your domain is managed outside of AWS (e.g., Namecheap, GoDaddy, Cloudflare):

1. Log in to your domain provider’s dashboard
2. Navigate to the **DNS settings** for your domain
3. Create a new **A record**:

   - **Host / Name**: `api` (or leave blank for root domain)
   - **Type**: `A`
   - **Value / Points to**: your EC2’s **Elastic IP**
   - **TTL**: default (or 300 seconds for faster propagation)

4. Save the DNS record

Once the DNS record has propagated, you can access your backend via `http://api.example.com` or `https://api.example.com`.

---

## 🔐 Step 4: Connect to the EC2 Instance via SSH

Once your EC2 instance is running and has an Elastic IP (or custom domain name), you can connect to it securely using SSH.

---

### 🧰 Requirements

- Your `.pem` SSH private key file (downloaded when the key pair was created)
- The public IP or DNS name of your EC2 instance
- An SSH client (Linux/macOS terminal or PuTTY on Windows)

---

### ✅ Connect from Linux/macOS

Open your terminal and run:

`ssh -i /path/to/your-key.pem ubuntu@<your-ec2-ip>`

> Replace `/path/to/your-key.pem` with the path to your private key, and `<your-ec2-ip>` with your Elastic IP or domain (e.g., `api.example.com`).

If necessary, fix file permissions by running:

`chmod 400 /path/to/your-key.pem`

---

### ✅ Connect from Windows (PuTTY)

1. Convert your `.pem` file to `.ppk` format using PuTTYgen
2. Open PuTTY
3. In the **Host Name** field, enter: `ubuntu@<your-ec2-ip>`
4. Under **Connection > SSH > Auth**, browse and select your `.ppk` file
5. Click **Open** to initiate the SSH session

---

⚠️ **Note**  
If you're **reusing old `.pem` files** for new EC2 instances, or you're connecting via a **domain name** (e.g., `api.example.com`), you may encounter the following SSH warning:

```
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
```

This happens because your SSH client detects that the server's identity (host key) has changed — often due to a new EC2 instance using the same IP or domain.

### ✅ To resolve it, run:

```
ssh-keygen -f ~/.ssh/known_hosts -R HOST
```

Replace `HOST` with the **IP address** or **domain name** of your EC2 instance.

Example:
``` bash
ssh-keygen -f ~/.ssh/known_hosts -R api.example.com
```


### ✅ Result

You are now connected to your EC2 instance and can begin configuring the environment, installing Docker, or deploying your services.


## 📜 Step 5: Copy and Run the EC2 Setup Script

Now that you're connected to your EC2 instance, the next step is to copy your setup script (`setup-ec2-script.sh`) to the server so it can install dependencies and configure the environment.

---

### 🧾 Create the Script on the EC2 Instance

On your EC2 instance:

1. Create a new file using `nano ec2-setup.sh`
2. Copy the contents of your script from `/docker/ec2-setup.sh` in your project repository and paste it into the `nano` editor
3. Save the file and exit (`CTRL+O`, `Enter`, then `CTRL+X`)

---

### 🔐 Make the Script Executable

Set execute permissions using:  
`chmod +x ec2-setup.sh`

---

### ▶️ Run the Script

Run the script with:  
`./ec2-setup.sh`

---

### ✅ Result

Your EC2 instance is now configured with everything specified in the script, such as Docker, Docker Compose, system packages, and any custom configuration required for your backend project.

## 🐳 Step 6: Deploy Services with Docker Compose

The `setup-ec2-script.sh` script you executed in the previous step has already downloaded the `docker-compose.yml` file onto the EC2 instance. This file is configured to pull container images directly from your Amazon ECR repository and define your backend architecture.

---

### ▶️ Navigate to the Compose File Directory

Change into the directory where the `docker-compose.yml` file was placed:  
`cd /home/ubuntu` (it should be where the ec2-setup.sh script is, usually on the root)

---

### 🚀 Start the Services

Run the following command to start all services in the background:
```bash
sudo service nginx stop
docker compose up -d
```
Previous command in script will run nginx so we have to stop it since it will be run inside a container. If we do not stop the nginx process it can result in an error that port 80 is already in use.


This will:

- Pull images from ECR
- Start containers for your backend, Nginx, Redis, Celery, etc.
- Set up container networking as defined in the Compose file

---

### ✅ Result

Your backend services are now running and accessible.

- Access the API or frontend via the EC2 Elastic IP or custom domain (e.g., `http://api.example.com`)
- Verify the status of the containers using `docker ps`
- Check service logs using `docker compose logs -f`

---

> 🧠 **Tip:** To stop everything later, run `docker compose down`

🎉 Deployment complete — your application is now live!


## 🚀 Setting up Repo for Deployment

To enable automatic build and deployment to your EC2 instance using GitHub Actions, you must configure several **repository secrets**. These are secure values stored in your GitHub repository that the pipeline uses to authenticate with AWS and access your EC2 instance.

### 🔐 How to Add Secrets

1. Go to your GitHub repository.
2. Click on **Settings** → **Secrets and variables** → **Actions**.
3. Click **New repository secret**.
4. Add each of the secrets listed below, one by one.

### 📋 Required Secrets

| Secret Name             | Description                                                                                     |
|-------------------------|-------------------------------------------------------------------------------------------------|
| `AWS_ACCESS_KEY_ID`     | Access key for an IAM user with permissions to push to Amazon ECR and interact with EC2.        |
| `AWS_SECRET_ACCESS_KEY` | Secret access key that pairs with the access key ID above.                                      |
| `EC2_HOST_MACHINE`      | Public IP or DNS of your EC2 instance (e.g., `13.48.123.45` or `ec2-...compute.amazonaws.com`). |
| `EC2_USER`              | Linux user for SSH access (e.g., `ubuntu` for Ubuntu AMIs, `ec2-user` for Amazon Linux).        |
| `EC2_SSH_KEY`           | The **private SSH key** (`.pem` file) used to connect to EC2. Paste the full contents here.     |
|---------------------------------------------------------------------------------------------------------------------------|

### 🧠 What These Are Used For

- **`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`**  
  Used by the GitHub Actions runner to:
  - Log in to Amazon ECR (Elastic Container Registry)
  - Push Docker images
  - (Optional) Use AWS CLI inside the EC2 instance (e.g., `aws ecr get-login-password`)

- **`EC2_HOST_MACHINE`, `EC2_USER`, and `EC2_SSH_KEY`**  
  Used to securely SSH into your EC2 server from the GitHub Actions runner to:
  - Pull the Docker image
  - Update services (e.g., restart Docker containers)
  - Run `docker compose` or other deployment scripts
# backend-haypp
