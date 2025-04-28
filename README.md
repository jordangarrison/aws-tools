# AWS Tools Collection

A collection of CLI utilities for working with AWS services, packaged with Nix for reproducible environments.

## Available Tools

### dns-upload

Upload and manage DNS records in AWS Route53 from CSV files.

**Features:**

- Support for multiple record types (CNAME, TXT, A, AAAA, etc.)
- Dry-run mode to preview changes
- Colorized output

### reboot-ec2

Quickly reboot an EC2 instance.

```bash
# Reboot by ID
reboot-ec2 --instance-id i-asdfasdfasdfasdfsd --region us-west-2

# Reboot by Name tag and wait for health checks
reboot-ec2 --name MyInstanceName --wait --region us-west-2
```

## Installation

### Using Nix Flakes

```bash
# Install the entire AWS tools collection
nix profile install github:jordangarrison/aws-tools

# Install a specific tool
nix profile install github:jordangarrison/aws-tools#dns-upload
```

### Using Devbox

[Devbox](https://www.jetify.com/devbox/) provides an easy way to get started without installing Nix directly.

```bash
# Install Devbox if you haven't already
# https://www.jetify.com/devbox/docs/installing/

# Initialize Devbox in the project directory
devbox init

# Add the Nix flake from this repository
echo '{
  "packages": [],
  "flakes": [
    "github:jordangarrison/aws-tools"
  ]
}' > devbox.json

# Enter the development environment
devbox shell

# Run any tool
dns-upload --help

# Exit the shell when done
exit
```

### Using Nix Development Shell

```bash
# Enter development environment
nix develop
```

### Using PDM (for Python-based development)

```bash
pdm install
```

## Development

### Working with Nix Flakes

```bash
# Enter the development shell
nix develop

# Run a tool directly without installing
nix run .#dns-upload -- --help

# Test specific tools
nix run .#dns-upload -- path/to/your/records.csv
```

### Building and Deploying

```bash
# Build a specific package without installing
nix build .#dns-upload

# Install to your profile
nix profile install .#dns-upload

# Run directly without installing
nix run .#dns-upload -- --dry-run path/to/your/records.csv

# Add this repository to your flake inputs
# In your flake.nix:
# inputs.aws-tools.url = "github:jordangarrison/aws-tools";
# Then in your outputs:
# outputs = { self, nixpkgs, aws-tools, ... }: { ... };
```

### Local Development

```bash
# Install development dependencies
pdm install --dev

# Run linting
pdm run black .
pdm run isort .
pdm run flake8

# Run type checking
pdm run mypy scripts/
```

## Tool Documentation

### Route53 DNS Uploader

Upload DNS records to AWS Route53 from CSV files.

#### Usage

```bash
# Create a template CSV file
dns-upload --create-template

# Upload DNS records from a CSV file
dns-upload path/to/your/records.csv

# Dry run (preview changes without applying)
dns-upload --dry-run path/to/your/records.csv
```

#### CSV Format

The CSV file should have the following headers:

```csv
env,zone,type,name,value,ttl
```

Example:

```csv
prod,example.com,CNAME,www,target.example.com,300
prod,example.com,TXT,_verification,verification-code-here,300
```

### EC2 Instance Reboot Utility

Reboot EC2 instances by instance ID or Name tag.

```bash
# Reboot by instance ID
reboot-ec2 --instance-id i-asdfasdfasdfasdfsd

# Reboot by Name tag
reboot-ec2 --name MyInstanceName

# Specify region (defaults to AWS_REGION env var or us-west-2)
reboot-ec2 --instance-id i-asdfasdfasdfasdfsd --region us-east-1

# Use a specific AWS profile
reboot-ec2 --instance-id i-asdfasdfasdfasdfsd --profile my-profile

# Wait for instance to pass status checks after reboot
reboot-ec2 --instance-id i-asdfasdfasdfasdfsd --wait

# Custom timeout when waiting (default: 600 seconds)
reboot-ec2 --instance-id i-asdfasdfasdfasdfsd --wait --timeout 300

# Dry run (show what would happen without making changes)
reboot-ec2 --instance-id i-asdfasdfasdfasdfsd --dry-run
```
