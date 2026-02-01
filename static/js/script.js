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
    const pauseAllBtn = document.getElementById('pause-all-btn');
    const resumeAllBtn = document.getElementById('resume-all-btn');
    const glossaryText = document.getElementById('glossary-text');
    const glossaryUseSaved = document.getElementById('glossary-use-saved');
    const glossaryUseFilename = document.getElementById('glossary-use-filename');
    const glossaryFile = document.getElementById('glossary-file');
    const glossaryPreviewInput = document.getElementById('glossary-preview-input');
    const glossarySaveNow = document.getElementById('glossary-save-now');
    const glossaryPreviewContent = document.getElementById('glossary-preview-content');
    const logModal = document.getElementById('log-modal');
    const logModalContent = document.getElementById('log-modal-content');
    const logModalDownload = document.getElementById('log-modal-download');
    const logModalClose = document.getElementById('log-modal-close');
    const logModalDismiss = document.getElementById('log-modal-dismiss');
    const logModalBackdrop = document.getElementById('log-modal-backdrop');

    // AI Service elements
    const aiProvider = document.getElementById('ai-provider');
    const aiModel = document.getElementById('ai-model');
    const aiApiKey = document.getElementById('ai-api-key');
    const aiEnableExpansion = document.getElementById('ai-enable-expansion');
    const aiEnableTranslation = document.getElementById('ai-enable-translation');
    const aiEnableTranslationSrt = document.getElementById('ai-enable-translation-srt');
    const aiStatusBadge = document.getElementById('ai-status-badge');
    const aiProviderIcon = document.getElementById('ai-provider-icon');
    const aiKeyHint = document.getElementById('ai-key-hint');

    /** @type {{ file: File, id: string, status: string, results: Array<{label:string,url:string}>|null, log: {download_url:string, preview_url:string}|null }[]} */
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
    /** @type {{ file: File, id: string, status: string, results: Array<{label:string,url:string}>|null, log: {download_url:string, preview_url:string}|null }[]} */
    let srtQueue = [];
    let queuePaused = false;
    let resumeQueueResolve = null;

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

    if (aiEnableTranslation && aiEnableTranslationSrt) {
        aiEnableTranslation.addEventListener('change', () => {
            aiEnableTranslationSrt.checked = aiEnableTranslation.checked;
            saveAiSettings();
        });
        aiEnableTranslationSrt.addEventListener('change', () => {
            aiEnableTranslation.checked = aiEnableTranslationSrt.checked;
            saveAiSettings();
        });
    }

    function setQueuePaused(paused) {
        queuePaused = paused;
        if (pauseAllBtn && resumeAllBtn) {
            pauseAllBtn.style.display = paused ? 'none' : 'inline-flex';
            resumeAllBtn.style.display = paused ? 'inline-flex' : 'none';
        }
        if (!paused && resumeQueueResolve) {
            resumeQueueResolve();
            resumeQueueResolve = null;
        }
    }

    async function waitForResume() {
        if (!queuePaused) return;
        await new Promise((resolve) => {
            resumeQueueResolve = resolve;
        });
    }

    if (pauseAllBtn) {
        pauseAllBtn.addEventListener('click', () => {
            setQueuePaused(true);
            videoQueue.forEach((video) => {
                if (video.status === 'pending') {
                    video.status = 'paused';
                    const itemEl = document.getElementById(`video-${video.id}`);
                    if (itemEl) {
                        const pauseBtn = itemEl.querySelector('.pause-btn');
                        const resumeBtn = itemEl.querySelector('.resume-btn');
                        if (pauseBtn) pauseBtn.style.display = 'none';
                        if (resumeBtn) resumeBtn.style.display = 'inline-flex';
                    }
                }
            });
            updateUIState();
        });
    }

    if (resumeAllBtn) {
        resumeAllBtn.addEventListener('click', () => {
            setQueuePaused(false);
            videoQueue.forEach((video) => {
                if (video.status === 'paused') {
                    video.status = 'pending';
                    const itemEl = document.getElementById(`video-${video.id}`);
                    if (itemEl) {
                        const pauseBtn = itemEl.querySelector('.pause-btn');
                        const resumeBtn = itemEl.querySelector('.resume-btn');
                        if (pauseBtn) pauseBtn.style.display = 'inline-flex';
                        if (resumeBtn) resumeBtn.style.display = 'none';
                    }
                }
            });
            updateUIState();
        });
    }

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
                log: null,
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
                log: null,
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
                            <option value="ru">Russian</option>
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
                            <option value="ru">Russian</option>
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
                    <label>Initial Prompt (append for this video):</label>
                    <textarea class="video-prompt-input" rows="2" placeholder="Optional: names, places, terms"></textarea>
                    <label class="checkbox-row">
                        <input type="checkbox" class="video-infer-checkbox" data-default="batch">
                        Infer keywords from filename (use batch by default)
                    </label>
                </div>
                <div class="setting-group">
                    <label>Glossary (append for this video):</label>
                    <textarea class="video-glossary-input" rows="2" placeholder="term = translation"></textarea>
                    <label class="checkbox-row">
                        <input type="checkbox" class="video-glossary-save">
                        Save this glossary to saved list
                    </label>
                </div>
            </div>
            <div class="video-actions-row">
                <button class="pause-btn" type="button"><i class="fa-solid fa-pause"></i> Pause</button>
                <button class="resume-btn" type="button" style="display:none;"><i class="fa-solid fa-play"></i> Resume</button>
                <button class="retry-btn" type="button"><i class="fa-solid fa-rotate-right"></i> Retry</button>
                <button class="top-btn" type="button"><i class="fa-solid fa-arrow-up"></i> Move to Top</button>
            </div>
            <div class="video-progress" id="progress-${video.id}">Waiting for processing...</div>
            <div class="video-results" id="results-${video.id}"></div>
            <button class="log-button" id="log-${video.id}" type="button" style="display:none;">View Log</button>
        `;

        const toggle = item.querySelector('.video-advanced-toggle');
        const advancedFields = item.querySelector('.video-advanced-fields');
        const videoModelSelect = item.querySelector('.video-model-select');
        const videoInferCheckbox = item.querySelector('.video-infer-checkbox');
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

        if (videoInferCheckbox) {
            videoInferCheckbox.indeterminate = true;
            videoInferCheckbox.dataset.mode = 'batch';
            videoInferCheckbox.addEventListener('change', () => {
                videoInferCheckbox.indeterminate = false;
                videoInferCheckbox.dataset.mode = 'override';
            });
        }

        const pauseBtn = item.querySelector('.pause-btn');
        const resumeBtn = item.querySelector('.resume-btn');
        const retryBtn = item.querySelector('.retry-btn');
        const topBtn = item.querySelector('.top-btn');

        if (pauseBtn) {
            pauseBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (video.status === 'processing') {
                    setQueuePaused(true);
                    const progressEl = document.getElementById(`progress-${video.id}`);
                    if (progressEl) progressEl.textContent = 'Pause requested. Will stop after current item.';
                } else if (video.status !== 'completed') {
                    video.status = 'paused';
                    pauseBtn.style.display = 'none';
                    if (resumeBtn) resumeBtn.style.display = 'inline-flex';
                }
                updateUIState();
            });
        }

        if (resumeBtn) {
            resumeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (video.status === 'paused') {
                    video.status = 'pending';
                    resumeBtn.style.display = 'none';
                    if (pauseBtn) pauseBtn.style.display = 'inline-flex';
                    updateUIState();
                }
            });
        }

        if (retryBtn) {
            retryBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (video.status === 'failed') {
                    video.status = 'pending';
                    video.results = null;
                    video.log = null;
                    const resultsEl = document.getElementById(`results-${video.id}`);
                    if (resultsEl) resultsEl.innerHTML = '';
                    const logBtn = document.getElementById(`log-${video.id}`);
                    if (logBtn) logBtn.style.display = 'none';
                    updateUIState();
                }
            });
        }

        if (topBtn) {
            topBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                moveVideoToTop(video.id);
            });
        }

        const logBtn = item.querySelector(`#log-${video.id}`);
        if (logBtn) {
            logBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (video.log) {
                    openLogModal(video.log.preview_url, video.log.download_url);
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
                        <option value="ru">Russian</option>
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
                        <option value="ru">Russian</option>
                    </select>
                </div>
            </div>
            <div class="video-progress" id="progress-srt-${srtItem.id}">Waiting for processing...</div>
            <div class="video-results" id="results-srt-${srtItem.id}"></div>
            <button class="log-button" id="log-srt-${srtItem.id}" type="button" style="display:none;">View Log</button>
            <i class="fa-solid fa-xmark remove-video-btn" data-id="${srtItem.id}" title="Remove SRT"></i>
        `;

        const logBtn = item.querySelector(`#log-srt-${srtItem.id}`);
        if (logBtn) {
            logBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (srtItem.log) {
                    openLogModal(srtItem.log.preview_url, srtItem.log.download_url);
                }
            });
        }

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

    function moveVideoToTop(id) {
        const index = videoQueue.findIndex((v) => v.id === id);
        if (index <= 0) return;
        const [item] = videoQueue.splice(index, 1);
        videoQueue.unshift(item);
        const el = document.getElementById(`video-${id}`);
        if (el && videoList) {
            videoList.prepend(el);
        }
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
            processBtn.disabled = videoQueue.every((v) => v.status === 'completed' || v.status === 'paused');
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
        const toProcess = videoQueue.filter((v) => v.status !== 'completed' && v.status !== 'processing' && v.status !== 'paused');
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
                if (video.status === 'paused') continue;
                if (queuePaused) {
                    if (progressArea && progressText) {
                        progressText.textContent = 'Queue paused. Waiting to resume...';
                    }
                    await waitForResume();
                }
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
        const videoInferCheckbox = itemEl.querySelector('.video-infer-checkbox');
        const videoGlossaryInput = itemEl.querySelector('.video-glossary-input');
        const videoGlossarySave = itemEl.querySelector('.video-glossary-save');

        video.status = 'processing';
        progressEl.style.display = 'block';
        resultsEl.style.display = 'none';
        sourceSelect.disabled = true;
        targetSelect.disabled = true;

        const formData = new FormData();
        formData.append('file', video.file);
        formData.append('source_language', sourceSelect.value);
        formData.append('target_language', targetSelect.value);
        const globalGlossaryText = glossaryText ? glossaryText.value : '';
        const videoGlossaryText = videoGlossaryInput ? videoGlossaryInput.value : '';
        const combinedGlossary = [globalGlossaryText, videoGlossaryText].filter((v) => v && v.trim()).join('\n');
        formData.append('glossary_text', combinedGlossary);
        formData.append('glossary_use_saved', glossaryUseSaved && glossaryUseSaved.checked ? '1' : '0');
        formData.append('glossary_save', videoGlossarySave && videoGlossarySave.checked ? '1' : '0');
        if (videoGlossarySave && videoGlossarySave.checked) {
            formData.append('glossary_save_text', videoGlossaryText);
        }
        if (videoInferCheckbox && videoInferCheckbox.dataset.mode === 'override') {
            formData.append('glossary_use_filename', videoInferCheckbox.checked ? '1' : '0');
        } else if (videoInferCheckbox) {
            formData.append('glossary_use_filename', glossaryUseFilename && glossaryUseFilename.checked ? '1' : '0');
        } else {
            formData.append('glossary_use_filename', glossaryUseFilename && glossaryUseFilename.checked ? '1' : '0');
        }
        if (glossaryFile && glossaryFile.files && glossaryFile.files[0]) {
            formData.append('glossary_file', glossaryFile.files[0]);
        }

        // AI Services
        if (aiProvider) formData.append('ai_provider', aiProvider.value);
        if (aiModel) formData.append('ai_model', aiModel.value);
        if (aiApiKey) formData.append('ai_api_key', aiApiKey.value.trim());
        if (aiEnableExpansion) formData.append('ai_enable_expansion', aiEnableExpansion.checked ? '1' : '0');
        if (aiEnableTranslation) formData.append('ai_enable_translation', aiEnableTranslation.checked ? '1' : '0');
        const batchModel = modelSelect ? modelSelect.value : 'auto';
        const batchPrompt = promptInput ? (promptInput.value || '').trim() : '';
        if (videoModelSelect && videoModelSelect.value !== 'batch') {
            formData.append('whisper_model', videoModelSelect.value);
        } else if (batchModel) {
            formData.append('whisper_model', batchModel);
        }

        const videoPrompt = videoPromptInput ? (videoPromptInput.value || '').trim() : '';
        let finalPrompt = '';
        if (batchPrompt && videoPrompt) {
            finalPrompt = `${batchPrompt}\n${videoPrompt}`;
        } else {
            finalPrompt = videoPrompt || batchPrompt;
        }

        if (finalPrompt) {
            formData.append('whisper_prompt', finalPrompt);
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
                        if (data.log) {
                            video.log = data.log;
                            showLogButton(video.id);
                        }
                        displayVideoResults(video);
                        progressEl.style.display = 'none';
                    } else if (data.type === 'error') {
                        if (data.log) {
                            video.log = data.log;
                            showLogButton(video.id);
                            openLogModal(data.log.preview_url, data.log.download_url);
                        }
                        throw new Error(data.message || 'Processing failed');
                    }
                }
            }
        } catch (error) {
            console.error(error);
            video.status = 'failed';
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
        formData.append('glossary_text', glossaryText ? glossaryText.value : '');
        formData.append('glossary_use_saved', glossaryUseSaved && glossaryUseSaved.checked ? '1' : '0');
        formData.append('glossary_use_filename', glossaryUseFilename && glossaryUseFilename.checked ? '1' : '0');

        // AI Services
        if (aiProvider) formData.append('ai_provider', aiProvider.value);
        if (aiModel) formData.append('ai_model', aiModel.value);
        if (aiApiKey) formData.append('ai_api_key', aiApiKey.value.trim());
        if (aiEnableTranslationSrt) formData.append('ai_enable_translation', aiEnableTranslationSrt.checked ? '1' : '0');
        else if (aiEnableTranslation) formData.append('ai_enable_translation', aiEnableTranslation.checked ? '1' : '0');
        if (glossaryFile && glossaryFile.files && glossaryFile.files[0]) {
            formData.append('glossary_file', glossaryFile.files[0]);
        }

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
                        if (data.log) {
                            srtItem.log = data.log;
                            showLogButton(`srt-${srtItem.id}`);
                        }
                        displaySrtResults(srtItem);
                        progressEl.style.display = 'none';
                    } else if (data.type === 'error') {
                        if (data.log) {
                            srtItem.log = data.log;
                            showLogButton(`srt-${srtItem.id}`);
                            openLogModal(data.log.preview_url, data.log.download_url);
                        }
                        throw new Error(data.message || 'Processing failed');
                    }
                }
            }
        } catch (error) {
            console.error(error);
            srtItem.status = 'failed';
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

    function showLogButton(id) {
        const btn = document.getElementById(`log-${id}`);
        if (btn) {
            btn.style.display = 'inline-flex';
        }
    }

    function openLogModal(previewUrl, downloadUrl) {
        if (!logModal || !logModalContent) return;
        logModal.classList.add('active');
        logModal.setAttribute('aria-hidden', 'false');
        logModalContent.textContent = 'Loading...';
        if (logModalDownload) {
            logModalDownload.onclick = () => {
                window.open(downloadUrl, '_blank');
            };
        }
        fetch(previewUrl)
            .then((res) => res.text())
            .then((text) => {
                logModalContent.textContent = text;
            })
            .catch(() => {
                logModalContent.textContent = 'Failed to load log preview.';
            });
    }

    function closeLogModal() {
        if (!logModal) return;
        logModal.classList.remove('active');
        logModal.setAttribute('aria-hidden', 'true');
    }

    if (logModalClose) logModalClose.addEventListener('click', closeLogModal);
    if (logModalDismiss) logModalDismiss.addEventListener('click', closeLogModal);
    if (logModalBackdrop) logModalBackdrop.addEventListener('click', closeLogModal);

    function normalizeGlossaryDict(dict) {
        const normalized = {};
        Object.entries(dict || {}).forEach(([key, value]) => {
            const term = String(key || '').trim();
            if (!term) return;
            normalized[term] = String(value || '').trim() || term;
        });
        return normalized;
    }

    function parseGlossaryTextToDict(text) {
        const dict = {};
        if (!text) return dict;
        text.split(/\r?\n/).forEach((line) => {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#')) return;
            if (trimmed.includes('->')) {
                const [src, tgt] = trimmed.split('->', 2);
                const term = src.trim();
                const val = (tgt || '').trim();
                if (term) dict[term] = val || term;
                return;
            }
            if (trimmed.includes('=')) {
                const [src, tgt] = trimmed.split('=', 2);
                const term = src.trim();
                const val = (tgt || '').trim();
                if (term) dict[term] = val || term;
            }
        });
        return dict;
    }

    function parseGlossaryJsonToDict(jsonText) {
        try {
            const data = JSON.parse(jsonText);
            if (Array.isArray(data)) {
                const dict = {};
                data.forEach((item) => {
                    if (!item || typeof item !== 'object') return;
                    const term = String(item.term || '').trim();
                    const translation = String(item.translation || '').trim();
                    if (term) dict[term] = translation || term;
                });
                return dict;
            }
            if (data && typeof data === 'object') {
                return data;
            }
        } catch (_) {
            return {};
        }
        return {};
    }

    async function buildGlossaryInputDict() {
        let dict = {};
        if (glossaryText && glossaryText.value.trim()) {
            dict = { ...dict, ...parseGlossaryTextToDict(glossaryText.value) };
        }
        if (glossaryFile && glossaryFile.files && glossaryFile.files[0]) {
            const file = glossaryFile.files[0];
            const text = await file.text();
            if (file.name.toLowerCase().endsWith('.json')) {
                dict = { ...dict, ...parseGlossaryJsonToDict(text) };
            } else {
                dict = { ...dict, ...parseGlossaryTextToDict(text) };
            }
        }
        return normalizeGlossaryDict(dict);
    }

    let glossaryInputUrl = null;

    async function refreshGlossaryInputLink() {
        if (!glossaryPreviewInput) return;
        const dict = await buildGlossaryInputDict();
        const jsonText = JSON.stringify(dict, null, 2);
        if (glossaryInputUrl) {
            URL.revokeObjectURL(glossaryInputUrl);
        }
        const blob = new Blob([jsonText || '{}'], { type: 'application/json;charset=utf-8' });
        glossaryInputUrl = URL.createObjectURL(blob);
        glossaryPreviewInput.href = glossaryInputUrl;
    }

    if (glossaryText) {
        glossaryText.addEventListener('input', () => {
            refreshGlossaryInputLink();
        });
    }

    if (glossaryFile) {
        glossaryFile.addEventListener('change', () => {
            refreshGlossaryInputLink();
        });
    }

    refreshGlossaryInputLink();

    async function refreshSavedGlossaryPreview() {
        if (!glossaryPreviewContent) return;
        try {
            const res = await fetch('/glossary/preview');
            if (!res.ok) {
                glossaryPreviewContent.textContent = '{}';
                return;
            }
            const text = await res.text();
            glossaryPreviewContent.textContent = text || '{}';
        } catch (_) {
            glossaryPreviewContent.textContent = '{}';
        }
    }

    refreshSavedGlossaryPreview();

    if (glossarySaveNow) {
        glossarySaveNow.addEventListener('click', async () => {
            const formData = new FormData();
            formData.append('glossary_text', glossaryText ? glossaryText.value : '');
            if (glossaryFile && glossaryFile.files && glossaryFile.files[0]) {
                formData.append('glossary_file', glossaryFile.files[0]);
            }
            try {
                const res = await fetch('/glossary/save', { method: 'POST', body: formData });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    throw new Error(data.error || 'Failed to save glossary');
                }
                alert(`Saved glossary. Total terms: ${data.total_terms || 0}.`);
                refreshSavedGlossaryPreview();
            } catch (err) {
                alert(`Glossary save failed: ${err.message}`);
            }
        });
    }

    document.addEventListener('click', () => {
        document.querySelectorAll('.download-dropdown').forEach((d) => d.classList.remove('show-dropdown'));
        document.querySelectorAll('.video-item').forEach((item) => item.classList.remove('is-active'));
    });

    // --- AI Persistence & Dynamic Options ---
    const AI_MODELS = {
        gemini: [
            { value: 'gemini-3-flash', label: 'gemini-3-flash (2026 Default)' },
            { value: 'gemini-3-pro', label: 'gemini-3-pro (High Quality)' },
            { value: 'gemini-2.5-flash-lite', label: 'gemini-2.5-flash-lite (Economy)' },
            { value: 'gemini-1.5-flash', label: 'gemini-1.5-flash (Legacy)' },
        ],
        chatgpt: [
            { value: 'gpt-5-mini', label: 'gpt-5-mini (2026 Default)' },
            { value: 'gpt-5.2', label: 'gpt-5.2 (High Quality)' },
            { value: 'gpt-4o-mini', label: 'gpt-4o-mini (Legacy Economic)' },
            { value: 'gpt-3.5-turbo', label: 'gpt-3.5-turbo (Legacy)' },
        ],
    };

    function updateAiModelOptions() {
        if (!aiProvider || !aiModel) return;
        const provider = aiProvider.value;
        const models = AI_MODELS[provider] || [];
        const currentVal = aiModel.value;
        aiModel.innerHTML = models.map((m) => `<option value="${m.value}">${m.label}</option>`).join('');

        // If current model is not for this provider or it's first load, pick first (default)
        if (!models.some((m) => m.value === currentVal)) {
            aiModel.value = models[0]?.value || '';
        }
    }

    function saveAiSettings() {
        const provider = aiProvider?.value;
        const currentSettings = JSON.parse(localStorage.getItem('autocaption_ai_settings') || '{}');
        const keys = currentSettings.keys || { gemini: '', chatgpt: '' };

        // Update the key for the CURRENT provider
        if (provider) keys[provider] = aiApiKey?.value || '';

        const settings = {
            provider: provider,
            model: aiModel?.value,
            keys: keys,
            enableExpansion: aiEnableExpansion?.checked,
            enableTranslation: aiEnableTranslation?.checked,
        };
        localStorage.setItem('autocaption_ai_settings', JSON.stringify(settings));
        updateAiStatusUI();
    }

    const aiCheckKeyBtn = document.getElementById('ai-check-key-btn');

    function updateAiStatusUI() {
        if (!aiProvider || !aiStatusBadge || !aiProviderIcon || !aiKeyHint) return;
        const provider = aiProvider.value;
        const currentSettings = JSON.parse(localStorage.getItem('autocaption_ai_settings') || '{}');
        const keys = currentSettings.keys || { gemini: '', chatgpt: '' };
        const k = keys[provider] || '';

        // Validation logic
        const isFormatValid = validateApiKeyFormat(provider, k);

        // Status Badge
        if (!k.trim()) {
            aiStatusBadge.textContent = 'Missing';
            aiStatusBadge.className = 'status-badge missing';
        } else if (!isFormatValid) {
            aiStatusBadge.textContent = 'Format Error';
            aiStatusBadge.className = 'status-badge invalid';
        } else {
            // Check if it was already verified in this session or from storage
            const verifiedKeys = JSON.parse(sessionStorage.getItem('verified_keys') || '{}');
            if (verifiedKeys[provider] === k) {
                aiStatusBadge.textContent = 'Verified';
                aiStatusBadge.className = 'status-badge verified';
            } else {
                aiStatusBadge.textContent = 'Configured';
                aiStatusBadge.className = 'status-badge configured';
            }
        }

        // Provider Icon & Hint
        if (provider === 'gemini') {
            aiProviderIcon.className = 'fa-brands fa-google';
            aiKeyHint.textContent = '正在编辑 Google Gemini 的密钥';
        } else {
            aiProviderIcon.className = 'fa-solid fa-bolt';
            aiKeyHint.textContent = '正在编辑 OpenAI ChatGPT 的密钥';
        }

        // Sync input field if provider just changed
        if (aiApiKey && aiApiKey.value !== k) {
            aiApiKey.value = k;
        }

        // Enable/Disable check button
        if (aiCheckKeyBtn) {
            aiCheckKeyBtn.disabled = !k.trim() || !isFormatValid;
        }
    }

    function validateApiKeyFormat(provider, key) {
        if (!key) return false;
        if (provider === 'gemini') {
            // Gemini keys are usually around 39 chars, alphanumeric + underscores
            return key.length >= 30;
        } else if (provider === 'chatgpt') {
            // OpenAI keys start with sk- or proj-sk- or something similar
            return (key.startsWith('sk-') || key.includes('-sk-')) && key.length >= 20;
        }
        return true;
    }

    async function checkApiKey() {
        if (!aiProvider || !aiApiKey || !aiCheckKeyBtn || !aiStatusBadge) return;
        const provider = aiProvider.value;
        const key = aiApiKey.value;

        aiCheckKeyBtn.disabled = true;
        aiCheckKeyBtn.textContent = '...';
        aiStatusBadge.textContent = 'Verifying...';
        aiStatusBadge.className = 'status-badge verifying';

        try {
            const response = await fetch('/verify_api_key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider, api_key: key })
            });
            const data = await response.json();

            if (data.success) {
                aiStatusBadge.textContent = 'Verified';
                aiStatusBadge.className = 'status-badge verified';
                // Store verified status for this session
                const verifiedKeys = JSON.parse(sessionStorage.getItem('verified_keys') || '{}');
                verifiedKeys[provider] = key;
                sessionStorage.setItem('verified_keys', JSON.stringify(verifiedKeys));
            } else {
                aiStatusBadge.textContent = 'Invalid';
                aiStatusBadge.className = 'status-badge invalid';
                alert(`Verification failed: ${data.message}`);
            }
        } catch (err) {
            aiStatusBadge.textContent = 'Error';
            aiStatusBadge.className = 'status-badge invalid';
            alert('Network error during verification.');
        } finally {
            aiCheckKeyBtn.disabled = false;
            aiCheckKeyBtn.textContent = 'Check';
        }
    }

    if (aiCheckKeyBtn) {
        aiCheckKeyBtn.addEventListener('click', checkApiKey);
    }

    function loadAiSettings() {
        const raw = localStorage.getItem('autocaption_ai_settings');
        if (!raw) return;
        try {
            const s = JSON.parse(raw);
            if (aiProvider && s.provider) aiProvider.value = s.provider;
            updateAiModelOptions();
            if (aiModel && s.model) aiModel.value = s.model;

            // Load key for current provider
            const keys = s.keys || { gemini: '', chatgpt: '' };
            if (aiApiKey) aiApiKey.value = keys[aiProvider.value] || '';

            if (aiEnableExpansion && s.enableExpansion !== undefined) aiEnableExpansion.checked = s.enableExpansion;
            if (aiEnableTranslation && s.enableTranslation !== undefined) {
                aiEnableTranslation.checked = s.enableTranslation;
                if (aiEnableTranslationSrt) aiEnableTranslationSrt.checked = s.enableTranslation;
            }

            updateAiStatusUI();
        } catch (_) { }
    }

    if (aiProvider) {
        aiProvider.addEventListener('change', () => {
            updateAiModelOptions();
            updateAiStatusUI(); // This will also swap the key in the input
            saveAiSettings();
        });
    }
    [aiModel, aiApiKey, aiEnableExpansion, aiEnableTranslation, aiEnableTranslationSrt].forEach((el) => {
        el?.addEventListener('change', saveAiSettings);
        el?.addEventListener('input', saveAiSettings);
    });

    // Start
    loadAiSettings();

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
