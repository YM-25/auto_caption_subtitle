/**
 * AutoCaption Pro — batch video upload, processing, and download.
 * Consumes NDJSON stream from /upload_and_process; parses lines safely.
 */

document.addEventListener('DOMContentLoaded', () => {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const videoList = document.getElementById('video-list');
    const globalActions = document.getElementById('global-actions');
    const processBtn = document.getElementById('process-btn');
    const clearBtn = document.getElementById('clear-btn');
    const uploadContent = document.querySelector('.upload-content');
    const progressArea = document.getElementById('progress-area');
    const progressText = document.getElementById('progress-text');

    /** @type {{ file: File, id: string, status: string, results: Array<{label:string,url:string}>|null }[]} */
    let videoQueue = [];

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

    function addVideoToUI(video) {
        const item = document.createElement('div');
        item.className = 'video-item';
        item.id = `video-${video.id}`;
        const safeName = escapeHtml(video.file.name);
        item.innerHTML = `
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
            <div class="video-progress" id="progress-${video.id}">Waiting for processing...</div>
            <div class="video-results" id="results-${video.id}"></div>
            <i class="fa-solid fa-xmark remove-video-btn" data-id="${video.id}" title="Remove Video"></i>
        `;

        item.querySelector('.remove-video-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            removeVideo(video.id);
        });

        videoList.appendChild(item);
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

        video.status = 'processing';
        progressEl.style.display = 'block';
        resultsEl.style.display = 'none';
        sourceSelect.disabled = true;
        targetSelect.disabled = true;

        const formData = new FormData();
        formData.append('file', video.file);
        formData.append('source_language', sourceSelect.value);
        formData.append('target_language', targetSelect.value);

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
