import csv
import subprocess
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def read_ip_list(file_name):
    """
    Reads IP addresses from a CSV file.
    """
    ip_list = []
    with open(file_name, mode='r') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            ip_list.append(row[0])
    return ip_list

def run_ssh_command(ip, username, password, command):
    """
    Executes an SSH command using the Linux ssh command.
    """
    try:
        # Use sshpass to provide the password
        full_command = f"sshpass -p {password} ssh -o StrictHostKeyChecking=no {username}@{ip} '{command}'"
        logging.info(f"Executing command: {full_command}")

        result = subprocess.run(full_command, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            logging.error(f"Error executing command: {command}, Error: {result.stderr}")
            return ""

        return result.stdout
    except Exception as e:
        logging.error(f"Failed to execute SSH command: {command}, Error: {e}")
        return ""

def parse_cdp_output(output):
    """
    Parses the 'show cdp neighbors' output to find devices and interfaces.
    """
    device_info = {}
    lines = output.splitlines()
    logging.debug(f"CDP Neighbors Output Lines: {lines}")  # Debug log for raw CDP output

    # Log the raw output for analysis
    logging.info(f"Raw CDP Output:\n{output}")

    # Skip header lines and empty lines
    for line in lines:
        logging.debug(f"Processing line: {line}")  # Log each line being processed
        # Match lines with device ID, local interface, hold time, capability, platform, and port ID
        match = re.search(r'^(?P<device_id>\S+)\s+(?P<local_interface>\S+\s+\S+)\s+\d+\s+[RTBSHIPDCM]+\s+(?P<platform>\S+)\s+\S+', line)
        if match:
            device_id = match.group('device_id')
            local_interface = match.group('local_interface').replace(' ', '')
            logging.info(f"Found device: {device_id} on interface: {local_interface}")

            # Only store the first occurrence of each device ID
            if device_id not in device_info:
                device_info[device_id] = local_interface

    return device_info

def parse_cdp_detail_output(output):
    """
    Parses the detailed 'show cdp neighbor [interface] detail' output to extract platform and version.
    """
    platform_match = re.search(r'Platform: (.+?),', output)
    version_match = re.search(r'Version\s+:\s+(.+?)\n', output, re.DOTALL)

    logging.debug(f"CDP Detail Output: {output}")  # Debug log for CDP detail output

    platform = platform_match.group(1) if platform_match else 'N/A'
    version = version_match.group(1).strip() if version_match else 'N/A'

    logging.info(f"Parsed Platform: {platform}, Version: {version}")  # Log parsed platform and version

    return platform, version

def write_to_csv(data, file_name='output.csv'):
    """
    Writes extracted data to a CSV file.
    """
    with open(file_name, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["IP", "Device Type", "OS Version"])
        for row in data:
            writer.writerow(row)
        logging.info(f"Data has been written to {file_name}")

def main():
    ip_list = read_ip_list('list.csv')
    username = 'cisco'  # Test username
    password = 'cisco123'  # Test password

    results = []

    for ip in ip_list:
        logging.info(f"Connecting to {ip}...")

        # Run 'show cdp neighbors' command
        cdp_command = 'show cdp neighbors'
        cdp_output = run_ssh_command(ip, username, password, cdp_command)

        if not cdp_output:
            logging.warning(f"No CDP neighbor output from {ip}. Skipping.")
            continue

        device_interfaces = parse_cdp_output(cdp_output)
        if not device_interfaces:
            logging.warning(f"No devices found in CDP output from {ip}. Skipping.")
            continue

        for device_id, interface in device_interfaces.items():
            # Correct interface naming for detailed command
            corrected_interface = interface.replace('Fas', 'FastEthernet').replace('Gig', 'GigabitEthernet')
            logging.info(f"Running detailed command for device {device_id} on interface {corrected_interface}")

            detail_command = f"show cdp neighbor {corrected_interface} detail"
            cdp_detail_output = run_ssh_command(ip, username, password, detail_command)

            if not cdp_detail_output:
                logging.warning(f"No detailed CDP output for device {device_id} on {ip}. Skipping interface {interface}.")
                continue

            platform, version = parse_cdp_detail_output(cdp_detail_output)
            if platform == 'N/A' or version == 'N/A':
                logging.warning(f"Failed to parse platform/version for device {device_id} on {ip}.")
                continue

            # Save result
            results.append([ip, platform, version])

    write_to_csv(results)

if __name__ == "__main__":
    main()
