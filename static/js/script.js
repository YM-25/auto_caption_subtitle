document.addEventListener('DOMContentLoaded', () => {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const fileInfo = document.getElementById('file-info');
    const filenameSpan = document.getElementById('filename');
    const removeBtn = document.getElementById('remove-file');
    const processBtn = document.getElementById('process-btn');
    const sourceLangSelect = document.getElementById('source-language-select');
    const targetLangSelect = document.getElementById('target-language-select');
    const resultsArea = document.getElementById('results-area');
    const uploadContent = document.querySelector('.upload-content');
    const progressArea = document.getElementById('progress-area');
    const progressText = document.getElementById('progress-text');

    let currentFile = null;

    // Drag & Drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => uploadArea.classList.add('drag-over'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => uploadArea.classList.remove('drag-over'), false);
    });

    uploadArea.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    // Click to upload
    uploadArea.addEventListener('click', (e) => {
        if (e.target !== removeBtn) {
            fileInput.click();
        }
    });

    fileInput.addEventListener('change', () => handleFiles(fileInput.files));

    function handleFiles(files) {
        if (files.length > 0) {
            currentFile = files[0];
            showFile(currentFile);
        }
    }

    function showFile(file) {
        filenameSpan.textContent = file.name;
        fileInfo.style.display = 'flex';
        uploadContent.style.display = 'none';
        processBtn.disabled = false;
        resultsArea.innerHTML = '';
        progressArea.style.display = 'none';
    }

    removeBtn.addEventListener('click', () => {
        currentFile = null;
        fileInput.value = '';
        fileInfo.style.display = 'none';
        uploadContent.style.display = 'block';
        processBtn.disabled = true;
        progressArea.style.display = 'none';
    });

    // Process with Stream support
    processBtn.addEventListener('click', async () => {
        if (!currentFile) return;

        // UI Loading State
        processBtn.disabled = true;
        processBtn.querySelector('.btn-text').textContent = "Processing...";
        processBtn.querySelector('.loader').style.display = 'block';
        resultsArea.innerHTML = '';
        progressArea.style.display = 'block';
        progressText.textContent = "Initiating upload...";

        const formData = new FormData();
        formData.append('file', currentFile);
        formData.append('source_language', sourceLangSelect.value);
        formData.append('target_language', targetLangSelect.value);

        try {
            const response = await fetch('/upload_and_process', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const text = await response.text();
                let message = 'Upload failed';
                try {
                    const errorData = JSON.parse(text);
                    if (errorData && errorData.error) message = errorData.error;
                } catch (_) {
                    if (text) message = text.slice(0, 200);
                }
                throw new Error(message);
            }

            // Read the stream
            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');

                // Process all complete lines
                buffer = lines.pop(); // Keep the last partial line in buffer

                for (const line of lines) {
                    if (!line.trim()) continue;

                    try {
                        const data = JSON.parse(line);

                        if (data.type === 'progress') {
                            progressText.textContent = data.message;
                        }
                        else if (data.type === 'result') {
                            displayResults(data.files);
                            progressText.textContent = "Done!";
                        }
                        else if (data.type === 'error') {
                            alert('Error: ' + data.message);
                            progressText.textContent = "Error occurred.";
                        }
                    } catch (e) {
                        console.error('Error parsing JSON chunk', e);
                    }
                }
            }

        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred: ' + error.message);
            progressText.textContent = "Failed.";
        } finally {
            // Reset UI
            processBtn.disabled = false;
            processBtn.querySelector('.btn-text').textContent = "Generate Subtitles";
            processBtn.querySelector('.loader').style.display = 'none';
        }
    });

    function displayResults(files) {
        resultsArea.innerHTML = '';
        if (files.length === 0) return;

        files.forEach((file, index) => {
            const item = document.createElement('div');
            item.className = 'result-item';
            item.style.animationDelay = `${index * 0.1}s`;

            item.innerHTML = `
                <span><i class="fa-solid fa-file-contract"></i> ${file.label}</span>
                <a href="${file.url}" class="download-link" download><i class="fa-solid fa-download"></i> Download</a>
            `;

            resultsArea.appendChild(item);
        });
    }

    // Clear History
    const clearBtn = document.getElementById('clear-btn');
    clearBtn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to delete all uploaded videos and generated subtitles? This cannot be undone.')) {
            return;
        }

        try {
            const response = await fetch('/clear_history', { method: 'POST' });
            if (response.ok) {
                alert('History cleared successfully.');
                // Reset UI
                if (currentFile) removeBtn.click();
                resultsArea.innerHTML = '';
            } else {
                alert('Failed to clear history.');
            }
        } catch (error) {
            console.error('Error clearing history:', error);
            alert('Error clearing history.');
        }
    });
});
