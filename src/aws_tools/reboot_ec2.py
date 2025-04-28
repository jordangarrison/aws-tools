#!/usr/bin/env python3
"""
EC2 Instance Reboot Utility

This module allows for rebooting AWS EC2 instances by instance ID or Name tag.
"""

import argparse
import os
import sys
import time
from typing import Optional

try:
    import boto3
    import colorama
    from botocore.exceptions import ClientError, NoCredentialsError, WaiterError
    from colorama import Fore, Style
except ImportError:
    print("Error: Required dependencies not found.")
    print("Please install with: pdm install")
    sys.exit(1)

# Initialize colorama
colorama.init(autoreset=True)


class EC2Rebooter:
    """Class to handle EC2 instance reboots"""

    def __init__(
        self,
        region: Optional[str] = None,
        profile: Optional[str] = None,
        verbose: bool = False,
    ):
        """Initialize the EC2 client"""
        session_kwargs = {}
        if profile:
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)

        client_kwargs = {}
        if region:
            client_kwargs["region_name"] = region

        self.ec2 = session.client("ec2", **client_kwargs)
        self.region = region or boto3.Session().region_name or "us-west-2"
        self.verbose = verbose

    def get_instance_by_name(self, name: str) -> Optional[str]:
        """
        Find an EC2 instance by its Name tag.

        Args:
            name: The Name tag value to search for

        Returns:
            The instance ID if found, None otherwise
        """
        try:
            response = self.ec2.describe_instances(
                Filters=[
                    {"Name": "tag:Name", "Values": [name]},
                    {
                        "Name": "instance-state-name",
                        "Values": ["pending", "running", "stopping", "stopped"],
                    },
                ]
            )

            instances = []
            for reservation in response.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    instances.append(instance["InstanceId"])

            if not instances:
                print(
                    f"{Fore.RED}Error: No instances found with Name tag '{name}'.{Style.RESET_ALL}"
                )
                return None

            if len(instances) > 1:
                print(
                    f"{Fore.RED}Error: Multiple instances found with Name tag '{name}'. Please use instance-id instead.{Style.RESET_ALL}"
                )
                for instance_id in instances:
                    print(f"  - {instance_id}")
                return None

            return instances[0]

        except ClientError as e:
            print(f"{Fore.RED}Error searching for instance: {str(e)}{Style.RESET_ALL}")
            return None

    def reboot_instance(self, instance_id: str, dry_run: bool = False) -> bool:
        """
        Reboot an EC2 instance.

        Args:
            instance_id: The EC2 instance ID to reboot
            dry_run: Whether to run in dry-run mode (no actual changes)

        Returns:
            True if successful, False otherwise
        """
        try:
            print(
                f"{Fore.YELLOW}Rebooting instance {instance_id} in region {self.region}...{Style.RESET_ALL}"
            )

            # First verify that the instance exists and is in a valid state
            describe_response = self.ec2.describe_instances(InstanceIds=[instance_id])
            if not describe_response.get("Reservations") or not describe_response[
                "Reservations"
            ][0].get("Instances"):
                print(
                    f"{Fore.RED}Error: Instance {instance_id} not found{Style.RESET_ALL}"
                )
                return False

            instance = describe_response["Reservations"][0]["Instances"][0]
            instance_state = instance.get("State", {}).get("Name")
            print(
                f"{Fore.CYAN}Instance current state: {instance_state}{Style.RESET_ALL}"
            )

            if instance_state not in ["running", "stopping", "stopped"]:
                print(
                    f"{Fore.RED}Warning: Instance is in '{instance_state}' state. Reboot may not work as expected.{Style.RESET_ALL}"
                )

            # Perform the reboot operation
            response = self.ec2.reboot_instances(
                InstanceIds=[instance_id], DryRun=dry_run
            )

            # Check response metadata for validation
            status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            request_id = response.get("ResponseMetadata", {}).get(
                "RequestId", "Unknown"
            )

            if dry_run:
                print(
                    f"{Fore.CYAN}DRY RUN: Would reboot instance {instance_id}{Style.RESET_ALL}"
                )
                return True
            else:
                if status_code == 200:
                    print(
                        f"{Fore.GREEN}Successfully initiated reboot for instance {instance_id}{Style.RESET_ALL}"
                    )

                    if self.verbose:
                        print(
                            f"{Fore.CYAN}API Request ID: {request_id}{Style.RESET_ALL}"
                        )
                        print(
                            f"{Fore.CYAN}To verify this API call in CloudTrail:{Style.RESET_ALL}"
                        )
                        print(
                            f"{Fore.CYAN}  1. Open AWS CloudTrail console: https://{self.region}.console.aws.amazon.com/cloudtrail/home?region={self.region}#{Style.RESET_ALL}"
                        )
                        print(
                            f"{Fore.CYAN}  2. Select 'Event history'{Style.RESET_ALL}"
                        )
                        print(
                            f"{Fore.CYAN}  3. Filter by 'Event name' = 'RebootInstances'{Style.RESET_ALL}"
                        )
                        print(
                            f"{Fore.CYAN}  4. Look for Request ID: {request_id}{Style.RESET_ALL}"
                        )

                    # Verify the instance is entering reboot state by waiting briefly and checking state
                    print(
                        f"{Fore.YELLOW}Verifying reboot initiated...{Style.RESET_ALL}"
                    )
                    time.sleep(5)  # Wait briefly to let AWS register the state change

                    try:
                        post_response = self.ec2.describe_instances(
                            InstanceIds=[instance_id]
                        )
                        if post_response.get("Reservations") and post_response[
                            "Reservations"
                        ][0].get("Instances"):
                            post_state = (
                                post_response["Reservations"][0]["Instances"][0]
                                .get("State", {})
                                .get("Name")
                            )
                            print(
                                f"{Fore.CYAN}Post-reboot request state: {post_state}{Style.RESET_ALL}"
                            )

                            # EC2 reboot doesn't always show a visible state change in the API
                            # Instance state remains 'running' during a reboot in most cases
                            if post_state == "running" and instance_state == "running":
                                print(
                                    f"{Fore.YELLOW}Note: EC2 API shows 'running' status even during reboot.{Style.RESET_ALL}"
                                )
                                print(
                                    f"{Fore.YELLOW}The reboot is likely still in progress at the instance level.{Style.RESET_ALL}"
                                )
                    except Exception as e:
                        print(
                            f"{Fore.YELLOW}Unable to verify post-reboot state: {str(e)}{Style.RESET_ALL}"
                        )

                    return True
                else:
                    print(
                        f"{Fore.RED}Unexpected API response code: {status_code}{Style.RESET_ALL}"
                    )
                    return False

        except ClientError as e:
            if e.response["Error"]["Code"] == "DryRunOperation":
                print(
                    f"{Fore.CYAN}DRY RUN: Would reboot instance {instance_id}{Style.RESET_ALL}"
                )
                return True
            else:
                print(
                    f"{Fore.RED}Error rebooting instance {instance_id}: {str(e)}{Style.RESET_ALL}"
                )
                print(
                    f"{Fore.RED}Error code: {e.response.get('Error', {}).get('Code')}{Style.RESET_ALL}"
                )
                return False

    def wait_for_instance_ok(self, instance_id: str, timeout: int = 600) -> bool:
        """
        Wait for an EC2 instance to pass status checks.

        Args:
            instance_id: The EC2 instance ID to wait for
            timeout: Timeout in seconds

        Returns:
            True if instance is OK within timeout, False otherwise
        """
        try:
            attempts = timeout // 15  # 15 seconds between checks
            delay = 15

            print(
                f"{Fore.YELLOW}Waiting for instance {instance_id} to pass status checks...{Style.RESET_ALL}"
            )
            print(
                f"{Fore.YELLOW}Will check every {delay} seconds for up to {timeout} seconds.{Style.RESET_ALL}"
            )

            waiter = self.ec2.get_waiter("instance_status_ok")
            waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={"Delay": delay, "MaxAttempts": attempts},
            )

            print(f"{Fore.GREEN}Instance {instance_id} is now OK!{Style.RESET_ALL}")
            return True

        except WaiterError as e:
            print(
                f"{Fore.RED}Error waiting for instance {instance_id}: {str(e)}{Style.RESET_ALL}"
            )
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="EC2 Instance Reboot Utility")

    # Create mutually exclusive group for instance identification
    instance_group = parser.add_mutually_exclusive_group(required=True)
    instance_group.add_argument("--instance-id", help="EC2 instance ID to reboot")
    instance_group.add_argument("--name", help="EC2 instance Name tag to search for")

    # Other arguments
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-west-2"),
        help="AWS region (default: AWS_REGION env var or us-west-2)",
    )
    parser.add_argument("--profile", help="AWS profile to use")
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for instance to pass all status checks after reboot",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Timeout in seconds when waiting for instance status (default: 600)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making actual changes",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed API response information and CloudTrail guidance",
    )

    args = parser.parse_args()

    print("=" * 40)
    print("EC2 Instance Reboot Utility")
    print("=" * 40)

    # Initialize rebooter
    rebooter = EC2Rebooter(
        region=args.region, profile=args.profile, verbose=args.verbose
    )

    # Determine instance ID
    instance_id = args.instance_id
    if args.name:
        instance_id = rebooter.get_instance_by_name(args.name)
        if not instance_id:
            sys.exit(1)

    # Reboot the instance
    result = rebooter.reboot_instance(instance_id, args.dry_run)
    if not result:
        sys.exit(1)

    # Wait for instance to be OK if requested
    if args.wait and not args.dry_run:
        wait_result = rebooter.wait_for_instance_ok(instance_id, args.timeout)
        if not wait_result:
            sys.exit(1)

    print(f"{Fore.GREEN}Reboot operation completed successfully.{Style.RESET_ALL}")

    if not args.dry_run and not args.verbose:
        print(
            f"{Fore.YELLOW}For detailed API verification, run with --verbose flag.{Style.RESET_ALL}"
        )


if __name__ == "__main__":
    main()
