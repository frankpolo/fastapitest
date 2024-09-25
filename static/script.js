document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded and parsed');
    
    setupDropzone('zipDropzone', 'zipFile');
    setupForm('zipForm', 'zipFile', '/process_zip/', uploadZIP);

    // Load test results on the main page
    if (document.getElementById('testResults')) {
        loadTestResults();
    }

    // Load and setup sitelist page
    if (document.getElementById('siteList')) {
        setupDropzone('siteDropzone', 'siteFile');
        setupForm('siteForm', 'siteFile', '/sites/upload', uploadCSV);
        loadSites();
    }

    // Load and setup criteria page
    if (document.getElementById('criteriaList')) {
        setupDropzone('criteriaDropzone', 'criteriaFile');
        setupForm('criteriaForm', 'criteriaFile', '/criteria/upload', uploadCSV);
        loadCriteria();
    }

    // Set up event listeners for edit forms
    if (document.getElementById('editSiteForm')) {
        document.getElementById('editSiteForm').addEventListener('submit', function(e) {
            e.preventDefault();
            updateSite();
        });
    }

    if (document.getElementById('editCriteriaForm')) {
        document.getElementById('editCriteriaForm').addEventListener('submit', function(e) {
            e.preventDefault();
            updateCriteria();
        });
    }
});

function setupDropzone(dropzoneId, fileInputId) {
    const dropzone = document.getElementById(dropzoneId);
    const fileInput = document.getElementById(fileInputId);

    if (!dropzone || !fileInput) {
        console.error(`Dropzone or file input not found: ${dropzoneId}, ${fileInputId}`);
        return;
    }

    dropzone.onclick = () => fileInput.click();

    fileInput.onchange = () => {
        if (fileInput.files.length > 0) {
            dropzone.textContent = `Selected: ${Array.from(fileInput.files).map(f => f.name).join(', ')}`;
        }
    };

    dropzone.ondragover = (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    };

    dropzone.ondragleave = () => {
        dropzone.classList.remove('dragover');
    };

    dropzone.ondrop = (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        fileInput.files = e.dataTransfer.files;
        if (fileInput.files.length > 0) {
            dropzone.textContent = `Selected: ${Array.from(fileInput.files).map(f => f.name).join(', ')}`;
        }
    };
}

function setupForm(formId, fileInputId, uploadUrl, uploadFunction) {
    const form = document.getElementById(formId);
    
    if (!form) {
        console.error(`Form not found: ${formId}`);
        return;
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        uploadFunction(uploadUrl, formId, fileInputId);
    });
}

function uploadZIP(url, formId, fileInputId) {
    const fileInput = document.getElementById(fileInputId);
    const statusElement = document.getElementById(`${formId.replace('Form', '')}Status`);
    const files = fileInput.files;

    if (!files || files.length === 0) {
        showStatus(statusElement, 'Please select files to upload.', 'error');
        return;
    }

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }

    uploadFile(url, formData, statusElement);
}

function uploadCSV(url, formId, fileInputId) {
    const fileInput = document.getElementById(fileInputId);
    const statusElement = document.getElementById(`${formId.replace('Form', '')}Status`);
    const file = fileInput.files[0];

    if (!file) {
        showStatus(statusElement, 'Please select a file to upload.', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    uploadFile(url, formData, statusElement);
}

function uploadFile(url, formData, statusElement) {
    showStatus(statusElement, 'Processing...', 'processing');

    fetch(url, {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => {
                throw new Error(`HTTP error! status: ${response.status}, message: ${text}`);
            });
        }
        return response.json();
    })
    .then(data => {
        showStatus(statusElement, 'Upload successful', 'success');
        console.log('Upload successful:', data);
        showResult(JSON.stringify(data, null, 2));
        if (url.includes('sites')) {
            loadSites();
        } else if (url.includes('criteria')) {
            loadCriteria();
        } else if (url.includes('process_zip')) {
            loadTestResults();
        }
    })
    .catch(error => {
        console.error('Upload error:', error);
        showStatus(statusElement, `Error: ${error.message}`, 'error');
    });
}

function showStatus(element, message, type) {
    if (!element) {
        console.error('Status element not found');
        return;
    }
    element.textContent = message;
    element.className = `status ${type}`;
}

function showResult(message) {
    const resultDiv = document.getElementById('processingResults');
    if (!resultDiv) {
        console.error('Results div not found');
        return;
    }
    resultDiv.textContent = message;
}

function loadTestResults() {
    fetch('/test_results')
        .then(response => response.json())
        .then(results => {
            const tableBody = document.getElementById('testResultsTableBody');
            tableBody.innerHTML = '';
            results.forEach(result => {
                const row = `
                    <tr>
                        <td>${result.filename}</td>
                        <td>${result.timestamp}</td>
                        <td>
                            <button onclick="viewTestResult('${result.filename}')">View Details</button>
                            <button onclick="openPlotPage('${result.filename}')">View Plots</button>
                            <button onclick="deleteTestResult('${result.filename}')">Delete</button>
                        </td>
                    </tr>
                `;
                tableBody.innerHTML += row;
            });
        })
        .catch(error => console.error('Error loading test results:', error));
}

function loadSites() {
    fetch('/sites')
        .then(response => response.json())
        .then(sites => {
            const tableBody = document.getElementById('sitesTableBody');
            tableBody.innerHTML = '';
            sites.forEach(site => {
                const row = `
                    <tr>
                        <td>${site.siteid_sectorid}</td>
                        <td>${site.market}</td>
                        <td>${site.site_name}</td>
                        <td>${site.latitude}</td>
                        <td>${site.longitude}</td>
                        <td>${site.criteria}</td>
                        <td>${site.criteria_value}</td>
                        <td>
                            <button onclick="editSite('${site.siteid_sectorid}')">Edit</button>
                            <button onclick="deleteSite('${site.siteid_sectorid}')">Delete</button>
                        </td>
                    </tr>
                `;
                tableBody.innerHTML += row;
            });
        })
        .catch(error => console.error('Error loading sites:', error));
}

function loadCriteria() {
    fetch('/criteria')
        .then(response => response.json())
        .then(criteriaList => {
            const tableBody = document.getElementById('criteriaTableBody');
            tableBody.innerHTML = '';
            criteriaList.forEach(criteria => {
                const row = `
                    <tr>
                        <td>${criteria.type}</td>
                        <td>${criteria.value}</td>
                        <td>${criteria.kpi_name}</td>
                        <td>${criteria.pass_condition}</td>
                        <td>${criteria.pass_value}</td>
                        <td>${criteria.conditional_pass_condition}</td>
                        <td>${criteria.conditional_pass_value}</td>
                        <td>${criteria.unit}</td>
                        <td>
                            <button onclick="editCriteria(${criteria.id})">Edit</button>
                            <button onclick="deleteCriteria(${criteria.id})">Delete</button>
                        </td>
                    </tr>
                `;
                tableBody.innerHTML += row;
            });
        })
        .catch(error => console.error('Error loading criteria:', error));
}

function viewTestResult(filename) {
    fetch(`/test_results/${filename}`)
        .then(response => response.json())
        .then(result => {
            const detailsDiv = document.getElementById('testResultDetails');
            detailsDiv.innerHTML = `
                <h3>Test Result Details for ${result.filename}</h3>
                <p>Timestamp: ${result.timestamp}</p>
                <h4>Summary Results</h4>
                <pre>${JSON.stringify(result.summary_results, null, 2)}</pre>
                <h4>DL Test Results</h4>
                <pre>${JSON.stringify(result.dl_test_results, null, 2)}</pre>
                <h4>UL Test Results</h4>
                <pre>${JSON.stringify(result.ul_test_results, null, 2)}</pre>
                <h4>Ookla Test Results</h4>
                <pre>${JSON.stringify(result.ookla_test_results, null, 2)}</pre>
                <h4>Evaluation Results</h4>
                <pre>${JSON.stringify(result.evaluation_results, null, 2)}</pre>
            `;
            document.getElementById('testResultModal').style.display = 'block';
        })
        .catch(error => console.error('Error fetching test result details:', error));
}

function deleteTestResult(filename) {
    if (confirm('Are you sure you want to delete this test result?')) {
        fetch(`/test_results/${filename}`, { method: 'DELETE' })
            .then(response => response.json())
            .then(data => {
                console.log('Test result deleted:', data);
                loadTestResults();
            })
            .catch(error => console.error('Error deleting test result:', error));
    }
}

function openPlotPage(filename) {
    window.open(`/plot/${filename}`, '_blank');
}

function editSite(siteid_sectorid) {
    fetch(`/site/${siteid_sectorid}`)
        .then(response => response.json())
        .then(site => {
            document.getElementById('editSiteId').value = site.siteid_sectorid;
            document.getElementById('editMarket').value = site.market;
            document.getElementById('editSiteName').value = site.site_name;
            document.getElementById('editLatitude').value = site.latitude;
            document.getElementById('editLongitude').value = site.longitude;
            document.getElementById('editCriteria').value = site.criteria;
            document.getElementById('editCriteriaValue').value = site.criteria_value;
            
            document.getElementById('editSiteModal').style.display = 'block';
        })
        .catch(error => console.error('Error fetching site details:', error));
}

function updateSite() {
    const siteid_sectorid = document.getElementById('editSiteId').value;
    const updatedSite = {
        market: document.getElementById('editMarket').value,
        site_name: document.getElementById('editSiteName').value,
        latitude: parseFloat(document.getElementById('editLatitude').value),
        longitude: parseFloat(document.getElementById('editLongitude').value),
        criteria: document.getElementById('editCriteria').value,
        criteria_value: document.getElementById('editCriteriaValue').value
    };

    fetch(`/site/${siteid_sectorid}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(updatedSite),
    })
    .then(response => response.json())
    .then(data => {
        console.log('Success:', data);
        document.getElementById('editSiteModal').style.display = 'none';
        loadSites();
    })
    .catch((error) => {
        console.error('Error:', error);
    });
}

function deleteSite(siteid_sectorid) {
    if (confirm('Are you sure you want to delete this site?')) {
        fetch(`/site/${siteid_sectorid}`, { method: 'DELETE' })
            .then(response => response.json())
            .then(data => {
                console.log('Site deleted:', data);
                loadSites();
            })
            .catch(error => console.error('Error deleting site:', error));
    }
}

function editCriteria(id) {
    fetch(`/criteria/${id}`)
        .then(response => response.json())
        .then(criteria => {
            document.getElementById('editCriteriaId').value = criteria.id;
            document.getElementById('editType').value = criteria.type;
            document.getElementById('editValue').value = criteria.value;
            document.getElementById('editKpiName').value = criteria.kpi_name;
            document.getElementById('editPassCondition').value = criteria.pass_condition;
            document.getElementById('editPassValue').value = criteria.pass_value;
            document.getElementById('editConditionalPassCondition').value = criteria.conditional_pass_condition;
            document.getElementById('editConditionalPassValue').value = criteria.conditional_pass_value;
            document.getElementById('editUnit').value = criteria.unit;
            
            document.getElementById('editCriteriaModal').style.display = 'block';
        })
        .catch(error => console.error('Error fetching criteria details:', error));
}

function updateCriteria() {
    const id = document.getElementById('editCriteriaId').value;
    const updatedCriteria = {
        type: document.getElementById('editType').value,
        value: document.getElementById('editValue').value,
        kpi_name: document.getElementById('editKpiName').value,
        pass_condition: document.getElementById('editPassCondition').value,
        pass_value: parseFloat(document.getElementById('editPassValue').value),
        conditional_pass_condition: document.getElementById('editConditionalPassCondition').value,
        conditional_pass_value: parseFloat(document.getElementById('editConditionalPassValue').value),
        unit: document.getElementById('editUnit').value
    };

    fetch(`/criteria/${id}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(updatedCriteria),
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw err; });
        }
        return response.json();
    })
    .then(data => {
        console.log('Success:', data);
        document.getElementById('editCriteriaModal').style.display = 'none';
        loadCriteria();
    })
    .catch((error) => {
        console.error('Error:', error);
        alert('Failed to update criteria: ' + (error.detail || error.message || 'Unknown error'));
    });
}

function deleteCriteria(id) {
    if (confirm('Are you sure you want to delete this criteria?')) {
        fetch(`/criteria/${id}`, { method: 'DELETE' })
            .then(response => response.json())
            .then(data => {
                console.log('Criteria deleted:', data);
                loadCriteria();
            })
            .catch(error => console.error('Error deleting criteria:', error));
    }
}

// Close modal functions
function closeTestResultModal() {
    document.getElementById('testResultModal').style.display = 'none';
}

function closeEditSiteModal() {
    document.getElementById('editSiteModal').style.display = 'none';
}

function closeEditCriteriaModal() {
    document.getElementById('editCriteriaModal').style.display = 'none';
}

// When the user clicks anywhere outside of the modal, close it
window.onclick = function(event) {
    if (event.target.className === 'modal') {
        event.target.style.display = 'none';
    }
}

// Function to load plots
function loadPlots(filename) {
    fetch(`/api/timeseries/${filename}`)
        .then(response => response.json())
        .then(data => {
            const plotContainer = document.getElementById('plotContainer');
            plotContainer.innerHTML = ''; // Clear previous plots

            data.data.forEach((trace, index) => {
                const plotDiv = document.createElement('div');
                plotDiv.id = `plot-${index}`;
                plotDiv.style.width = '100%';
                plotDiv.style.height = '400px';
                plotContainer.appendChild(plotDiv);

                Plotly.newPlot(`plot-${index}`, [trace], {
                    title: trace.name,
                    xaxis: { title: 'Time' },
                    yaxis: { title: trace.name }
                });
            });
        })
        .catch(error => console.error('Error loading plots:', error));
}

// Call this function when the plot page loads
if (window.location.pathname.startsWith('/plot/')) {
    const filename = window.location.pathname.split('/').pop();
    loadPlots(filename);
}