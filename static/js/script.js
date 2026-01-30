/**
 * AutoCaption Pro — batch video upload, processing, and download.
 * Consumes NDJSON stream from /upload_and_process; parses lines safely.
 */

document.addEventListener('DOMContentLoaded', () => {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const srtUploadArea = document.getElementById('srt-upload-area');
    const srtFileInput = document.getElementById('srt-file-input');
    const videoList = document.getElementById('video-list');
    const globalActions = document.getElementById('global-actions');
    const processBtn = document.getElementById('process-btn');
    const clearBtn = document.getElementById('clear-btn');
    const uploadContent = document.querySelector('.upload-content');
    const progressArea = document.getElementById('progress-area');
    const progressText = document.getElementById('progress-text');
    const modelSelect = document.getElementById('model-select');
    const cudaStatus = document.getElementById('cuda-status');
    let cudaAvailable = null;
    const promptInput = document.getElementById('prompt-input');
    const srtList = document.getElementById('srt-list');
    const srtActions = document.getElementById('srt-actions');
    const srtProcessBtn = document.getElementById('srt-process-btn');
    const modeTabs = document.querySelectorAll('.mode-tab');
    const modePanels = document.querySelectorAll('.mode-panel');

    /** @type {{ file: File, id: string, status: string, results: Array<{label:string,url:string}>|null }[]} */
    let videoQueue = [];
    const heavyModels = new Set(['medium', 'large', 'large-v2', 'large-v3']);

    async function fetchSystemInfo() {
        try {
            const res = await fetch('/system_info');
            if (!res.ok) throw new Error('Failed to fetch system info');
            const data = await res.json();
            cudaAvailable = Boolean(data.cuda_available);
            if (cudaStatus) {
                cudaStatus.textContent = cudaAvailable ? 'GPU (CUDA)' : 'CPU';
            }
        } catch (error) {
            if (cudaStatus) cudaStatus.textContent = 'Unknown';
        }
    }

    function warnIfNoCuda(modelValue) {
        if (cudaAvailable === false && heavyModels.has(modelValue)) {
            alert('Selected model benefits from GPU. Current device is CPU; consider using a smaller model or installing CUDA-enabled PyTorch.');
        }
    }

    fetchSystemInfo();

    if (modelSelect) {
        modelSelect.addEventListener('change', () => warnIfNoCuda(modelSelect.value));
    }
    /** @type {{ file: File, id: string, status: string, results: Array<{label:string,url:string}>|null }[]} */
    let srtQueue = [];

    function setActiveMode(mode) {
        modeTabs.forEach((tab) => {
            tab.classList.toggle('active', tab.dataset.mode === mode);
        });
        modePanels.forEach((panel) => {
            panel.classList.toggle('active', panel.id === `mode-${mode}`);
        });
    }

    modeTabs.forEach((tab) => {
        tab.addEventListener('click', () => setActiveMode(tab.dataset.mode));
    });

    // —— Drag & Drop ——
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((eventName) => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach((eventName) => {
        uploadArea.addEventListener(eventName, () => uploadArea.classList.add('drag-over'), false);
    });

    ['dragleave', 'drop'].forEach((eventName) => {
        uploadArea.addEventListener(eventName, () => uploadArea.classList.remove('drag-over'), false);
    });

    uploadArea.addEventListener('drop', (e) => {
        handleFiles(e.dataTransfer.files);
    }, false);

    uploadArea.addEventListener('click', (e) => {
        if (!e.target.closest('.video-item')) {
            fileInput.click();
        }
    });

    fileInput.addEventListener('change', () => handleFiles(fileInput.files));

    if (srtUploadArea && srtFileInput) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((eventName) => {
            srtUploadArea.addEventListener(eventName, preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach((eventName) => {
            srtUploadArea.addEventListener(eventName, () => srtUploadArea.classList.add('drag-over'), false);
        });

        ['dragleave', 'drop'].forEach((eventName) => {
            srtUploadArea.addEventListener(eventName, () => srtUploadArea.classList.remove('drag-over'), false);
        });

        srtUploadArea.addEventListener('drop', (e) => {
            handleSrtFiles(e.dataTransfer.files);
        }, false);

        srtUploadArea.addEventListener('click', (e) => {
            if (!e.target.closest('.video-item')) {
                srtFileInput.click();
            }
        });

        srtFileInput.addEventListener('change', () => handleSrtFiles(srtFileInput.files));
    }

    function handleFiles(files) {
        if (!files || files.length === 0) return;
        Array.from(files).forEach((file) => {
            const videoId = Math.random().toString(36).substring(2, 11);
            videoQueue.push({
                file,
                id: videoId,
                status: 'pending',
                results: null,
            });
            addVideoToUI(videoQueue[videoQueue.length - 1]);
        });
        updateUIState();
    }

    function handleSrtFiles(files) {
        if (!files || files.length === 0) return;
        Array.from(files).forEach((file) => {
            const srtId = Math.random().toString(36).substring(2, 11);
            srtQueue.push({
                file,
                id: srtId,
                status: 'pending',
                results: null,
            });
            addSrtToUI(srtQueue[srtQueue.length - 1]);
        });
        updateSrtUIState();
    }

    function addVideoToUI(video) {
        const item = document.createElement('div');
        item.className = 'video-item';
        item.id = `video-${video.id}`;
        const safeName = escapeHtml(video.file.name);
        item.innerHTML = `
            <div class="video-item-row">
                <div class="video-header">
                    <i class="fa-solid fa-file-video" style="color: var(--primary);"></i>
                    <span class="video-name" title="${safeName}">${safeName}</span>
                </div>
                <div class="video-item-settings">
                    <div class="setting-group">
                        <label>Source Language:</label>
                        <select class="source-lang-select">
                            <option value="auto">Auto Detect</option>
                            <option value="en">English</option>
                            <option value="zh-CN">Chinese (Simplified)</option>
                            <option value="zh-TW">Chinese (Traditional)</option>
                            <option value="es">Spanish</option>
                            <option value="fr">French</option>
                            <option value="de">German</option>
                            <option value="ja">Japanese</option>
                            <option value="ko">Korean</option>
                        </select>
                    </div>
                    <div class="setting-group">
                        <label>Target Language:</label>
                        <select class="target-lang-select">
                            <option value="auto">Auto (Smart Select)</option>
                            <option value="zh-CN">Chinese (Simplified)</option>
                            <option value="zh-TW">Chinese (Traditional)</option>
                            <option value="en">English (UK)</option>
                            <option value="es">Spanish</option>
                            <option value="fr">French</option>
                            <option value="de">German</option>
                            <option value="ja">Japanese</option>
                            <option value="ko">Korean</option>
                            <option value="none">None (Transcript Only)</option>
                        </select>
                    </div>
                </div>
                <div class="video-advanced-toggle" role="button" aria-expanded="false">
                    <i class="fa-solid fa-sliders"></i> Advanced
                </div>
                <i class="fa-solid fa-xmark remove-video-btn" data-id="${video.id}" title="Remove Video"></i>
            </div>
            <div class="video-advanced-fields">
                <div class="setting-group">
                    <label>Whisper Model (Override):</label>
                    <select class="video-model-select">
                        <option value="batch">Use Batch Settings</option>
                        <option value="tiny">tiny</option>
                        <option value="base">base</option>
                        <option value="small">small</option>
                        <option value="medium">medium</option>
                        <option value="large">large</option>
                        <option value="large-v2">large-v2</option>
                        <option value="large-v3">large-v3</option>
                    </select>
                </div>
                <div class="setting-group">
                    <label>Initial Prompt (Override):</label>
                    <textarea class="video-prompt-input" rows="2" placeholder="Optional: names, places, terms"></textarea>
                </div>
            </div>
            <div class="video-progress" id="progress-${video.id}">Waiting for processing...</div>
            <div class="video-results" id="results-${video.id}"></div>
        `;

        const toggle = item.querySelector('.video-advanced-toggle');
        const advancedFields = item.querySelector('.video-advanced-fields');
        const videoModelSelect = item.querySelector('.video-model-select');
        if (toggle && advancedFields) {
            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                const isOpen = advancedFields.classList.toggle('active');
                toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            });
        }

        if (videoModelSelect) {
            videoModelSelect.addEventListener('change', () => {
                if (videoModelSelect.value !== 'batch') {
                    warnIfNoCuda(videoModelSelect.value);
                } else if (modelSelect) {
                    warnIfNoCuda(modelSelect.value);
                }
            });
        }

        item.querySelector('.remove-video-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            removeVideo(video.id);
        });

        videoList.appendChild(item);
    }

    function addSrtToUI(srtItem) {
        if (!srtList) return;
        const item = document.createElement('div');
        item.className = 'video-item';
        item.id = `srt-${srtItem.id}`;
        const safeName = escapeHtml(srtItem.file.name);
        item.innerHTML = `
            <div class="video-header">
                <i class="fa-solid fa-file-lines" style="color: var(--accent);"></i>
                <span class="video-name" title="${safeName}">${safeName}</span>
            </div>
            <div class="video-item-settings">
                <div class="setting-group">
                    <label>Source Language:</label>
                    <select class="srt-source-select">
                        <option value="auto">Auto</option>
                        <option value="en">English</option>
                        <option value="zh-CN">Chinese (Simplified)</option>
                        <option value="zh-TW">Chinese (Traditional)</option>
                        <option value="es">Spanish</option>
                        <option value="fr">French</option>
                        <option value="de">German</option>
                        <option value="ja">Japanese</option>
                        <option value="ko">Korean</option>
                    </select>
                </div>
                <div class="setting-group">
                    <label>Target Language:</label>
                    <select class="srt-target-select">
                        <option value="auto">Auto (Smart Select)</option>
                        <option value="zh-CN">Chinese (Simplified)</option>
                        <option value="zh-TW">Chinese (Traditional)</option>
                        <option value="en">English (UK)</option>
                        <option value="es">Spanish</option>
                        <option value="fr">French</option>
                        <option value="de">German</option>
                        <option value="ja">Japanese</option>
                        <option value="ko">Korean</option>
                    </select>
                </div>
            </div>
            <div class="video-progress" id="progress-srt-${srtItem.id}">Waiting for processing...</div>
            <div class="video-results" id="results-srt-${srtItem.id}"></div>
            <i class="fa-solid fa-xmark remove-video-btn" data-id="${srtItem.id}" title="Remove SRT"></i>
        `;

        item.querySelector('.remove-video-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            removeSrt(srtItem.id);
        });

        srtList.appendChild(item);
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function removeVideo(id) {
        videoQueue = videoQueue.filter((v) => v.id !== id);
        const el = document.getElementById(`video-${id}`);
        if (el) el.remove();
        updateUIState();
    }

    function removeSrt(id) {
        srtQueue = srtQueue.filter((v) => v.id !== id);
        const el = document.getElementById(`srt-${id}`);
        if (el) el.remove();
        updateSrtUIState();
    }

    function updateUIState() {
        if (videoQueue.length > 0) {
            uploadContent.style.padding = '1rem';
            uploadContent.querySelector('h3').textContent = 'Add More Videos';
            globalActions.style.display = 'block';
            processBtn.disabled = videoQueue.every((v) => v.status === 'completed');
        } else {
            uploadContent.style.padding = '3rem 2rem';
            uploadContent.querySelector('h3').textContent = 'Drag & Drop Video Here';
            globalActions.style.display = 'none';
        }
    }

    function updateSrtUIState() {
        if (!srtActions || !srtProcessBtn) return;
        if (srtQueue.length > 0) {
            srtActions.style.display = 'block';
            srtProcessBtn.disabled = srtQueue.every((v) => v.status === 'completed');
        } else {
            srtActions.style.display = 'none';
        }
    }

    processBtn.addEventListener('click', async () => {
        const toProcess = videoQueue.filter((v) => v.status !== 'completed' && v.status !== 'processing');
        if (toProcess.length === 0) return;

        processBtn.disabled = true;
        processBtn.querySelector('.btn-text').textContent = 'Processing Batch...';
        processBtn.querySelector('.loader').style.display = 'block';
        if (progressArea && progressText) {
            progressArea.style.display = 'block';
            progressText.textContent = `Processing 0 of ${toProcess.length}...`;
        }

        const total = toProcess.length;
        let current = 0;

        try {
            for (const video of videoQueue) {
                if (video.status === 'completed' || video.status === 'processing') continue;
                current += 1;
                if (progressArea && progressText) {
                    progressText.textContent = `Processing ${current} of ${total}: ${video.file.name}`;
                }
                await processSingleVideo(video, (msg) => {
                    if (progressText) progressText.textContent = `[${current}/${total}] ${msg}`;
                });
            }
        } finally {
            processBtn.querySelector('.btn-text').textContent = 'Generate All Subtitles';
            processBtn.querySelector('.loader').style.display = 'none';
            processBtn.disabled = false;
            if (progressArea) progressArea.style.display = 'none';
            updateUIState();
        }
    });

    if (srtProcessBtn) {
        srtProcessBtn.addEventListener('click', async () => {
            const toProcess = srtQueue.filter((v) => v.status !== 'completed' && v.status !== 'processing');
            if (toProcess.length === 0) return;

            srtProcessBtn.disabled = true;
            srtProcessBtn.querySelector('.btn-text').textContent = 'Processing SRT Batch...';
            srtProcessBtn.querySelector('.loader').style.display = 'block';
            if (progressArea && progressText) {
                progressArea.style.display = 'block';
                progressText.textContent = `Processing 0 of ${toProcess.length}...`;
            }

            const total = toProcess.length;
            let current = 0;

            try {
                for (const srtItem of srtQueue) {
                    if (srtItem.status === 'completed' || srtItem.status === 'processing') continue;
                    current += 1;
                    if (progressArea && progressText) {
                        progressText.textContent = `Processing ${current} of ${total}: ${srtItem.file.name}`;
                    }
                    await processSingleSrt(srtItem, (msg) => {
                        if (progressText) progressText.textContent = `[${current}/${total}] ${msg}`;
                    });
                }
            } finally {
                srtProcessBtn.querySelector('.btn-text').textContent = 'Translate SRT Files';
                srtProcessBtn.querySelector('.loader').style.display = 'none';
                srtProcessBtn.disabled = false;
                if (progressArea) progressArea.style.display = 'none';
                updateSrtUIState();
            }
        });
    }

    /**
     * @param {{ file: File, id: string, status: string, results: Array|null }} video
     * @param {(msg: string) => void} [onProgress] Optional callback for global progress text.
     */
    async function processSingleVideo(video, onProgress) {
        const itemEl = document.getElementById(`video-${video.id}`);
        const progressEl = document.getElementById(`progress-${video.id}`);
        const resultsEl = document.getElementById(`results-${video.id}`);
        if (!itemEl || !progressEl || !resultsEl) return;

        const sourceSelect = itemEl.querySelector('.source-lang-select');
        const targetSelect = itemEl.querySelector('.target-lang-select');
        const videoModelSelect = itemEl.querySelector('.video-model-select');
        const videoPromptInput = itemEl.querySelector('.video-prompt-input');

        video.status = 'processing';
        progressEl.style.display = 'block';
        resultsEl.style.display = 'none';
        sourceSelect.disabled = true;
        targetSelect.disabled = true;

        const formData = new FormData();
        formData.append('file', video.file);
        formData.append('source_language', sourceSelect.value);
        formData.append('target_language', targetSelect.value);
        const batchModel = modelSelect ? modelSelect.value : 'auto';
        const batchPrompt = promptInput ? promptInput.value : '';
        if (videoModelSelect && videoModelSelect.value !== 'batch') {
            formData.append('whisper_model', videoModelSelect.value);
        } else if (batchModel) {
            formData.append('whisper_model', batchModel);
        }
        const promptValue = videoPromptInput && videoPromptInput.value.trim().length > 0
            ? videoPromptInput.value.trim()
            : batchPrompt;
        if (promptValue) {
            formData.append('whisper_prompt', promptValue);
        }

        try {
            const response = await fetch('/upload_and_process', { method: 'POST', body: formData });
            if (!response.ok) throw new Error('Upload failed');

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() ?? '';

                for (const line of lines) {
                    if (!line.trim()) continue;
                    let data;
                    try {
                        data = JSON.parse(line);
                    } catch (_) {
                        continue;
                    }
                    if (data.type === 'progress') {
                        progressEl.textContent = data.message;
                        if (onProgress && data.message) onProgress(data.message);
                    } else if (data.type === 'result') {
                        video.status = 'completed';
                        video.results = data.files;
                        displayVideoResults(video);
                        progressEl.style.display = 'none';
                    } else if (data.type === 'error') {
                        throw new Error(data.message || 'Processing failed');
                    }
                }
            }
        } catch (error) {
            console.error(error);
            video.status = 'error';
            progressEl.textContent = `Error: ${error.message}`;
            progressEl.style.display = 'block';
            sourceSelect.disabled = false;
            targetSelect.disabled = false;
            alert(`Processing failed:\n${error.message}`);
        }
    }

    async function processSingleSrt(srtItem, onProgress) {
        const itemEl = document.getElementById(`srt-${srtItem.id}`);
        const progressEl = document.getElementById(`progress-srt-${srtItem.id}`);
        const resultsEl = document.getElementById(`results-srt-${srtItem.id}`);
        if (!itemEl || !progressEl || !resultsEl) return;

        const sourceSelect = itemEl.querySelector('.srt-source-select');
        const targetSelect = itemEl.querySelector('.srt-target-select');

        srtItem.status = 'processing';
        progressEl.style.display = 'block';
        resultsEl.style.display = 'none';
        sourceSelect.disabled = true;
        targetSelect.disabled = true;

        const formData = new FormData();
        formData.append('file', srtItem.file);
        formData.append('source_language', sourceSelect.value);
        formData.append('target_language', targetSelect.value);

        try {
            const response = await fetch('/upload_srt_and_translate', { method: 'POST', body: formData });
            if (!response.ok) throw new Error('Upload failed');

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() ?? '';

                for (const line of lines) {
                    if (!line.trim()) continue;
                    let data;
                    try {
                        data = JSON.parse(line);
                    } catch (_) {
                        continue;
                    }
                    if (data.type === 'progress') {
                        progressEl.textContent = data.message;
                        if (onProgress && data.message) onProgress(data.message);
                    } else if (data.type === 'result') {
                        srtItem.status = 'completed';
                        srtItem.results = data.files;
                        displaySrtResults(srtItem);
                        progressEl.style.display = 'none';
                    } else if (data.type === 'error') {
                        throw new Error(data.message || 'Processing failed');
                    }
                }
            }
        } catch (error) {
            console.error(error);
            srtItem.status = 'error';
            progressEl.textContent = `Error: ${error.message}`;
            progressEl.style.display = 'block';
            sourceSelect.disabled = false;
            targetSelect.disabled = false;
            alert(`Processing failed:\n${error.message}`);
        }
    }

    function displayVideoResults(video) {
        const resultsEl = document.getElementById(`results-${video.id}`);
        if (!resultsEl || !video.results) return;

        resultsEl.style.display = 'block';
        let html = `
            <div class="download-dropdown" id="dropdown-${video.id}">
                <button class="dropdown-toggle" type="button" style="width: 100%; justify-content: space-between;">
                    <span><i class="fa-solid fa-download"></i> Get Files</span>
                    <i class="fa-solid fa-chevron-down"></i>
                </button>
                <div class="dropdown-menu">
        `;
        video.results.forEach((file) => {
            html += `<a href="${escapeHtml(file.url)}" download><i class="fa-solid fa-file-arrow-down"></i> ${escapeHtml(file.label)}</a>`;
        });
        html += '</div></div>';
        resultsEl.innerHTML = html;

        const dropdown = resultsEl.querySelector('.download-dropdown');
        const toggle = dropdown.querySelector('.dropdown-toggle');
        const itemEl = document.getElementById(`video-${video.id}`);

        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            const wasActive = dropdown.classList.contains('show-dropdown');
            document.querySelectorAll('.download-dropdown').forEach((d) => d.classList.remove('show-dropdown'));
            document.querySelectorAll('.video-item').forEach((item) => item.classList.remove('is-active'));
            if (!wasActive) {
                dropdown.classList.add('show-dropdown');
                if (itemEl) itemEl.classList.add('is-active');
            }
        });
    }

    function displaySrtResults(srtItem) {
        const resultsEl = document.getElementById(`results-srt-${srtItem.id}`);
        if (!resultsEl || !srtItem.results) return;

        resultsEl.style.display = 'block';
        let html = `
            <div class="download-dropdown" id="dropdown-srt-${srtItem.id}">
                <button class="dropdown-toggle" type="button" style="width: 100%; justify-content: space-between;">
                    <span><i class="fa-solid fa-download"></i> Get Files</span>
                    <i class="fa-solid fa-chevron-down"></i>
                </button>
                <div class="dropdown-menu">
        `;
        srtItem.results.forEach((file) => {
            html += `<a href="${escapeHtml(file.url)}" download><i class="fa-solid fa-file-arrow-down"></i> ${escapeHtml(file.label)}</a>`;
        });
        html += '</div></div>';
        resultsEl.innerHTML = html;

        const dropdown = resultsEl.querySelector('.download-dropdown');
        const toggle = dropdown.querySelector('.dropdown-toggle');
        const itemEl = document.getElementById(`srt-${srtItem.id}`);

        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            const wasActive = dropdown.classList.contains('show-dropdown');
            document.querySelectorAll('.download-dropdown').forEach((d) => d.classList.remove('show-dropdown'));
            document.querySelectorAll('.video-item').forEach((item) => item.classList.remove('is-active'));
            if (!wasActive) {
                dropdown.classList.add('show-dropdown');
                if (itemEl) itemEl.classList.add('is-active');
            }
        });
    }

    document.addEventListener('click', () => {
        document.querySelectorAll('.download-dropdown').forEach((d) => d.classList.remove('show-dropdown'));
        document.querySelectorAll('.video-item').forEach((item) => item.classList.remove('is-active'));
    });

    clearBtn.addEventListener('click', async () => {
        if (!confirm('Clear all uploaded files and generated subtitles from the server? This cannot be undone.')) return;
        const response = await fetch('/clear_history', { method: 'POST' });
        if (response.ok) {
            videoQueue = [];
            videoList.innerHTML = '';
            updateUIState();
            alert('History cleared.');
        } else {
            const err = await response.json().catch(() => ({}));
            alert(err.error || 'Failed to clear history.');
        }
    });
});
