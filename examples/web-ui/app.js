// Radix Rent Roll Uploader — Standalone Web UI
//
// This is a self-contained single-page app that uploads rent roll files
// to the Radix Underwriting API and polls for processing status.
//
// To use: open index.html in a browser and enter your API key.
// All requests go to the production API at https://connect.rediq.io.

(function () {
    'use strict';

    // -----------------------------------------------------------------------
    // Configuration — change this if you are targeting a different environment
    // -----------------------------------------------------------------------
    var API_BASE_URL = 'https://connect.rediq.io';

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------
    var selectedFiles = [];
    var currentBatchId = null;
    var currentApiKey = null;
    var statusPollInterval = null;
    var totalFiles = 0;

    // -----------------------------------------------------------------------
    // DOM elements
    // -----------------------------------------------------------------------
    var dropZone = document.getElementById('dropZone');
    var fileInput = document.getElementById('fileInput');
    var browseLink = document.getElementById('browseLink');
    var fileList = document.getElementById('fileList');
    var uploadForm = document.getElementById('uploadForm');
    var submitBtn = document.getElementById('submitBtn');
    var apiKeyInput = document.getElementById('apiKey');
    var toggleApiKeyBtn = document.getElementById('toggleApiKey');
    var emailCheckbox = document.getElementById('emailCheckbox');
    var emailInput = document.getElementById('email');
    var webhookCheckbox = document.getElementById('webhookCheckbox');
    var webhookInput = document.getElementById('webhookUrl');
    var webhookHint = document.querySelector('.webhook-hint');

    // Steps
    var uploadStep = document.getElementById('uploadStep');
    var successStep = document.getElementById('successStep');
    var errorStep = document.getElementById('errorStep');

    // Success elements
    var batchIdDisplay = document.getElementById('batchIdDisplay');
    var fileCountDisplay = document.getElementById('fileCountDisplay');
    var notificationInfo = document.getElementById('notificationInfo');
    var notificationEmail = document.getElementById('notificationEmail');
    var refreshStatusBtn = document.getElementById('refreshStatusBtn');
    var statusBadge = document.getElementById('statusBadge');
    var statusText = statusBadge.querySelector('.status-text');
    var progressFill = document.getElementById('progressFill');
    var progressPercent = document.getElementById('progressPercent');
    var filesCompleted = document.getElementById('filesCompleted');
    var filesInProgress = document.getElementById('filesInProgress');
    var filesFailed = document.getElementById('filesFailed');
    var newUploadBtn = document.getElementById('newUploadBtn');

    // Error elements
    var errorMessage = document.getElementById('errorMessage');
    var retryBtn = document.getElementById('retryBtn');

    // Constants
    var MAX_FILES = 20;
    var MAX_FILE_SIZE = 2 * 1024 * 1024; // 2 MB
    var ALLOWED_EXTENSIONS = ['.xlsx', '.xls', '.xlsm', '.csv', '.ods'];
    var STATUS_POLL_INTERVAL = 30000; // 30 seconds

    // -----------------------------------------------------------------------
    // Initialisation
    // -----------------------------------------------------------------------
    function init() {
        setupEventListeners();
    }

    function setupEventListeners() {
        dropZone.addEventListener('click', function (e) {
            if (e.target.id !== 'browseLink') fileInput.click();
        });
        browseLink.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            fileInput.click();
        });

        dropZone.addEventListener('dragover', handleDragOver);
        dropZone.addEventListener('dragleave', handleDragLeave);
        dropZone.addEventListener('drop', handleDrop);
        fileInput.addEventListener('change', handleFileSelect);

        toggleApiKeyBtn.addEventListener('click', function () {
            apiKeyInput.type = apiKeyInput.type === 'password' ? 'text' : 'password';
        });

        emailCheckbox.addEventListener('change', function () {
            emailInput.disabled = !emailCheckbox.checked;
            if (emailCheckbox.checked) emailInput.focus(); else emailInput.value = '';
            validateForm();
        });

        webhookCheckbox.addEventListener('change', function () {
            webhookInput.disabled = !webhookCheckbox.checked;
            webhookHint.classList.toggle('hidden', !webhookCheckbox.checked);
            if (webhookCheckbox.checked) webhookInput.focus(); else webhookInput.value = '';
            validateForm();
        });

        uploadForm.addEventListener('submit', handleSubmit);
        apiKeyInput.addEventListener('input', validateForm);
        emailInput.addEventListener('input', validateForm);
        webhookInput.addEventListener('input', validateForm);

        refreshStatusBtn.addEventListener('click', function () {
            refreshStatusBtn.classList.add('spinning');
            fetchStatus().finally(function () {
                setTimeout(function () { refreshStatusBtn.classList.remove('spinning'); }, 500);
            });
        });

        newUploadBtn.addEventListener('click', resetToUpload);
        retryBtn.addEventListener('click', resetToUpload);
    }

    // -----------------------------------------------------------------------
    // Drag & drop
    // -----------------------------------------------------------------------
    function handleDragOver(e) { e.preventDefault(); e.stopPropagation(); dropZone.classList.add('drag-over'); }
    function handleDragLeave(e) { e.preventDefault(); e.stopPropagation(); dropZone.classList.remove('drag-over'); }

    function handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('drag-over');
        addFiles(Array.from(e.dataTransfer.files));
    }

    function handleFileSelect(e) {
        addFiles(Array.from(e.target.files));
        fileInput.value = '';
    }

    // -----------------------------------------------------------------------
    // File management
    // -----------------------------------------------------------------------
    function addFiles(files) {
        var valid = files.filter(validateFile);
        if (selectedFiles.length + valid.length > MAX_FILES) {
            alert('Maximum ' + MAX_FILES + ' files allowed. Some files were not added.');
            valid.splice(MAX_FILES - selectedFiles.length);
        }
        selectedFiles = selectedFiles.concat(valid);
        renderFileList();
        validateForm();
    }

    function validateFile(file) {
        var ext = '.' + file.name.split('.').pop().toLowerCase();
        if (ALLOWED_EXTENSIONS.indexOf(ext) === -1) {
            alert('"' + file.name + '" is not a valid file type. Allowed: ' + ALLOWED_EXTENSIONS.join(', '));
            return false;
        }
        if (file.size > MAX_FILE_SIZE) {
            alert('"' + file.name + '" exceeds the 2 MB size limit.');
            return false;
        }
        if (selectedFiles.some(function (f) { return f.name === file.name && f.size === file.size; })) {
            return false;
        }
        return true;
    }

    function removeFile(index) {
        selectedFiles.splice(index, 1);
        renderFileList();
        validateForm();
    }

    function renderFileList() {
        if (selectedFiles.length === 0) {
            fileList.classList.add('hidden');
            fileList.innerHTML = '';
            return;
        }
        fileList.classList.remove('hidden');
        fileList.innerHTML = selectedFiles.map(function (file, i) {
            return '<div class="file-item">' +
                '<div class="file-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg></div>' +
                '<div class="file-info"><div class="file-name">' + escapeHtml(file.name) + '</div><div class="file-size">' + formatFileSize(file.size) + '</div></div>' +
                '<button type="button" class="remove-file-btn" onclick="window._removeFile(' + i + ')" title="Remove"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>' +
                '</div>';
        }).join('');
    }

    // -----------------------------------------------------------------------
    // Form validation
    // -----------------------------------------------------------------------
    function validateForm() {
        var hasFiles = selectedFiles.length > 0;
        var hasApiKey = apiKeyInput.value.trim().length > 0;
        var emailOk = !emailCheckbox.checked || isValidEmail(emailInput.value);
        var webhookOk = !webhookCheckbox.checked || isValidUrl(webhookInput.value);
        var hasNotification = (emailCheckbox.checked && emailInput.value.trim()) ||
                              (webhookCheckbox.checked && webhookInput.value.trim());
        submitBtn.disabled = !(hasFiles && hasApiKey && hasNotification && emailOk && webhookOk);
    }

    function isValidEmail(v) { return !v || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v); }
    function isValidUrl(v) {
        if (!v) return true;
        try { return new URL(v).protocol === 'https:'; } catch (_) { return false; }
    }

    // -----------------------------------------------------------------------
    // Submit
    // -----------------------------------------------------------------------
    async function handleSubmit(e) {
        e.preventDefault();
        if (selectedFiles.length === 0) return;

        var apiKey = apiKeyInput.value.trim();
        var email = emailCheckbox.checked ? emailInput.value.trim() : '';
        var webhookUrl = webhookCheckbox.checked ? webhookInput.value.trim() : '';

        // Strip "Bearer " prefix if user pasted the full header value
        if (apiKey.toLowerCase().startsWith('bearer ')) apiKey = apiKey.substring(7);

        currentApiKey = apiKey;
        totalFiles = selectedFiles.length;

        var notificationMethod = [];
        if (email) notificationMethod.push({ type: 'email', entry: email });
        if (webhookUrl) notificationMethod.push({ type: 'webhook', entry: webhookUrl });

        var formData = new FormData();
        selectedFiles.forEach(function (f) { formData.append('files', f); });
        formData.append('notificationMethod', JSON.stringify(notificationMethod));

        setLoading(true);

        try {
            var response = await fetch(API_BASE_URL + '/api/external/v1/upload', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + apiKey },
                body: formData
            });

            var body = await response.json();

            if (!response.ok) {
                var err = body.error;
                var msg = 'Upload failed';
                if (typeof err === 'string') msg = err;
                else if (err && typeof err === 'object') {
                    msg = err.message || 'Upload failed';
                    if (Array.isArray(err.details)) msg += ': ' + err.details.map(function (d) { return d.message || d.path; }).join(', ');
                }
                throw new Error(msg);
            }

            showSuccess(body.data || body, email);
        } catch (error) {
            console.error('Upload error:', error);
            showError(error.message || 'An unexpected error occurred');
        } finally {
            setLoading(false);
        }
    }

    function setLoading(on) {
        submitBtn.classList.toggle('loading', on);
        submitBtn.disabled = on;
    }

    // -----------------------------------------------------------------------
    // Step navigation
    // -----------------------------------------------------------------------
    function showStep(step) {
        [uploadStep, successStep, errorStep].forEach(function (s) { s.classList.remove('active'); });
        step.classList.add('active');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function showSuccess(data, email) {
        currentBatchId = data.batchId;
        batchIdDisplay.textContent = data.batchId || '-';
        fileCountDisplay.textContent = data.filesUploaded || totalFiles;

        if (email) {
            notificationInfo.classList.remove('hidden');
            notificationEmail.classList.remove('hidden');
            notificationEmail.querySelector('.notification-value').textContent = email;
        } else {
            notificationInfo.classList.add('hidden');
        }

        updateStatusDisplay({ status: 'queued', completed: 0, inProgress: 0, failed: 0, total: totalFiles });
        showStep(successStep);
        startStatusPolling();
    }

    function showError(message) {
        errorMessage.textContent = message;
        showStep(errorStep);
    }

    function resetToUpload() {
        stopStatusPolling();
        currentBatchId = null;
        currentApiKey = null;
        selectedFiles = [];
        renderFileList();
        uploadForm.reset();
        emailInput.disabled = true;
        webhookInput.disabled = true;
        webhookHint.classList.add('hidden');
        validateForm();
        showStep(uploadStep);
    }

    // -----------------------------------------------------------------------
    // Status polling
    // -----------------------------------------------------------------------
    function startStatusPolling() {
        fetchStatus();
        statusPollInterval = setInterval(fetchStatus, STATUS_POLL_INTERVAL);
    }

    function stopStatusPolling() {
        if (statusPollInterval) { clearInterval(statusPollInterval); statusPollInterval = null; }
    }

    async function fetchStatus() {
        if (!currentBatchId || !currentApiKey) return;
        try {
            var response = await fetch(API_BASE_URL + '/api/external/v1/job/' + currentBatchId + '/status', {
                headers: { 'Authorization': 'Bearer ' + currentApiKey }
            });
            if (!response.ok) throw new Error('Failed to fetch status');
            var body = await response.json();
            processStatusData(body.data || body);
        } catch (err) {
            console.error('Status fetch error:', err);
        }
    }

    function processStatusData(data) {
        var files = data.files || [];
        var total = files.length || totalFiles;
        var completed = 0, inProgress = 0, failed = 0;

        files.forEach(function (f) {
            var s = (f.status || '').toLowerCase();
            if (s.indexOf('complete') !== -1 || s.indexOf('success') !== -1 || s === 'done') completed++;
            else if (s.indexOf('fail') !== -1 || s.indexOf('error') !== -1) failed++;
            else inProgress++;
        });

        var overall = 'queued';
        if (completed + failed === total && total > 0) {
            overall = failed > 0 ? 'failed' : 'complete';
            stopStatusPolling();
        } else if (completed > 0 || inProgress > 0) {
            overall = 'processing';
        }

        updateStatusDisplay({ status: overall, completed: completed, inProgress: inProgress, failed: failed, total: total });
    }

    function updateStatusDisplay(info) {
        statusBadge.className = 'status-badge ' + info.status;
        var labels = { queued: 'Queued', processing: 'In Progress', complete: 'Complete', failed: 'Failed' };
        statusText.textContent = labels[info.status] || 'Unknown';

        var pct = info.total > 0 ? Math.round((info.completed / info.total) * 100) : 0;
        progressFill.style.width = pct + '%';
        progressPercent.textContent = pct + '% complete';

        filesCompleted.textContent = info.completed + ' / ' + info.total;
        filesInProgress.textContent = info.inProgress;
        filesFailed.textContent = info.failed;
    }

    // -----------------------------------------------------------------------
    // Utilities
    // -----------------------------------------------------------------------
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        var k = 1024, sizes = ['B', 'KB', 'MB', 'GB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Expose removeFile globally for inline onclick handlers
    window._removeFile = removeFile;

    // Boot
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();


