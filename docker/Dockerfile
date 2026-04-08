FROM python:3.11.6

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y python3-pip

# Copy dependencies and install them
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install uvicorn[standard]

# Copy project files
COPY . /app/

# Copy the entrypoint script and give it execute permissions
COPY docker/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Use the entrypoint script
ENTRYPOINT ["/entrypoint.sh"]