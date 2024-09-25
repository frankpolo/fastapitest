import csv
import glob
import os
import sys
import argparse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_summary_csv(file_path):
    attachrequest_count = 0
    attachcomplete_count = 0
    ping_max = float('-inf')
    ping_min = float('inf')
    ping_avg = 0
    ping_attempt_count = 0
    ping_success_count = 0
    ping_error_count = 0
    ping_avg_count = 0

    with open(file_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Count attach requests and completes
            if row.get('NAS') == 'RegRequest5G':
                attachrequest_count += 1
            elif row.get('NAS') == 'RegComplete5G':
                attachcomplete_count += 1

            # Calculate ping statistics
            if row.get('Max'):
                ping_max = max(ping_max, float(row['Max']))
            if row.get('Min'):
                ping_min = min(ping_min, float(row['Min']))
            if row.get('Avg'):
                ping_avg += float(row['Avg'])
                ping_avg_count += 1
            if row.get('Total'):
                ping_attempt_count += int(row['Total'])
            if row.get('Success'):
                ping_success_count += int(row['Success'])
            if row.get('Error'):
                ping_error_count += int(row['Error'])

    # Calculate overall ping average
    ping_avg = ping_avg / ping_avg_count if ping_avg_count > 0 else 0

    # Handle case where no valid ping data was found
    if ping_max == float('-inf'):
        ping_max = 0
    if ping_min == float('inf'):
        ping_min = 0

    return {
        'attachrequest_count': attachrequest_count/2,
        'attachcomplete_count': attachcomplete_count,
        'ping_max': f"{ping_max:.2f}",
        'ping_min': f"{ping_min:.2f}",
        'ping_avg': f"{ping_avg:.2f}",
        'ping_attempt_count': ping_attempt_count,
        'ping_success_count': ping_success_count,
        'ping_error_count': ping_error_count
    }

def main(folder_path):
    # Find all CSV files with 'summary' in the name in the specified directory
    summary_files = glob.glob(os.path.join(folder_path, '*summary*.csv'))

    results = {}
    if not summary_files:
        logger.warning(f"No summary CSV files found in the directory: {folder_path}")
    else:
        for file in summary_files:
            logger.info(f"Processing file: {file}")
            file_results = process_summary_csv(file)
            results[os.path.basename(file)] = file_results
            logger.info(f"Processed {file}")

    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process summary CSV files in a specified folder.")
    parser.add_argument("folder_path", help="Path to the folder containing summary CSV files")
    args = parser.parse_args()

    if not os.path.isdir(args.folder_path):
        logger.error(f"Error: The specified path is not a valid directory: {args.folder_path}")
        sys.exit(1)

    results = main(args.folder_path)
    print(results)