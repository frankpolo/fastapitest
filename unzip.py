import os
import zipfile
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def unzip_cellular_data(folder_path):
    """
    Unzips specific files from all ZIP files in the given folder.
    
    Args:
    folder_path (str): Path to the folder containing ZIP files
    
    Returns:
    str: Path to the folder where files were extracted
    """
    extract_folder = os.path.join(folder_path, "Extractedfiles")
    os.makedirs(extract_folder, exist_ok=True)
    
    # Updated regex patterns
    nrrf_pattern = re.compile(r'.*NR_RF.*\.csv$', re.IGNORECASE)
    summary_pattern = re.compile(r'.*Summary.*\.csv$', re.IGNORECASE)
    screenshots_pattern = re.compile(r'.*\.(jpg|png|jpeg)$', re.IGNORECASE)
    
    for filename in os.listdir(folder_path):
        if filename.endswith('.zip'):
            zip_path = os.path.join(folder_path, filename)
            
            # Extract all files to the Extractedfiles folder
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file in zip_ref.namelist():
                    if (nrrf_pattern.match(file) or 
                        summary_pattern.match(file) or 
                        screenshots_pattern.match(file)):
                        zip_ref.extract(file, extract_folder)
                        logger.info(f"Extracted: {file}")
            
            logger.info(f"Processed {filename}")
    
    logger.info("All files processed")
    return extract_folder

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
        extracted_folder = unzip_cellular_data(folder_path)
        print(f"Files extracted to: {extracted_folder}")
    else:
        print("Please provide the path to the folder containing ZIP files as an argument.")