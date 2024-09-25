import logging
import os
import shutil
import tempfile
import csv
import io
import json
import traceback
import re
from datetime import datetime
from typing import List, Optional, Dict, Union
from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, UniqueConstraint, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import IntegrityError

import pandas as pd

from unzip import unzip_cellular_data
from summary import process_summary_csv
from nrrf4 import process_csv as process_nrrf_csv

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Cellular Data Processing API",
    description="API for processing and managing cellular network test data",
    version="1.0.0",
    docs_url=None,  # Disable the default docs
    redoc_url=None,  # Disable the default redoc
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup for static files and templates
current_dir = os.path.dirname(os.path.realpath(__file__))
static_dir = os.path.join(current_dir, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates_dir = os.path.join(current_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)

FINAL_FOLDER = r"D:\tws\final"

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database models
class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    summary_results = Column(JSON)
    dl_test_results = Column(JSON)
    ul_test_results = Column(JSON)
    ookla_test_results = Column(JSON)
    evaluation_results = Column(JSON)

class Site(Base):
    __tablename__ = "sites"

    id = Column(Integer, primary_key=True, index=True)
    siteid_sectorid = Column(String, unique=True, index=True)
    market = Column(String)
    site_name = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    criteria = Column(String)
    criteria_value = Column(String)

class Criteria(Base):
    __tablename__ = "criteria"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String)
    value = Column(String)
    kpi_name = Column(String)
    pass_condition = Column(String)
    pass_value = Column(Float)
    conditional_pass_condition = Column(String)
    conditional_pass_value = Column(Float)
    unit = Column(String)

    UniqueConstraint('type', 'value', 'kpi_name', name='uix_1')

Base.metadata.create_all(bind=engine)

# Pydantic models
class SiteCreate(BaseModel):
    siteid_sectorid: str
    market: str
    site_name: str
    latitude: float
    longitude: float
    criteria: str
    criteria_value: str

class SiteUpdate(BaseModel):
    market: Optional[str] = None
    site_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    criteria: Optional[str] = None
    criteria_value: Optional[str] = None

class SiteResponse(SiteCreate):
    id: int

class CriteriaCreate(BaseModel):
    type: str
    value: str
    kpi_name: str
    pass_condition: str
    pass_value: float
    conditional_pass_condition: str
    conditional_pass_value: float
    unit: str

class CriteriaUpdate(BaseModel):
    type: Optional[str] = None
    value: Optional[str] = None
    kpi_name: Optional[str] = None
    pass_condition: Optional[str] = None
    pass_value: Optional[float] = None
    conditional_pass_condition: Optional[str] = None
    conditional_pass_value: Optional[float] = None
    unit: Optional[str] = None

class CriteriaResponse(CriteriaCreate):
    id: int

class TimeSeriesData(BaseModel):
    data: List[Dict]
    time_range: Dict[str, str]

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility functions
def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

def rename_file(filename):
    match = re.match(r'.*?(\d+-\d+).*', filename)
    if match:
        if 'Summary' in filename:
            return f"{match.group(1)}_Summary.csv"
        elif 'NR_RF' in filename:
            return f"{match.group(1)}_NR_RF.csv"
    return filename

def get_numeric_id(filename):
    match = re.match(r'.*?(\d+-\d+).*', filename)
    if match:
        return match.group(1)
    return filename

# Data processing functions
def append_to_sqlite(data):
    try:
        db = SessionLocal()
        timestamp = datetime.now()
        for filename, file_results in data['results'].items():
            existing_result = db.query(TestResult).filter(TestResult.filename == filename).first()
            
            if existing_result:
                new_result = existing_result
            else:
                new_result = TestResult(filename=filename)
            
            new_result.timestamp = timestamp
            new_result.summary_results = file_results.get('summary_results', {}).get(filename, {})
            
            nrrf_results = file_results.get('nrrf_results', {}).get(filename, {})
            new_result.dl_test_results = nrrf_results.get('DL_Test', {})
            new_result.ul_test_results = nrrf_results.get('UL_Test', {})
            new_result.ookla_test_results = nrrf_results.get('Ookla_Test', {})
            new_result.evaluation_results = nrrf_results.get('evaluation', [])
            
            if not existing_result:
                db.add(new_result)
        
        db.commit()
        logger.info("Data successfully appended to SQLite")
        return True
    except IntegrityError as e:
        logger.error(f"IntegrityError while appending to SQLite: {str(e)}")
        db.rollback()
        return False
    except Exception as e:
        logger.error(f"Error appending to SQLite: {str(e)}")
        logger.error(traceback.format_exc())
        db.rollback()
        return False
    finally:
        db.close()

async def process_zip_file(zip_file: UploadFile, db: Session):
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, zip_file.filename)
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(zip_file.file, buffer)
        
        try:
            extracted_folder = unzip_cellular_data(temp_dir)
            
            summary_results = {}
            nrrf_results = {}
            
            for file in os.listdir(extracted_folder):
                file_path = os.path.join(extracted_folder, file)
                if 'summary' in file.lower():
                    summary_results[file] = process_summary_csv(file_path)
                elif 'nr_rf' in file.lower():
                    nrrf_results[file] = process_nrrf_csv(file_path, file_path)
            
            ensure_dir(FINAL_FOLDER)
            
            for file in os.listdir(extracted_folder):
                src = os.path.join(extracted_folder, file)
                if 'summary' in file.lower() or file.endswith('_NR_RF.csv'):
                    new_name = rename_file(file)
                    dst = os.path.join(FINAL_FOLDER, new_name)
                    shutil.move(src, dst)
                    logger.info(f"Moved and renamed file: {file} to {new_name}")
                elif file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    screenshots_folder = os.path.join(FINAL_FOLDER, "Screenshots")
                    ensure_dir(screenshots_folder)
                    dst = os.path.join(screenshots_folder, file)
                    shutil.copy2(src, dst)
                    logger.info(f"Copied screenshot: {file}")
            
            renamed_summary_results = {get_numeric_id(k): v for k, v in summary_results.items()}
            renamed_nrrf_results = {get_numeric_id(k): v for k, v in nrrf_results.items()}

            results = {
                "summary_results": renamed_summary_results,
                "nrrf_results": renamed_nrrf_results
            }

            # Evaluate results against criteria
            for filename, file_results in results['nrrf_results'].items():
                site = db.query(Site).filter(Site.siteid_sectorid == filename).first()
                if site:
                    logger.debug(f"Found site for filename {filename}: {site.siteid_sectorid}")
                    criteria_list = db.query(Criteria).filter(
                        Criteria.type == site.criteria,
                        Criteria.value == site.criteria_value
                    ).all()
                    logger.debug(f"Criteria for site {filename}: {[c.kpi_name for c in criteria_list]}")
                    
                    evaluation_results = []
                    summary_data = results['summary_results'].get(filename, {})
                    dl_test_data = file_results.get('DL_Test', {})
                    ul_test_data = file_results.get('UL_Test', {})
                    ookla_test_data = file_results.get('Ookla_Test', {})

                    logger.debug(f"Summary data for {filename}: {summary_data}")
                    logger.debug(f"DL test data for {filename}: {dl_test_data}")
                    logger.debug(f"UL test data for {filename}: {ul_test_data}")
                    logger.debug(f"Ookla test data for {filename}: {ookla_test_data}")

                    kpi_data = {
                        'PDSCH_Peak': dl_test_data.get('PDSCH_Peak'),
                        'PUSCH_Peak': ul_test_data.get('PUSCH_Peak'),
                        'Ping _avg': summary_data.get('ping_avg'),
                        'Ookla_DL(Mbps)': ookla_test_data.get('Ookla_DL(Mbps)_Peak'),
                        'Ookla_UL(Mbps)': ookla_test_data.get('Ookla_UL(Mbps)_Peak'),
                        'Attach_Successrate': (float(summary_data.get('attachcomplete_count', 0)) / float(summary_data.get('attachrequest_count', 1))) * 100 if float(summary_data.get('attachrequest_count', 0)) > 0 else 0,
                        'PDSCH_Avg': dl_test_data.get('Avg_NR_Total_PDSCH Tput(Mbps)'),
                        'PUSCH_Avg': ul_test_data.get('Avg_NR_Total_PUSCH Tput(Mbps)')
                    }

                    logger.debug(f"KPI data for {filename}: {kpi_data}")

                    for criterion in criteria_list:
                        logger.debug(f"Evaluating criterion: {criterion.kpi_name}")
                        if criterion.kpi_name in kpi_data:
                            value = kpi_data[criterion.kpi_name]
                            logger.debug(f"Value for {criterion.kpi_name}: {value}")
                            try:
                                result = float(value) if value is not None else None
                                status = evaluate_criterion(criterion, result)
                                evaluation_results.append({
                                    "kpi_name": criterion.kpi_name,
                                    "result": result,
                                    "status": status,
                                    "pass_value": criterion.pass_value,
                                    "conditional_pass_value": criterion.conditional_pass_value,
                                    "unit": criterion.unit
                                })
                            except (ValueError, TypeError) as e:
                                logger.error(f"Error converting {value} to float for {criterion.kpi_name}: {str(e)}")
                                evaluation_results.append({
                                    "kpi_name": criterion.kpi_name,
                                    "result": value,
                                    "status": "Error",
                                    "pass_value": criterion.pass_value,
                                    "conditional_pass_value": criterion.conditional_pass_value,
                                    "unit": criterion.unit
                                })
                        else:
                            logger.warning(f"KPI {criterion.kpi_name} not found in data")
                            evaluation_results.append({
                                "kpi_name": criterion.kpi_name,
                                "result": None,
                                "status": "No data",
                                "pass_value": criterion.pass_value,
                                "conditional_pass_value": criterion.conditional_pass_value,
                                "unit": criterion.unit
                            })
                    
                    results['nrrf_results'][filename]['evaluation'] = evaluation_results
                else:
                    logger.warning(f"No site found for {filename}")
                    results['nrrf_results'][filename]['evaluation'] = [{"error": "No site found in database"}]

            return results

        except Exception as e:
            logger.error(f"Error processing {zip_file.filename}: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Error processing {zip_file.filename}: {str(e)}")

def evaluate_criterion(criterion: Criteria, value: Optional[float]) -> str:
    if value is None:
        return "No data"
    try:
        if compare_values(value, criterion.pass_condition, criterion.pass_value):
            return "Pass"
        elif compare_values(value, criterion.conditional_pass_condition, criterion.conditional_pass_value):
            return "Conditional Pass"
        else:
            return "Fail"
    except ValueError as e:
        logger.error(f"Error evaluating criterion: {str(e)}")
        return "Error"

def compare_values(value: float, condition: str, threshold: float) -> bool:
    if condition == ">=":
        return value >= threshold
    elif condition == "<=":
        return value <= threshold
    elif condition == ">":
        return value > threshold
    elif condition == "<":
        return value < threshold
    else:
        raise ValueError(f"Unknown comparison condition: {condition}")

# API Endpoints
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Render the main page of the application.
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/edit_sitelist", response_class=HTMLResponse)
async def edit_sitelist(request: Request):
    """
    Render the edit site list page of the application.
    """
    return templates.TemplateResponse("EditSiteList.html", {"request": request})

@app.get("/edit_criteria", response_class=HTMLResponse)
async def edit_criteria(request: Request):
    """
    Render the edit criteria page of the application.
    """
    return templates.TemplateResponse("EditCriteria.html", {"request": request})

@app.post("/process_zip/")
async def process_zip(files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    """
    Process uploaded ZIP files containing cellular network test data.

    - **files**: One or more ZIP files containing test data
    - Returns a summary of processed files, any errors encountered, and evaluation results
    """
    logger.info(f"Received request to process files")
    logger.info(f"Files received: {[file.filename for file in files]}")
    
    processed_files = []
    errors = []
    results = {}

    if not files:
        logger.warning("No files were uploaded")
        raise HTTPException(status_code=400, detail="No files were uploaded")

    for file in files:
        logger.info(f"Processing file: {file.filename}")
        if file.filename.endswith('.zip'):
            try:
                file_results = await process_zip_file(file, db)
                numeric_id = get_numeric_id(file.filename)
                processed_files.append(numeric_id)
                results[numeric_id] = file_results
                logger.info(f"Successfully processed file: {file.filename}")
            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {str(e)}")
                logger.error(traceback.format_exc())
                errors.append({"file": file.filename, "error": str(e)})
        else:
            logger.warning(f"Skipped non-ZIP file: {file.filename}")
            errors.append({"file": file.filename, "error": "Not a ZIP file"})

    response_data = {
        "message": "All files processed successfully" if not errors else "Some files could not be processed",
        "processed": processed_files,
        "errors": errors,
        "results": results
    }

    # Append to SQLite
    sqlite_saved = append_to_sqlite(response_data)
    if sqlite_saved:
        response_data["sqlite_status"] = "Data successfully saved to SQLite"
    else:
        response_data["sqlite_status"] = "Failed to save data to SQLite"
        logger.error("Failed to save data to SQLite. Check logs for details.")

    status_code = 200 if not errors else 207  # Multi-Status
    return JSONResponse(content=response_data, status_code=status_code)

@app.post("/sites/upload")
async def upload_sites(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a CSV file containing site information.

    - **file**: A CSV file with site data
    - Returns a summary of the upload process, including the number of sites added or updated
    """
    logger.info(f"Received request to upload sites CSV: {file.filename}")
    if not file.filename.endswith('.csv'):
        logger.error(f"Invalid file type: {file.filename}")
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    content = await file.read()
    csv_reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
    
    added_count = 0
    updated_count = 0
    error_count = 0
    for row in csv_reader:
        try:
            existing_site = db.query(Site).filter(Site.siteid_sectorid == row['siteid_sectorid']).first()
            if existing_site:
                # Update existing site
                for key, value in row.items():
                    setattr(existing_site, key, value)
                updated_count += 1
                logger.info(f"Updated site: {existing_site.siteid_sectorid}")
            else:
                # Add new site
                new_site = Site(**row)
                db.add(new_site)
                added_count += 1
                logger.info(f"Added new site: {new_site.siteid_sectorid}")
            db.commit()
        except Exception as e:
            logger.error(f"Error processing row: {row}. Error: {str(e)}")
            db.rollback()
            error_count += 1
    
    logger.info(f"Sites upload completed. Added: {added_count}, Updated: {updated_count}, Errors: {error_count}")
    return {"message": f"{added_count} sites added, {updated_count} sites updated successfully", "errors": error_count}

@app.get("/sites", response_model=List[SiteResponse])
async def read_sites(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieve a list of sites.

    - **skip**: Number of sites to skip (for pagination)
    - **limit**: Maximum number of sites to return
    - Returns a list of sites
    """
    sites = db.query(Site).offset(skip).limit(limit).all()
    return sites

@app.get("/site/{siteid_sectorid}", response_model=SiteResponse)
async def read_site(siteid_sectorid: str, db: Session = Depends(get_db)):
    site = db.query(Site).filter(Site.siteid_sectorid == siteid_sectorid).first()
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return site

@app.put("/site/{siteid_sectorid}", response_model=SiteResponse)
async def update_site(siteid_sectorid: str, site_update: SiteUpdate, db: Session = Depends(get_db)):
    db_site = db.query(Site).filter(Site.siteid_sectorid == siteid_sectorid).first()
    if db_site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    
    for key, value in site_update.dict(exclude_unset=True).items():
        setattr(db_site, key, value)
    
    try:
        db.commit()
        db.refresh(db_site)
        logger.info(f"Updated site: {siteid_sectorid}")
    except IntegrityError:
        db.rollback()
        logger.error(f"Update failed for site: {siteid_sectorid}")
        raise HTTPException(status_code=400, detail="Update failed due to integrity constraint")
    
    return db_site

@app.delete("/site/{siteid_sectorid}")
async def delete_site(siteid_sectorid: str, db: Session = Depends(get_db)):
    db_site = db.query(Site).filter(Site.siteid_sectorid == siteid_sectorid).first()
    if db_site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    
    db.delete(db_site)
    db.commit()
    logger.info(f"Deleted site: {siteid_sectorid}")
    
    return {"message": f"Site {siteid_sectorid} deleted successfully"}

@app.post("/criteria/upload")
async def upload_criteria(file: UploadFile = File(...), db: Session = Depends(get_db)):
    logger.info(f"Received request to upload criteria CSV: {file.filename}")
    if not file.filename.endswith('.csv'):
        logger.error(f"Invalid file type: {file.filename}")
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    content = await file.read()
    csv_reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
    
    added_count = 0
    updated_count = 0
    error_count = 0
    for row in csv_reader:
        try:
            existing_criteria = db.query(Criteria).filter(
                Criteria.type == row['type'],
                Criteria.value == row['value'],
                Criteria.kpi_name == row['kpi_name']
            ).first()
            if existing_criteria:
                # Update existing criteria
                for key, value in row.items():
                    setattr(existing_criteria, key, value)
                updated_count += 1
                logger.info(f"Updated criteria: {existing_criteria.type} - {existing_criteria.kpi_name}")
            else:
                # Add new criteria
                new_criteria = Criteria(**row)
                db.add(new_criteria)
                added_count += 1
                logger.info(f"Added new criteria: {new_criteria.type} - {new_criteria.kpi_name}")
            db.commit()
        except Exception as e:
            logger.error(f"Error processing row: {row}. Error: {str(e)}")
            db.rollback()
            error_count += 1
    
    logger.info(f"Criteria upload completed. Added: {added_count}, Updated: {updated_count}, Errors: {error_count}")
    return {"message": f"{added_count} criteria added, {updated_count} criteria updated successfully", "errors": error_count}

@app.get("/criteria", response_model=List[CriteriaResponse])
async def read_criteria(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    criteria = db.query(Criteria).offset(skip).limit(limit).all()
    return criteria

@app.get("/criteria/{id}", response_model=CriteriaResponse)
async def read_criteria_by_id(id: int, db: Session = Depends(get_db)):
    criteria = db.query(Criteria).filter(Criteria.id == id).first()
    if criteria is None:
        raise HTTPException(status_code=404, detail="Criteria not found")
    return criteria

@app.put("/criteria/{id}", response_model=CriteriaResponse)
async def update_criteria(id: int, criteria_update: CriteriaUpdate, db: Session = Depends(get_db)):
    db_criteria = db.query(Criteria).filter(Criteria.id == id).first()
    if db_criteria is None:
        raise HTTPException(status_code=404, detail="Criteria not found")
    
    update_data = criteria_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_criteria, key, value)
    
    try:
        db.commit()
        db.refresh(db_criteria)
        logger.info(f"Updated criteria: {id}")
    except IntegrityError:
        db.rollback()
        logger.error(f"Update failed for criteria: {id}")
        raise HTTPException(status_code=400, detail="Update failed due to integrity constraint")
    
    return db_criteria

@app.delete("/criteria/{id}")
async def delete_criteria(id: int, db: Session = Depends(get_db)):
    db_criteria = db.query(Criteria).filter(Criteria.id == id).first()
    if db_criteria is None:
        raise HTTPException(status_code=404, detail="Criteria not found")
    
    db.delete(db_criteria)
    db.commit()
    logger.info(f"Deleted criteria: {id}")
    
    return {"message": f"Criteria {id} deleted successfully"}

@app.get("/test_results")
async def get_test_results(db: Session = Depends(get_db)):
    results = db.query(TestResult).all()
    return [
        {
            "id": result.id,
            "filename": result.filename,
            "timestamp": result.timestamp,
            "summary_results": result.summary_results,
            "dl_test_results": result.dl_test_results,
            "ul_test_results": result.ul_test_results,
            "ookla_test_results": result.ookla_test_results,
            "evaluation_results": result.evaluation_results
        }
        for result in results
    ]

@app.get("/test_results/{filename}")
async def get_test_result(filename: str, db: Session = Depends(get_db)):
    result = db.query(TestResult).filter(TestResult.filename == filename).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Test result not found")
    return {
        "id": result.id,
        "filename": result.filename,
        "timestamp": result.timestamp,
        "summary_results": result.summary_results,
        "dl_test_results": result.dl_test_results,
        "ul_test_results": result.ul_test_results,
        "ookla_test_results": result.ookla_test_results,
        "evaluation_results": result.evaluation_results
    }

@app.delete("/test_results/{filename}")
async def delete_test_result(filename: str, db: Session = Depends(get_db)):
    result = db.query(TestResult).filter(TestResult.filename == filename).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Test result not found")
    
    db.delete(result)
    db.commit()
    logger.info(f"Deleted test result: {filename}")
    
    return {"message": f"Test result {filename} deleted successfully"}

@app.get("/api/timeseries/{filename}", response_model=TimeSeriesData)
async def get_timeseries_data(filename: str):
    file_path = os.path.join(FINAL_FOLDER, f"{filename}_NR_RF.csv")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="CSV file not found")

    df = pd.read_csv(file_path)

    # Find the timestamp column (assuming it contains 'time' in its name)
    timestamp_column = next((col for col in df.columns if 'time' in col.lower()), None)
    if timestamp_column:
        # Convert the timestamp column to datetime
        df[timestamp_column] = pd.to_datetime(df[timestamp_column], format="%H:%M:%S.%f")
    else:
        raise HTTPException(status_code=400, detail="Timestamp column not found in the CSV file")

    desired_kpis = [
        "NR_PCELL_PCI",
        "NR_PCell_PDSCH Tput(Mbps)",
        "NR_PCell_SS-RSRP",
        "NR_PCell_SS-SINR",
        "NR_PCell_WB CQI",
        "NR_PCell_DL MCS(Avg)",
        "NR_PCell_DL Modulation"
    ]

    available_kpis = [col for col in df.columns if any(kpi.lower() in col.lower() for kpi in desired_kpis)]
    
    if not available_kpis:
        raise HTTPException(status_code=400, detail="No matching KPI columns found in the CSV file")
    
    traces = []
    for kpi in available_kpis:
        valid_data = df[[timestamp_column, kpi]].dropna()
        
        traces.append({
            "x": valid_data[timestamp_column].dt.strftime('%H:%M:%S.%f').tolist(),
            "y": valid_data[kpi].tolist(),
            "name": kpi
        })
    
    time_range = {
        "start": df[timestamp_column].min().strftime('%H:%M:%S.%f'),
        "end": df[timestamp_column].max().strftime('%H:%M:%S.%f')
    }
    
    return TimeSeriesData(data=traces, time_range=time_range)

@app.get("/plot/{filename}", response_class=HTMLResponse)
async def get_plot(request: Request, filename: str):
    """
    Render the plot page for a specific filename.
    """
    return templates.TemplateResponse("plot.html", {"request": request, "filename": filename})

# Swagger UI
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Cellular Data Processing API - Swagger UI",
        oauth2_redirect_url="/docs/oauth2-redirect",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )

@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    return JSONResponse(get_openapi(title="Cellular Data Processing API", version="1.0.0", routes=app.routes))

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI application...")
    logger.info(f"Templates directory: {templates_dir}")
    logger.info(f"Static files directory: {static_dir}")
    uvicorn.run(app, host="0.0.0.0", port=8000)