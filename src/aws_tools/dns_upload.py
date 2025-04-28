#!/usr/bin/env python3
"""
Route53 DNS Records Bulk Upload Utility

This module processes CSV files with DNS records and uploads them to AWS Route53.
"""

import argparse
import csv
import json
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

try:
    import boto3
    import colorama
    from botocore.exceptions import ClientError, NoCredentialsError
    from colorama import Fore, Style
except ImportError:
    print("Error: Required dependencies not found.")
    print("Please install with: pdm install")
    sys.exit(1)

# Initialize colorama
colorama.init(autoreset=True)


class Route53Uploader:
    """Class to handle Route53 DNS record uploads"""

    def __init__(self):
        """Initialize the Route53 client"""
        self.route53 = boto3.client("route53")

    def get_hosted_zone_id(self, zone_name: str) -> Optional[str]:
        """
        Get the hosted zone ID for a given zone name.

        Args:
            zone_name: The DNS zone name (e.g., example.com)

        Returns:
            The hosted zone ID or None if not found
        """
        try:
            # Ensure the zone name ends with a dot
            if not zone_name.endswith("."):
                zone_name_search = [f"{zone_name}.", zone_name]
            else:
                zone_name_search = [zone_name, zone_name[:-1]]

            response = self.route53.list_hosted_zones()
            for hosted_zone in response["HostedZones"]:
                if hosted_zone["Name"] in zone_name_search:
                    # Extract just the ID part
                    return hosted_zone["Id"].split("/")[-1]

            # If no exact match found, try again searching more broadly
            for hosted_zone in response["HostedZones"]:
                if any(name in hosted_zone["Name"] for name in zone_name_search):
                    return hosted_zone["Id"].split("/")[-1]

            return None
        except (ClientError, NoCredentialsError) as e:
            print(f"{Fore.RED}Error getting hosted zone: {str(e)}{Style.RESET_ALL}")
            return None

    def create_change_batch(
        self, record_type: str, record_name: str, zone_name: str, value: str, ttl: int
    ) -> Dict:
        """
        Create a change batch for Route53.

        Args:
            record_type: The DNS record type (e.g., CNAME, TXT)
            record_name: The DNS record name
            zone_name: The DNS zone name
            value: The DNS record value
            ttl: The DNS record TTL

        Returns:
            A change batch dictionary
        """
        # Ensure the record name is fully qualified
        if not record_name.endswith(zone_name):
            fqdn = f"{record_name}.{zone_name}"
        else:
            fqdn = record_name

        # Add trailing dot if missing
        if not fqdn.endswith("."):
            fqdn = f"{fqdn}."

        change_batch = {
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": fqdn,
                        "Type": record_type,
                        "TTL": ttl,
                        "ResourceRecords": [],
                    },
                }
            ]
        }

        # Different handling based on record type
        if record_type == "TXT":
            # TXT records need to be wrapped in quotes
            change_batch["Changes"][0]["ResourceRecordSet"]["ResourceRecords"].append(
                {"Value": f'"{value}"'}
            )
        else:
            change_batch["Changes"][0]["ResourceRecordSet"]["ResourceRecords"].append(
                {"Value": value}
            )

        return change_batch

    def upload_record(
        self,
        hosted_zone_id: str,
        record_type: str,
        record_name: str,
        zone_name: str,
        value: str,
        ttl: int,
    ) -> bool:
        """
        Upload a single DNS record to Route53.

        Args:
            hosted_zone_id: The Route53 hosted zone ID
            record_type: The DNS record type (e.g., CNAME, TXT)
            record_name: The DNS record name
            zone_name: The DNS zone name
            value: The DNS record value
            ttl: The DNS record TTL

        Returns:
            True if successful, False otherwise
        """
        try:
            change_batch = self.create_change_batch(
                record_type, record_name, zone_name, value, ttl
            )

            response = self.route53.change_resource_record_sets(
                HostedZoneId=hosted_zone_id, ChangeBatch=change_batch
            )

            change_id = response["ChangeInfo"]["Id"]
            print(
                f"{Fore.GREEN}Successfully submitted change. Change ID: {change_id}{Style.RESET_ALL}"
            )
            return True
        except ClientError as e:
            print(
                f"{Fore.RED}Error uploading record {record_name}.{zone_name}: {str(e)}{Style.RESET_ALL}"
            )
            return False


def process_csv(csv_file: str, dry_run: bool = False) -> None:
    """
    Process a CSV file with DNS records.

    Args:
        csv_file: Path to the CSV file
        dry_run: Whether to run in dry-run mode (no actual changes)
    """
    if not os.path.exists(csv_file):
        print(f"{Fore.RED}Error: File {csv_file} not found.{Style.RESET_ALL}")
        sys.exit(1)

    uploader = Route53Uploader()
    successes = 0
    failures = 0
    skipped = 0

    # Cache for hosted zone IDs to avoid repeated lookups
    zone_id_cache = {}

    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames or set(reader.fieldnames) != {
            "env",
            "zone",
            "type",
            "name",
            "value",
            "ttl",
        }:
            print(
                f"{Fore.RED}Error: CSV file must have these headers: env,zone,type,name,value,ttl{Style.RESET_ALL}"
            )
            sys.exit(1)

        for row_num, row in enumerate(
            reader, start=2
        ):  # Start at 2 to account for header
            try:
                env = row["env"].strip()
                zone = row["zone"].strip()
                record_type = row["type"].strip().upper()
                name = row["name"].strip()
                value = row["value"].strip()
                ttl = int(row["ttl"].strip())

                print(
                    f"\n{Fore.YELLOW}Processing row {row_num}: {env} {zone} {record_type} {name} {value} {ttl}{Style.RESET_ALL}"
                )

                # Skip unsupported record types
                if record_type not in {
                    "CNAME",
                    "TXT",
                    "A",
                    "AAAA",
                    "MX",
                    "NS",
                    "PTR",
                    "SRV",
                    "SOA",
                }:
                    print(
                        f"{Fore.YELLOW}Skipping unsupported record type: {record_type}{Style.RESET_ALL}"
                    )
                    skipped += 1
                    continue

                # Get hosted zone ID (use cache if available)
                if zone in zone_id_cache:
                    hosted_zone_id = zone_id_cache[zone]
                else:
                    hosted_zone_id = uploader.get_hosted_zone_id(zone)
                    if hosted_zone_id:
                        zone_id_cache[zone] = hosted_zone_id

                if not hosted_zone_id:
                    print(
                        f"{Fore.RED}Error: Hosted zone {zone} not found.{Style.RESET_ALL}"
                    )
                    failures += 1
                    continue

                print(f"Found hosted zone ID: {hosted_zone_id} for {zone}")

                if dry_run:
                    change_batch = uploader.create_change_batch(
                        record_type, name, zone, value, ttl
                    )
                    print(f"{Fore.CYAN}DRY RUN: Would apply change:{Style.RESET_ALL}")
                    print(json.dumps(change_batch, indent=2))
                    successes += 1
                else:
                    result = uploader.upload_record(
                        hosted_zone_id, record_type, name, zone, value, ttl
                    )
                    if result:
                        successes += 1
                    else:
                        failures += 1

                    # Small delay to avoid hitting API rate limits
                    time.sleep(0.5)

            except (KeyError, ValueError) as e:
                print(
                    f"{Fore.RED}Error processing row {row_num}: {str(e)}{Style.RESET_ALL}"
                )
                failures += 1

    print(
        f"\n{Fore.GREEN}Summary: {successes} successful, {failures} failed, {skipped} skipped{Style.RESET_ALL}"
    )


def create_template():
    """Create a template CSV file"""
    template_file = "dns_records_template.csv"
    with open(template_file, "w") as f:
        f.write("env,zone,type,name,value,ttl\n")
        f.write("prod,example.com,CNAME,www,target.example.com,300\n")
        f.write("prod,example.com,TXT,_verification,verification-code-here,300\n")

    print(f"{Fore.GREEN}Created template CSV at {template_file}{Style.RESET_ALL}")
    print(
        f"{Fore.YELLOW}Please fill this template with your DNS records and run the script again.{Style.RESET_ALL}"
    )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Route53 DNS Records Bulk Upload Utility"
    )
    parser.add_argument("csv_file", nargs="?", help="CSV file with DNS records")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making actual changes",
    )
    parser.add_argument(
        "--create-template", action="store_true", help="Create a template CSV file"
    )

    args = parser.parse_args()

    print("=" * 40)
    print("Route53 DNS Records Bulk Upload Utility")
    print("=" * 40)

    if args.create_template:
        create_template()
        return

    if not args.csv_file:
        parser.print_help()
        print(
            f"\n{Fore.YELLOW}No CSV file specified. Use --create-template to create a template.{Style.RESET_ALL}"
        )
        sys.exit(1)

    process_csv(args.csv_file, args.dry_run)


if __name__ == "__main__":
    main()
