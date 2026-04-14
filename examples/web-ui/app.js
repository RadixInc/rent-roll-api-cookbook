// Radix Rent Roll API Demo - standalone Web UI
//
// This page demonstrates:
// - deal CRUD
// - upload with optional deal attachment
// - batch status polling and result display

(function () {
    'use strict';

    var API_BASE_URL = 'https://connect.rediq.io';
    var MAX_FILES = 20;
    var MAX_FILE_SIZE = 2 * 1024 * 1024;
    var ALLOWED_EXTENSIONS = ['.xlsx', '.xls', '.xlsm', '.csv', '.ods'];
    var STATUS_POLL_INTERVAL = 30000;

    var state = {
        selectedFiles: [],
        deals: [],
        selectedDealId: null,
        currentBatchId: null,
        currentApiKey: null,
        currentAttachedDealId: null,
        currentNotifications: { email: '', webhook: '' },
        statusPollInterval: null,
        totalFiles: 0
    };

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
    var attachDealCheckbox = document.getElementById('attachDealCheckbox');
    var uploadDealSelect = document.getElementById('uploadDealSelect');

    var uploadStep = document.getElementById('uploadStep');
    var successStep = document.getElementById('successStep');
    var errorStep = document.getElementById('errorStep');

    var createDealForm = document.getElementById('createDealForm');
    var loadDealsBtn = document.getElementById('loadDealsBtn');
    var searchDealsBtn = document.getElementById('searchDealsBtn');
    var clearDealSearchBtn = document.getElementById('clearDealSearchBtn');
    var dealSearchInput = document.getElementById('dealSearchInput');
    var dealPicker = document.getElementById('dealPicker');
    var dealsEmptyState = document.getElementById('dealsEmptyState');
    var loadDealDetailsBtn = document.getElementById('loadDealDetailsBtn');
    var attachSelectedDealBtn = document.getElementById('attachSelectedDealBtn');
    var updateDealForm = document.getElementById('updateDealForm');
    var deleteDealBtn = document.getElementById('deleteDealBtn');

    var selectedCounterId = document.getElementById('selectedCounterId');
    var selectedDealName = document.getElementById('selectedDealName');
    var selectedAddress = document.getElementById('selectedAddress');
    var selectedCity = document.getElementById('selectedCity');
    var selectedState = document.getElementById('selectedState');
    var selectedZip = document.getElementById('selectedZip');
    var selectedUnitCount = document.getElementById('selectedUnitCount');

    var batchIdDisplay = document.getElementById('batchIdDisplay');
    var fileCountDisplay = document.getElementById('fileCountDisplay');
    var attachedDealDisplay = document.getElementById('attachedDealDisplay');
    var notificationInfo = document.getElementById('notificationInfo');
    var notificationEmail = document.getElementById('notificationEmail');
    var notificationWebhook = document.getElementById('notificationWebhook');
    var refreshStatusBtn = document.getElementById('refreshStatusBtn');
    var statusBadge = document.getElementById('statusBadge');
    var statusText = statusBadge.querySelector('.status-text');
    var progressFill = document.getElementById('progressFill');
    var progressPercent = document.getElementById('progressPercent');
    var filesCompleted = document.getElementById('filesCompleted');
    var filesInProgress = document.getElementById('filesInProgress');
    var filesFailed = document.getElementById('filesFailed');
    var batchMessage = document.getElementById('batchMessage');
    var batchDownloadsList = document.getElementById('batchDownloadsList');
    var failedFilesList = document.getElementById('failedFilesList');
    var newUploadBtn = document.getElementById('newUploadBtn');

    var errorMessage = document.getElementById('errorMessage');
    var retryBtn = document.getElementById('retryBtn');

    function init() {
        setupEventListeners();
        renderDealOptions();
        validateUploadForm();
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
            if (!emailCheckbox.checked) emailInput.value = '';
            validateUploadForm();
        });

        webhookCheckbox.addEventListener('change', function () {
            webhookInput.disabled = !webhookCheckbox.checked;
            webhookHint.classList.toggle('hidden', !webhookCheckbox.checked);
            if (!webhookCheckbox.checked) webhookInput.value = '';
            validateUploadForm();
        });

        attachDealCheckbox.addEventListener('change', function () {
            uploadDealSelect.disabled = !attachDealCheckbox.checked;
            validateUploadForm();
        });

        uploadDealSelect.addEventListener('change', validateUploadForm);
        uploadForm.addEventListener('submit', handleSubmit);
        apiKeyInput.addEventListener('input', validateUploadForm);
        emailInput.addEventListener('input', validateUploadForm);
        webhookInput.addEventListener('input', validateUploadForm);

        createDealForm.addEventListener('submit', handleCreateDeal);
        loadDealsBtn.addEventListener('click', function () { loadDeals(); });
        searchDealsBtn.addEventListener('click', function () { loadDeals(); });
        clearDealSearchBtn.addEventListener('click', function () {
            dealSearchInput.value = '';
            loadDeals();
        });
        dealPicker.addEventListener('change', function () {
            state.selectedDealId = dealPicker.value ? Number(dealPicker.value) : null;
        });
        loadDealDetailsBtn.addEventListener('click', handleLoadDealDetails);
        attachSelectedDealBtn.addEventListener('click', function () {
            if (!state.selectedDealId) {
                showError('Select a deal first.');
                return;
            }
            attachDealCheckbox.checked = true;
            uploadDealSelect.disabled = false;
            uploadDealSelect.value = String(state.selectedDealId);
            validateUploadForm();
        });
        updateDealForm.addEventListener('submit', handleUpdateDeal);
        deleteDealBtn.addEventListener('click', handleDeleteDeal);

        refreshStatusBtn.addEventListener('click', function () {
            refreshStatusBtn.classList.add('spinning');
            fetchStatus().finally(function () {
                setTimeout(function () { refreshStatusBtn.classList.remove('spinning'); }, 500);
            });
        });

        newUploadBtn.addEventListener('click', resetToUpload);
        retryBtn.addEventListener('click', resetToUpload);
    }

    function getApiKey() {
        var apiKey = apiKeyInput.value.trim();
        if (apiKey.toLowerCase().indexOf('bearer ') === 0) {
            apiKey = apiKey.substring(7);
        }
        return apiKey;
    }

    async function apiJson(path, options) {
        options = options || {};
        var apiKey = getApiKey();
        if (!apiKey) {
            throw new Error('Enter an API key first.');
        }

        var headers = { 'Authorization': 'Bearer ' + apiKey };
        if (options.body && !(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        }

        var response = await fetch(API_BASE_URL + path, {
            method: options.method || 'GET',
            headers: headers,
            body: options.body instanceof FormData ? options.body : (options.body ? JSON.stringify(options.body) : undefined)
        });

        var body = await response.json();
        if (!response.ok) {
            throw new Error(parseApiError(body, response.status));
        }
        return body.data || body;
    }

    function parseApiError(body, status) {
        if (body && typeof body.error === 'string') return body.error;
        if (body && body.error && typeof body.error.message === 'string') return body.error.message;
        return 'Request failed (HTTP ' + status + ')';
    }

    function handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('drag-over');
    }

    function handleDragLeave(e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('drag-over');
    }

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

    function addFiles(files) {
        var valid = files.filter(validateFile);
        if (state.selectedFiles.length + valid.length > MAX_FILES) {
            alert('Maximum ' + MAX_FILES + ' files allowed. Some files were not added.');
            valid.splice(MAX_FILES - state.selectedFiles.length);
        }
        state.selectedFiles = state.selectedFiles.concat(valid);
        renderFileList();
        validateUploadForm();
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
        if (state.selectedFiles.some(function (f) { return f.name === file.name && f.size === file.size; })) {
            return false;
        }
        return true;
    }

    function removeFile(index) {
        state.selectedFiles.splice(index, 1);
        renderFileList();
        validateUploadForm();
    }

    function renderFileList() {
        if (state.selectedFiles.length === 0) {
            fileList.classList.add('hidden');
            fileList.innerHTML = '';
            return;
        }

        fileList.classList.remove('hidden');
        fileList.innerHTML = state.selectedFiles.map(function (file, i) {
            return '<div class="file-item">' +
                '<div class="file-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg></div>' +
                '<div class="file-info"><div class="file-name">' + escapeHtml(file.name) + '</div><div class="file-size">' + formatFileSize(file.size) + '</div></div>' +
                '<button type="button" class="remove-file-btn" onclick="window._removeFile(' + i + ')" title="Remove"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>' +
                '</div>';
        }).join('');
    }

    function validateUploadForm() {
        var hasFiles = state.selectedFiles.length > 0;
        var hasApiKey = getApiKey().length > 0;
        var emailEnabled = emailCheckbox.checked;
        var webhookEnabled = webhookCheckbox.checked;
        var emailValue = emailInput.value.trim();
        var webhookValue = webhookInput.value.trim();
        var hasNotification = (emailEnabled && emailValue) || (webhookEnabled && webhookValue);
        var emailOk = !emailEnabled || isValidEmail(emailValue);
        var webhookOk = !webhookEnabled || isValidUrl(webhookValue);
        var dealOk = !attachDealCheckbox.checked || !!uploadDealSelect.value;

        submitBtn.disabled = !(hasFiles && hasApiKey && hasNotification && emailOk && webhookOk && dealOk);
    }

    function isValidEmail(v) {
        return !v || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
    }

    function isValidUrl(v) {
        if (!v) return true;
        try { return new URL(v).protocol === 'https:'; } catch (_) { return false; }
    }

    async function loadDeals(selectedDealId) {
        try {
            var search = dealSearchInput.value.trim();
            var path = '/api/external/v1/deals?page=1&limit=100';
            if (search) path += '&search=' + encodeURIComponent(search);
            var data = await apiJson(path);
            state.deals = data.deals || [];
            renderDealOptions(selectedDealId || state.selectedDealId);
        } catch (error) {
            showError(error.message || 'Failed to load deals.');
        }
    }

    function renderDealOptions(preferredId) {
        var deals = state.deals;
        dealsEmptyState.textContent = deals.length ? '' : 'No deals loaded.';

        dealPicker.innerHTML = deals.map(function (deal) {
            return '<option value="' + deal.counterId + '">' +
                escapeHtml('[' + deal.counterId + '] ' + deal.dealName + (deal.city ? ' - ' + deal.city : '')) +
                '</option>';
        }).join('');

        uploadDealSelect.innerHTML = ['<option value="">Select a deal</option>'].concat(
            deals.map(function (deal) {
                return '<option value="' + deal.counterId + '">' +
                    escapeHtml('[' + deal.counterId + '] ' + deal.dealName) +
                    '</option>';
            })
        ).join('');

        if (preferredId) {
            dealPicker.value = String(preferredId);
            uploadDealSelect.value = String(preferredId);
            state.selectedDealId = Number(preferredId);
        } else {
            state.selectedDealId = dealPicker.value ? Number(dealPicker.value) : null;
        }
    }

    async function handleCreateDeal(e) {
        e.preventDefault();
        try {
            var deal = await apiJson('/api/external/v1/deals', {
                method: 'POST',
                body: collectDealFormValues('create')
            });
            createDealForm.reset();
            await loadDeals(deal.counterId);
            fillSelectedDeal(deal);
        } catch (error) {
            showError(error.message || 'Failed to create deal.');
        }
    }

    async function handleLoadDealDetails() {
        if (!dealPicker.value) {
            showError('Select a deal first.');
            return;
        }
        try {
            var deal = await apiJson('/api/external/v1/deals/' + dealPicker.value);
            fillSelectedDeal(deal);
        } catch (error) {
            showError(error.message || 'Failed to load deal details.');
        }
    }

    async function handleUpdateDeal(e) {
        e.preventDefault();
        var counterId = selectedCounterId.value;
        if (!counterId) {
            showError('Load a deal before updating.');
            return;
        }

        try {
            var payload = collectDealFormValues('selected');
            if (!Object.keys(payload).length) {
                showError('Provide at least one field to update.');
                return;
            }
            var deal = await apiJson('/api/external/v1/deals/' + counterId, {
                method: 'PUT',
                body: payload
            });
            await loadDeals(deal.counterId);
            fillSelectedDeal(deal);
        } catch (error) {
            showError(error.message || 'Failed to update deal.');
        }
    }

    async function handleDeleteDeal() {
        var counterId = selectedCounterId.value;
        if (!counterId) {
            showError('Load a deal before deleting.');
            return;
        }
        if (!window.confirm('Delete deal ' + counterId + '?')) {
            return;
        }

        try {
            await apiJson('/api/external/v1/deals/' + counterId, { method: 'DELETE' });
            clearSelectedDeal();
            await loadDeals();
        } catch (error) {
            showError(error.message || 'Failed to delete deal.');
        }
    }

    function collectDealFormValues(mode) {
        var values = mode === 'create'
            ? {
                dealName: document.getElementById('createDealName').value.trim(),
                address: document.getElementById('createAddress').value.trim(),
                city: document.getElementById('createCity').value.trim(),
                state: document.getElementById('createState').value.trim(),
                zip: document.getElementById('createZip').value.trim(),
                unitCount: document.getElementById('createUnitCount').value.trim()
            }
            : {
                dealName: selectedDealName.value.trim(),
                address: selectedAddress.value.trim(),
                city: selectedCity.value.trim(),
                state: selectedState.value.trim(),
                zip: selectedZip.value.trim(),
                unitCount: selectedUnitCount.value.trim()
            };

        if (values.unitCount) values.unitCount = Number(values.unitCount);
        else delete values.unitCount;

        Object.keys(values).forEach(function (key) {
            if (values[key] === '') delete values[key];
        });
        return values;
    }

    function fillSelectedDeal(deal) {
        state.selectedDealId = deal.counterId;
        selectedCounterId.value = deal.counterId || '';
        selectedDealName.value = deal.dealName || '';
        selectedAddress.value = deal.address || '';
        selectedCity.value = deal.city || '';
        selectedState.value = deal.state || '';
        selectedZip.value = deal.zip || '';
        selectedUnitCount.value = deal.unitCount || '';
        renderDealOptions(deal.counterId);
    }

    function clearSelectedDeal() {
        state.selectedDealId = null;
        selectedCounterId.value = '';
        selectedDealName.value = '';
        selectedAddress.value = '';
        selectedCity.value = '';
        selectedState.value = '';
        selectedZip.value = '';
        selectedUnitCount.value = '';
    }

    async function handleSubmit(e) {
        e.preventDefault();
        if (state.selectedFiles.length === 0) return;

        var apiKey = getApiKey();
        var email = emailCheckbox.checked ? emailInput.value.trim() : '';
        var webhookUrl = webhookCheckbox.checked ? webhookInput.value.trim() : '';
        var attachedDealId = attachDealCheckbox.checked && uploadDealSelect.value ? Number(uploadDealSelect.value) : null;

        state.currentApiKey = apiKey;
        state.currentAttachedDealId = attachedDealId;
        state.currentNotifications = { email: email, webhook: webhookUrl };
        state.totalFiles = state.selectedFiles.length;

        var notificationMethod = [];
        if (email) notificationMethod.push({ type: 'email', entry: email });
        if (webhookUrl) notificationMethod.push({ type: 'webhook', entry: webhookUrl });

        var formData = new FormData();
        state.selectedFiles.forEach(function (f) { formData.append('files', f); });
        formData.append('notificationMethod', JSON.stringify(notificationMethod));
        if (attachedDealId) formData.append('dealId', String(attachedDealId));

        setLoading(true);

        try {
            var data = await apiJson('/api/external/v1/upload', {
                method: 'POST',
                body: formData
            });
            showSuccess(data);
        } catch (error) {
            showError(error.message || 'Upload failed.');
        } finally {
            setLoading(false);
        }
    }

    function setLoading(on) {
        submitBtn.classList.toggle('loading', on);
        submitBtn.disabled = on;
    }

    function showStep(step) {
        [uploadStep, successStep, errorStep].forEach(function (s) { s.classList.remove('active'); });
        step.classList.add('active');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function showSuccess(data) {
        state.currentBatchId = data.batchId;
        batchIdDisplay.textContent = data.batchId || '-';
        fileCountDisplay.textContent = data.filesUploaded || state.totalFiles;
        attachedDealDisplay.textContent = formatAttachedDealLabel(state.currentAttachedDealId);

        var email = state.currentNotifications.email;
        var webhook = state.currentNotifications.webhook;
        notificationInfo.classList.toggle('hidden', !(email || webhook));
        notificationEmail.classList.toggle('hidden', !email);
        notificationWebhook.classList.toggle('hidden', !webhook);
        if (email) notificationEmail.querySelector('.notification-value').textContent = email;
        if (webhook) notificationWebhook.querySelector('.notification-value').textContent = webhook;

        renderBatchDownloads([]);
        renderFailedFiles([]);
        updateStatusDisplay({
            status: 'queued',
            filesCompleted: 0,
            filesInProgress: 0,
            filesFailed: 0,
            fileCount: state.totalFiles,
            percentComplete: 0,
            errorMessage: data.message || 'Files uploaded successfully. Processing started.'
        });
        showStep(successStep);
        startStatusPolling();
    }

    function showError(message) {
        errorMessage.textContent = message;
        showStep(errorStep);
    }

    function resetToUpload() {
        stopStatusPolling();
        state.currentBatchId = null;
        state.currentApiKey = null;
        state.currentAttachedDealId = null;
        state.currentNotifications = { email: '', webhook: '' };
        state.selectedFiles = [];
        renderFileList();
        uploadForm.reset();
        emailInput.disabled = true;
        webhookInput.disabled = true;
        uploadDealSelect.disabled = true;
        webhookHint.classList.add('hidden');
        validateUploadForm();
        showStep(uploadStep);
    }

    function startStatusPolling() {
        stopStatusPolling();
        fetchStatus();
        state.statusPollInterval = setInterval(fetchStatus, STATUS_POLL_INTERVAL);
    }

    function stopStatusPolling() {
        if (state.statusPollInterval) {
            clearInterval(state.statusPollInterval);
            state.statusPollInterval = null;
        }
    }

    async function fetchStatus() {
        if (!state.currentBatchId || !state.currentApiKey) return;
        try {
            var data = await apiJson('/api/external/v1/job/' + state.currentBatchId + '/status');
            processStatusData(data);
        } catch (err) {
            console.error('Status fetch error:', err);
            batchMessage.textContent = err.message || 'Failed to refresh batch status.';
        }
    }

    function processStatusData(data) {
        updateStatusDisplay(data);
        renderBatchDownloads(data.batchDownloads || []);
        renderFailedFiles((data.files || []).filter(function (file) {
            return normalizeStatus(file.status).indexOf('fail') !== -1;
        }));

        var normalized = normalizeStatus(data.status);
        if (normalized === 'complete' || normalized === 'failed' || normalized === 'partially complete') {
            stopStatusPolling();
        }
    }

    function updateStatusDisplay(data) {
        var normalized = normalizeStatus(data.status);
        var badgeClass = 'queued';
        if (normalized === 'in progress') badgeClass = 'processing';
        else if (normalized === 'complete') badgeClass = 'complete';
        else if (normalized === 'failed') badgeClass = 'failed';
        else if (normalized === 'partially complete') badgeClass = 'partial';

        statusBadge.className = 'status-badge ' + badgeClass;
        statusText.textContent = formatStatusLabel(data.status || 'queued');

        var percent = Math.round(data.percentComplete || 0);
        progressFill.style.width = percent + '%';
        progressPercent.textContent = percent + '% complete';

        filesCompleted.textContent = (data.filesCompleted || 0) + ' / ' + (data.fileCount || state.totalFiles || 0);
        filesInProgress.textContent = String(data.filesInProgress || 0);
        filesFailed.textContent = String(data.filesFailed || 0);
        batchMessage.textContent = data.errorMessage || inferBatchMessage(data);
    }

    function inferBatchMessage(data) {
        var normalized = normalizeStatus(data.status);
        if (normalized === 'queued') return 'Batch is queued for processing.';
        if (normalized === 'in progress') return 'Batch is currently being processed.';
        if (normalized === 'complete') return 'Batch completed successfully.';
        if (normalized === 'partially complete') return 'Batch completed with one or more failed files.';
        if (normalized === 'failed') return 'Batch failed.';
        return 'Waiting for the next status update.';
    }

    function renderBatchDownloads(downloads) {
        if (!downloads.length) {
            batchDownloadsList.innerHTML = '<li>No download links available yet.</li>';
            return;
        }
        batchDownloadsList.innerHTML = downloads.map(function (item) {
            return '<li><strong>' + escapeHtml(item.type || 'download') + ':</strong> ' +
                '<a href="' + escapeHtml(item.downloadUrl || '#') + '" target="_blank" rel="noopener noreferrer">' +
                escapeHtml(item.downloadUrl || '') +
                '</a></li>';
        }).join('');
    }

    function renderFailedFiles(files) {
        if (!files.length) {
            failedFilesList.innerHTML = '<li>No failed files.</li>';
            return;
        }
        failedFilesList.innerHTML = files.map(function (file) {
            return '<li><strong>' + escapeHtml(file.fileName || 'Unknown file') + ':</strong> ' +
                escapeHtml(file.errorMessage || 'Unknown error') + '</li>';
        }).join('');
    }

    function formatStatusLabel(status) {
        var normalized = normalizeStatus(status);
        if (normalized === 'in progress') return 'In Progress';
        if (normalized === 'partially complete') return 'Partially Complete';
        if (normalized === 'complete') return 'Complete';
        if (normalized === 'failed') return 'Failed';
        return 'Queued';
    }

    function formatAttachedDealLabel(counterId) {
        if (!counterId) return 'None';
        var match = state.deals.filter(function (deal) { return String(deal.counterId) === String(counterId); })[0];
        return match ? '[' + match.counterId + '] ' + match.dealName : String(counterId);
    }

    function normalizeStatus(value) {
        return String(value || '').trim().toLowerCase();
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        var k = 1024;
        var sizes = ['B', 'KB', 'MB', 'GB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    window._removeFile = removeFile;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
