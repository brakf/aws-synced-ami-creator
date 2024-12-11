#!/usr/bin/env python3

import boto3
import argparse
import sys
from datetime import datetime
from typing import List, Dict
import time
import os
import signal

# Configurable settings
AMI_NAME_PATTERN = "{timestamp}_{instance_name}"
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

def get_script_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

class AMICreator:
    def __init__(self, instance_ids: List[str], auto_approve: bool = False, 
                 skip_stopping_instances: bool = False, skip_wait: bool = False, 
                 start_instances_after_ami_creation: bool = False,
                 region: str = None):
        # If region is provided, create client with specific region
        if region:
            self.ec2 = boto3.client('ec2', region_name=region)
        else:
            self.ec2 = boto3.client('ec2')
            
        self.instance_ids = instance_ids
        self.auto_approve = auto_approve
        self.skip_stopping_instances = skip_stopping_instances
        self.skip_wait = skip_wait
        self.start_instances_after_ami_creation = start_instances_after_ami_creation
        self.instances_info = {}
        self.pending_ami_ids = set()  # Track AMIs for cleanup
        
        # Set up interrupt handler
        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_interrupt)

    def _handle_interrupt(self, signum, frame):
        print("\n\nInterrupt received. Cleaning up AMIs...")
        for ami_id in self.pending_ami_ids:
            try:
                print(f"Deregistering AMI {ami_id}...")
                self.ec2.deregister_image(ImageId=ami_id)
                
                # Also remove associated snapshots
                response = self.ec2.describe_images(ImageIds=[ami_id])
                if response['Images']:
                    for mapping in response['Images'][0].get('BlockDeviceMappings', []):
                        if 'Ebs' in mapping and 'SnapshotId' in mapping['Ebs']:
                            snapshot_id = mapping['Ebs']['SnapshotId']
                            print(f"Deleting snapshot {snapshot_id}...")
                            self.ec2.delete_snapshot(SnapshotId=snapshot_id)
            except Exception as e:
                print(f"Error cleaning up AMI {ami_id}: {e}")
        
        print("Cleanup completed. Exiting...")
        sys.exit(1)

    def validate_instances(self) -> bool:
        try:
            response = self.ec2.describe_instances(InstanceIds=self.instance_ids)
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instance_id = instance['InstanceId']
                    instance_name = next((tag['Value'] for tag in instance['Tags'] 
                                       if tag['Key'] == 'Name'), instance_id)
                    self.instances_info[instance_id] = {
                        'name': instance_name,
                        'state': instance['State']['Name']
                    }
            return True
        except self.ec2.exceptions.ClientError as e:
            print(f"Error validating instances: {e}")
            return False

    def confirm_action(self) -> bool:
        if self.auto_approve:
            return True
        
        print("\nInstances to process:")
        for instance_id, info in self.instances_info.items():
            print(f"- {instance_id} ({info['name']})")
        
        if not self.skip_stopping_instances:
            print("\nWARNING: Instances will be stopped before creating AMIs!")
        
        return input("\nProceed with AMI creation? (y/N): ").lower() == 'y'

    def stop_instances(self) -> bool:
        if self.skip_stopping_instances:
            print("Skipping instance stop as requested")
            return True

        try:
            self.ec2.stop_instances(InstanceIds=self.instance_ids)
            self._wait_for_instances_state('stopped')
            return True
        except Exception as e:
            print(f"Error stopping instances: {e}")
            return False

    def create_amis(self) -> Dict[str, str]:
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        ami_map = {}

        for instance_id, info in self.instances_info.items():
            ami_name = AMI_NAME_PATTERN.format(
                timestamp=timestamp,
                instance_name=info['name']
            )
            try:
                response = self.ec2.create_image(
                    InstanceId=instance_id,
                    Name=ami_name,
                    Description=f"Created from {instance_id} ({info['name']})"
                )
                ami_id = response['ImageId']
                ami_map[instance_id] = ami_id
                self.pending_ami_ids.add(ami_id)  # Track for cleanup
                print(f"Creating AMI {ami_id} for instance {instance_id}")
            except Exception as e:
                print(f"Error creating AMI for instance {instance_id}: {e}")
                ami_map[instance_id] = None

        return ami_map

    def wait_for_amis(self, ami_map: Dict[str, str]):
        if self.skip_wait:
            print("Skipping AMI wait as requested")
            return

        print("\nWaiting for AMIs to complete...")
        pending_amis = {ami_id: {'instance_id': instance_id} 
                       for instance_id, ami_id in ami_map.items() if ami_id}
        
        start_time = time.time()
        results = []
        last_check = 0
        
        while pending_amis:
            try:
                elapsed = int(time.time() - start_time)
                print(f"\rTime elapsed: {elapsed}s", end='', flush=True)
                
                # Check AMI status every 5 seconds
                if elapsed - last_check >= 5:
                    last_check = elapsed
                    response = self.ec2.describe_images(ImageIds=list(pending_amis.keys()))
                    images = {image['ImageId']: image for image in response['Images']}
                    
                    for ami_id, info in sorted(pending_amis.items()):
                        instance_id = info['instance_id']
                        instance_name = self.instances_info[instance_id]['name']
                        
                        if ami_id in images:
                            image = images[ami_id]
                            state = image['State']
                            
                            if state == 'available':
                                results.append(f"✓ AMI {ami_id} for {instance_name} ({instance_id}) - available")
                                del pending_amis[ami_id]
                                self.pending_ami_ids.remove(ami_id)
                            elif state == 'failed':
                                results.append(f"✗ AMI {ami_id} for {instance_name} ({instance_id}) - failed")
                                del pending_amis[ami_id]
                                self.pending_ami_ids.remove(ami_id)
                
                time.sleep(1)  # Update counter every second
                    
            except Exception as e:
                print(f"\nError monitoring AMIs: {e}")
                break

        # Clear the time counter line and show results
        print("\n\nAMI Creation Results:")
        for result in results:
            print(result)
        
        total_time = int(time.time() - start_time)
        print(f"\nTotal time: {total_time} seconds")

    def start_instances(self):
        if not self.start_instances_after_ami_creation:
            return

        try:
            self.ec2.start_instances(InstanceIds=self.instance_ids)
            print("Started instances")
        except Exception as e:
            print(f"Error starting instances: {e}")

    def _wait_for_instances_state(self, target_state: str):
        waiter = self.ec2.get_waiter(f'instance_{target_state}')
        waiter.wait(InstanceIds=self.instance_ids)

def main():
    parser = argparse.ArgumentParser(description='Create AMIs from EC2 instances')
    parser.add_argument('instance_ids', nargs='+', help='List of EC2 instance IDs')
    parser.add_argument('--auto-approve', action='store_true', 
                       help='Skip confirmation prompt')
    parser.add_argument('--skip-stopping-instances', action='store_true', 
                       help='Do not stop instances before creating AMIs')
    parser.add_argument('--skip-wait', action='store_true', 
                       help='Do not wait for AMI creation to complete')
    parser.add_argument('--start-instances-after-ami-creation', action='store_true', 
                       help='Start instances after AMI creation')
    parser.add_argument('--region', 
                       help='AWS region (overrides default from AWS profile)')
    
    args = parser.parse_args()

    creator = AMICreator(
        args.instance_ids,
        auto_approve=args.auto_approve,
        skip_stopping_instances=args.skip_stopping_instances,
        skip_wait=args.skip_wait,
        start_instances_after_ami_creation=args.start_instances_after_ami_creation,
        region=args.region
    )

    if not creator.validate_instances():
        sys.exit(1)

    if not creator.confirm_action():
        print("Operation cancelled")
        sys.exit(0)

    if not creator.stop_instances():
        sys.exit(1)

    ami_map = creator.create_amis()
    creator.wait_for_amis(ami_map)
    creator.start_instances()

if __name__ == "__main__":
    main()
