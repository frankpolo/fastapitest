import csv
import os
import sys
import statistics
from collections import Counter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_csv(input_file, output_file):
    logger.info(f"Processing file: {input_file}")
    logger.info(f"Output file will be: {output_file}")

    required_headers = [
        "Date", "Time", "Latitude", "Longitude", "Call Event", "NR_PCell_Band",
        "NR_PCell_PCI", "NR_PCell_NR_ARFCN", "NR_PCell_SS-RSRP", "NR_PCell_SS-SINR", "NR_PCell_WB CQI",
        "NR_PCell_RI", "NR_PCell_DL MCS(Avg)", "NR_PCell_DL Num Layers",
        "NR_PCell_DL Num RBs", "NR_Total_PDSCH Tput(Mbps)",
        "NR_Total_PUSCH Tput(Mbps)", "NR_PCell_UL MCS(Avg)",
        "NR_PCell_DL Modulation", "NR_PCell_UL Modulation"
    ]

    try:
        with open(input_file, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            headers = reader.fieldnames

            if "Call Event" not in headers:
                logger.error(f"Error: 'Call Event' column not found in {input_file}")
                return None

            header_indices = {header: headers.index(header) for header in required_headers if header in headers}
            present_headers = [header for header in required_headers if header in header_indices]

            data = []
            iperf_dl_start = iperf_dl_end = iperf_ul_start = iperf_ul_end = None
            ookla_start = ookla_end = None
            iperf_dl_result = iperf_ul_result = ookla_result = ""
            dl_averages = {header: [] for header in present_headers[7:] if header in headers and header not in ["NR_PCell_DL Modulation", "NR_PCell_UL Modulation"]}
            ul_averages = {header: [] for header in present_headers[7:] if header in headers and header not in ["NR_PCell_DL Modulation", "NR_PCell_UL Modulation"]}
            ookla_averages = {header: [] for header in present_headers[7:] if header in headers and header not in ["NR_PCell_DL Modulation", "NR_PCell_UL Modulation"]}

            dl_pci_counter = Counter()
            dl_arfcn_counter = Counter()
            dl_mod_counter = Counter()

            ul_pci_counter = Counter()
            ul_arfcn_counter = Counter()
            ul_mod_counter = Counter()

            ookla_pci_counter = Counter()
            ookla_arfcn_counter = Counter()
            ookla_dl_mod_counter = Counter()
            ookla_ul_mod_counter = Counter()

            max_pdsch_tput = max_pusch_tput = max_ookla_dl_tput = max_ookla_ul_tput = 0

            dl_start_info = ul_start_info = ookla_start_info = None

            total_rows = 0
            iperf_dl_active = iperf_ul_active = ookla_active = False

            for row in reader:
                total_rows += 1
                call_events = row["Call Event"].split(";")
                for event in call_events:
                    new_row = [row.get(header, "") for header in present_headers]
                    new_row[present_headers.index("Call Event")] = event.strip()
                    new_row.append(str(len(call_events)))
                    data.append(new_row)

                    if "Iperf - UDP DL Start" in event:
                        iperf_dl_start = len(data) - 1
                        dl_start_info = (row["Date"], row["Time"], row["Latitude"], row["Longitude"], row["NR_PCell_PCI"], row["NR_PCell_NR_ARFCN"])
                        iperf_dl_active = True
                        iperf_ul_active = ookla_active = False
                    elif "Iperf - UDP UL Start" in event:
                        iperf_ul_start = len(data) - 1
                        ul_start_info = (row["Date"], row["Time"], row["Latitude"], row["Longitude"], row["NR_PCell_PCI"], row["NR_PCell_NR_ARFCN"])
                        iperf_ul_active = True
                        iperf_dl_active = ookla_active = False
                    elif "Speedtest - Session Start" in event:
                        ookla_start = len(data) - 1
                        ookla_start_info = (row["Date"], row["Time"], row["Latitude"], row["Longitude"], row["NR_PCell_PCI"], row["NR_PCell_NR_ARFCN"])
                        ookla_active = True
                        iperf_dl_active = iperf_ul_active = False
                    elif "Iperf - Complete" in event:
                        if iperf_dl_start is not None and iperf_dl_end is None:
                            iperf_dl_end = len(data) - 1
                        elif iperf_ul_start is not None and iperf_ul_end is None:
                            iperf_ul_end = len(data) - 1
                        iperf_dl_active = iperf_ul_active = False
                    elif "Speedtest - Complete" in event:
                        ookla_end = len(data) - 1
                        ookla_active = False

                    if iperf_dl_active:
                        if row.get("NR_PCell_PCI", "").strip():
                            dl_pci_counter[row["NR_PCell_PCI"]] += 1
                        if row.get("NR_PCell_NR_ARFCN", "").strip():
                            dl_arfcn_counter[row["NR_PCell_NR_ARFCN"]] += 1
                        if row.get("NR_PCell_DL Modulation", "").strip():
                            dl_mod_counter[row["NR_PCell_DL Modulation"]] += 1
                        try:
                            pdsch_tput = float(row["NR_Total_PDSCH Tput(Mbps)"])
                            max_pdsch_tput = max(max_pdsch_tput, pdsch_tput)
                        except (ValueError, KeyError):
                            pass
                    elif iperf_ul_active:
                        if row.get("NR_PCell_PCI", "").strip():
                            ul_pci_counter[row["NR_PCell_PCI"]] += 1
                        if row.get("NR_PCell_NR_ARFCN", "").strip():
                            ul_arfcn_counter[row["NR_PCell_NR_ARFCN"]] += 1
                        if row.get("NR_PCell_UL Modulation", "").strip():
                            ul_mod_counter[row["NR_PCell_UL Modulation"]] += 1
                        try:
                            pusch_tput = float(row["NR_Total_PUSCH Tput(Mbps)"])
                            max_pusch_tput = max(max_pusch_tput, pusch_tput)
                        except (ValueError, KeyError):
                            pass
                    elif ookla_active:
                        if row.get("NR_PCell_PCI", "").strip():
                            ookla_pci_counter[row["NR_PCell_PCI"]] += 1
                        if row.get("NR_PCell_NR_ARFCN", "").strip():
                            ookla_arfcn_counter[row["NR_PCell_NR_ARFCN"]] += 1
                        if row.get("NR_PCell_DL Modulation", "").strip():
                            ookla_dl_mod_counter[row["NR_PCell_DL Modulation"]] += 1
                        if row.get("NR_PCell_UL Modulation", "").strip():
                            ookla_ul_mod_counter[row["NR_PCell_UL Modulation"]] += 1
                        try:
                            ookla_dl_tput = float(row["NR_Total_PDSCH Tput(Mbps)"])
                            ookla_ul_tput = float(row["NR_Total_PUSCH Tput(Mbps)"])
                            max_ookla_dl_tput = max(max_ookla_dl_tput, ookla_dl_tput)
                            max_ookla_ul_tput = max(max_ookla_ul_tput, ookla_ul_tput)
                        except (ValueError, KeyError):
                            pass

                    if iperf_dl_start is not None and iperf_dl_end is None:
                        for header in dl_averages:
                            try:
                                value = float(row[header])
                                dl_averages[header].append(value)
                            except (ValueError, KeyError):
                                pass
                    elif iperf_ul_start is not None and iperf_ul_end is None:
                        for header in ul_averages:
                            try:
                                value = float(row[header])
                                ul_averages[header].append(value)
                            except (ValueError, KeyError):
                                pass
                    elif ookla_start is not None and ookla_end is None:
                        for header in ookla_averages:
                            try:
                                value = float(row[header])
                                ookla_averages[header].append(value)
                            except (ValueError, KeyError):
                                pass

            logger.info(f"Total rows processed: {total_rows}")

            # Check Iperf DL result
            if iperf_dl_start is not None and iperf_dl_end is not None:
                for i in range(iperf_dl_start, iperf_dl_end + 1):
                    if "Iperf - UDP DL Success" in data[i][present_headers.index("Call Event")]:
                        iperf_dl_result = "Success"
                        break
                    elif any(x in data[i][present_headers.index("Call Event")] for x in ["unable", "fail", "busy", "error"]):
                        iperf_dl_result = data[i][present_headers.index("Call Event")]
                        break
                if not iperf_dl_result:
                    iperf_dl_result = "Failure"

            # Check Iperf UL result
            if iperf_ul_start is not None and iperf_ul_end is not None:
                for i in range(iperf_ul_start, iperf_ul_end + 1):
                    if "Iperf - UDP UL Success" in data[i][present_headers.index("Call Event")]:
                        iperf_ul_result = "Success"
                        break
                    elif any(x in data[i][present_headers.index("Call Event")] for x in ["unable", "fail", "busy", "error"]):
                        iperf_ul_result = data[i][present_headers.index("Call Event")]
                        break
                if not iperf_ul_result:
                    iperf_ul_result = "Failure"

            # Check Ookla result
            if ookla_start is not None and ookla_end is not None:
                for i in range(ookla_start, ookla_end + 1):
                    if "Speedtest - Test Success" in data[i][present_headers.index("Call Event")]:
                        ookla_result = "Success"
                        break
                if not ookla_result:
                    ookla_result = "Failure"

            # Calculate final averages
            final_dl_averages = {header: statistics.mean(values) if values else 0 for header, values in dl_averages.items()}
            final_ul_averages = {header: statistics.mean(values) if values else 0 for header, values in ul_averages.items()}
            final_ookla_averages = {header: statistics.mean(values) if values else 0 for header, values in ookla_averages.items()}

            # Prepare distribution strings
            def prepare_dist_string(counter):
                total = sum(counter.values())
                return "; ".join([f"{key}: {count/total*100:.2f}%" for key, count in counter.most_common()])

            dl_pci_dist = prepare_dist_string(dl_pci_counter)
            dl_arfcn_dist = prepare_dist_string(dl_arfcn_counter)
            dl_mod_dist = prepare_dist_string(dl_mod_counter)

            ul_pci_dist = prepare_dist_string(ul_pci_counter)
            ul_arfcn_dist = prepare_dist_string(ul_arfcn_counter)
            ul_mod_dist = prepare_dist_string(ul_mod_counter)

            ookla_pci_dist = prepare_dist_string(ookla_pci_counter)
            ookla_arfcn_dist = prepare_dist_string(ookla_arfcn_counter)
            ookla_dl_mod_dist = prepare_dist_string(ookla_dl_mod_counter)
            ookla_ul_mod_dist = prepare_dist_string(ookla_ul_mod_counter)

            # Prepare key-value pairs
            kv_pairs = {
                "DL_Test": {
                    "Result": iperf_dl_result,
                    "Start_Date": dl_start_info[0] if dl_start_info else "",
                    "Start_Time": dl_start_info[1] if dl_start_info else "",
                    "Start_Latitude": dl_start_info[2] if dl_start_info else "",
                    "Start_Longitude": dl_start_info[3] if dl_start_info else "",
                    "Start_PCI": dl_start_info[4] if dl_start_info else "",
                    "Start_ARFCN": dl_start_info[5] if dl_start_info else "",
                    "PDSCH_Peak": f"{max_pdsch_tput:.2f}",
                    "PCI_Distribution": dl_pci_dist,
                    "ARFCN_Distribution": dl_arfcn_dist,
                    "Modulation_Distribution": dl_mod_dist,
                },
                "UL_Test": {
                    "Result": iperf_ul_result,
                    "Start_Date": ul_start_info[0] if ul_start_info else "",
                    "Start_Time": ul_start_info[1] if ul_start_info else "",
                    "Start_Latitude": ul_start_info[2] if ul_start_info else "",
                    "Start_Longitude": ul_start_info[3] if ul_start_info else "",
                    "Start_PCI": ul_start_info[4] if ul_start_info else "",
                    "Start_ARFCN": ul_start_info[5] if ul_start_info else "",
                    "PUSCH_Peak": f"{max_pusch_tput:.2f}",
                    "PCI_Distribution": ul_pci_dist,
                    "ARFCN_Distribution": ul_arfcn_dist,
                    "Modulation_Distribution": ul_mod_dist,
                },
                "Ookla_Test": {
                    "Result": ookla_result,
                    "Start_Date": ookla_start_info[0] if ookla_start_info else "",
                    "Start_Time": ookla_start_info[1] if ookla_start_info else "",
                    "Start_Latitude": ookla_start_info[2] if ookla_start_info else "",
                    "Start_Longitude": ookla_start_info[3] if ookla_start_info else "",
                    "Start_PCI": ookla_start_info[4] if ookla_start_info else "",
                    "Start_ARFCN": ookla_start_info[5] if ookla_start_info else "",
                    "Ookla_DL(Mbps)_Peak": f"{max_ookla_dl_tput:.2f}",
                    "Ookla_UL(Mbps)_Peak": f"{max_ookla_ul_tput:.2f}",
                    "PCI_Distribution": ookla_pci_dist,
                    "ARFCN_Distribution": ookla_arfcn_dist,
                    "DL_Modulation_Distribution": ookla_dl_mod_dist,
                    "UL_Modulation_Distribution": ookla_ul_mod_dist,
                }
            }

            for key, value in final_dl_averages.items():
                if key not in ["NR_PCell_DL Modulation", "NR_PCell_UL Modulation"]:
                    kv_pairs["DL_Test"][f"Avg_{key}"] = f"{value:.2f}"
            
            for key, value in final_ul_averages.items():
                if key not in ["NR_PCell_DL Modulation", "NR_PCell_UL Modulation"]:
                    kv_pairs["UL_Test"][f"Avg_{key}"] = f"{value:.2f}"
            
            for key, value in final_ookla_averages.items():
                if key not in ["NR_PCell_DL Modulation", "NR_PCell_UL Modulation"]:
                    kv_pairs["Ookla_Test"][f"Avg_{key}"] = f"{value:.2f}"

            return kv_pairs

    except Exception as e:
        logger.error(f"Error processing file {input_file}: {str(e)}")
        return None

def main(folder_path):
    if not os.path.isdir(folder_path):
        logger.error(f"Error: {folder_path} is not a valid directory")
        return {}

    logger.info(f"Searching for CSV files in: {folder_path}")
    csv_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.csv') and 'summary' not in f.lower()]
    logger.info(f"Found {len(csv_files)} CSV files (excluding summary files)")

    results = {}
    for filename in csv_files:
        input_file = os.path.join(folder_path, filename)
        output_file = f"{filename.split('_')[0]}_NR_RF.csv"
        output_path = os.path.join(folder_path, output_file)
        kv_pairs = process_csv(input_file, output_path)
        if kv_pairs:
            results[filename] = kv_pairs

    return results

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <folder_path>")
    else:
        folder_path = sys.argv[1]
        results = main(folder_path)
        print(results)