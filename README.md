# AMI Creator Script

A Python script for creating Amazon Machine Images (AMIs) from multiple EC2 instances with various control options.

## Prerequisites

- Python 3.6+
- boto3
- Configured AWS credentials with appropriate permissions

## Installation

### Option 1: Run as Python Script
1. Ensure you have Python 3.6 or higher installed
2. Install required dependencies:
   ```bash
   pip install boto3
   ```
3. Make the script executable:
   ```bash
   chmod +x create-amis.py
   ```

### Option 2: Build Standalone Executable
1. Install build dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the build script:
   ```bash
   python build.py
   ```
3. The executable will be created in the `dist` directory
4. Move the executable to your desired location:
   ```bash
   # On Linux/MacOS
   sudo mv dist/create-amis /usr/local/bin/
   
   # On Windows, move dist/create-amis.exe to your desired location
   ```

## Usage

```bash
create-amis INSTANCE_ID [INSTANCE_ID ...] [options]
```

### Arguments

- `INSTANCE_ID`: One or more EC2 instance IDs to create AMIs from

### Options

- `--auto-approve`: Skip confirmation prompt
- `--skip-stopping-instances`: Create AMIs without stopping instances (may result in inconsistent AMIs)
- `--skip-wait`: Don't wait for AMI creation to complete
- `--start-instances-after-ami-creation`: Start instances after AMI creation is complete
- `--region`: AWS region (overrides default from AWS profile)

### Examples

Create AMIs with confirmation prompt:
```bash
./create-amis.py i-1234567890 i-0987654321
```

Create AMIs without confirmation and start instances afterward:
```bash
./create-amis.py i-1234567890 i-0987654321 --auto-approve --start-instances-after-ami-creation
```

Create AMIs without stopping instances:
```bash
./create-amis.py i-1234567890 --skip-stopping-instances
```

Create AMIs in a specific region:
```bash
./create-amis.py i-1234567890 --region us-west-2
```

## Behavior

1. The script first validates all provided instance IDs
2. Unless `--auto-approve` is used, it asks for confirmation
3. Unless `--skip-stopping-instances` is used, it stops the instances
4. Creates all AMIs in parallel with names following the pattern: `{timestamp}_{instance_name}`
5. Unless `--skip-wait` is used, waits for AMI creation to complete
6. If `--start-instances-after-ami-creation` is used, starts the instances

Note: The script triggers all AMI creations simultaneously and then monitors their progress in parallel for faster completion time.

## AMI Naming

AMIs are named using the following pattern:
```
{timestamp}_{instance_name}
```
Where:
- `timestamp` is in format: YYYYMMDD_HHMMSS
- `instance_name` is taken from the instance's Name tag

## Error Handling

The script includes error handling for:
- Invalid instance IDs
- AWS API errors
- AMI creation failures
- Instance state transition failures

## Exit Codes

- 0: Success
- 1: Error occurred during execution

## Configuration

The AMI naming pattern can be modified by changing the `AMI_NAME_PATTERN` constant at the top of the script.