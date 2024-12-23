const API_URL = 'http://127.0.0.1:8000';

let processingMonitorInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    const videoSelect = document.getElementById('video-select');
    loadVideoList();
    
    videoSelect.addEventListener('change', () => {
        console.log('Video seleccionado cambiado');
        checkExistingProcessedVideo();
        stopStreamSimulation();
    });
});

function loadVideoList() {
    fetch(`${API_URL}/videos/available-videos`)
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(data => {
            const select = document.getElementById('video-select');
            select.innerHTML = '<option value="">Seleccione un video</option>';
            
            if (data.videos && Array.isArray(data.videos)) {
                data.videos.forEach(video => {
                    const option = document.createElement('option');
                    option.value = video;
                    option.textContent = video;
                    select.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showError('Error al cargar la lista de videos: ' + error.message);
        });
}

async function processVideo() {
    const videoName = document.getElementById('video-select').value;
    if (!videoName) {
        showError('Seleccione un video');
        return;
    }

    try {
        // Limpiar estado anterior
        clearDisplays();
        
        // Iniciar procesamiento
        const response = await fetch(`${API_URL}/videos/process/${videoName}`);
        const data = await response.json();
        
        if (data.status === 'completed') {
            // Si ya está todo procesado, mostrar resultados
            await showResults(videoName);
            return;
        }
        
        // Iniciar monitoreo
        updateProgress(true, 0, 'Iniciando procesamiento...');
        await startProgressMonitoring(videoName);
        
    } catch (error) {
        console.error('Error:', error);
        showError(error.message);
        updateProgress(false);
    }
}

async function startProgressMonitoring(videoName) {
    if (processingMonitorInterval) {
        clearInterval(processingMonitorInterval);
    }
    
    let failedAttempts = 0;
    const maxFailedAttempts = 5;

    const checkStatus = async () => {
        try {
            const response = await fetch(`${API_URL}/videos/status/${videoName}`);
            const data = await response.json();

            if (data.status === 'error') {
                clearInterval(processingMonitorInterval);
                showError(data.message || 'Error en el procesamiento');
                updateProgress(false);
                return;
            }

            // Actualizar barra de progreso
            updateProgress(true, data.progress, getStepMessage(data.step));

            // Si el proceso está completo
            if (data.status === 'completed' && data.processed_video_path && data.heatmap_path) {
                clearInterval(processingMonitorInterval);
                await showResults(videoName);
                setTimeout(() => updateProgress(false), 2000);
                return;
            }

            failedAttempts = 0;

        } catch (error) {
            console.error('Error monitoreando estado:', error);
            failedAttempts++;
            
            if (failedAttempts >= maxFailedAttempts) {
                clearInterval(processingMonitorInterval);
                showError('Error de conexión al monitorear el proceso');
                updateProgress(false);
            }
        }
    };

    await checkStatus();
    processingMonitorInterval = setInterval(checkStatus, 1000);

    setTimeout(() => {
        if (processingMonitorInterval) {
            clearInterval(processingMonitorInterval);
            showError('Tiempo de espera agotado');
            updateProgress(false);
        }
    }, 300000); // 5 minutos timeout
}

async function showResults(videoName) {
    try {
        const response = await fetch(`${API_URL}/videos/status/${videoName}`);
        const data = await response.json();
        
        if (data.status !== 'completed') {
            throw new Error('Los archivos no están listos');
        }
        
        if (data.processed_video_path) {
            await showProcessedVideo(data.processed_video_path);
        }
        
        if (data.heatmap_path) {
            const heatmapContainer = document.getElementById('heatmap-container');
            heatmapContainer.innerHTML = `
                <img src="${API_URL}${data.heatmap_path}"
                     alt="Mapa de calor"
                     style="max-width: 100%; display: block; margin: 0 auto;">
            `;
        }
        
        await loadVideoObjects();
        
    } catch (error) {
        console.error('Error mostrando resultados:', error);
        showError(error.message);
    }
}

function updateProgress(show = true, progress = 0, message = '') {
    const progressContainer = document.getElementById('progress-container');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    
    if (!progressContainer || !progressFill || !progressText) {
        console.error('Elementos de progreso no encontrados');
        return;
    }
    
    progressContainer.style.display = show ? 'block' : 'none';
    if (show) {
        progressFill.style.width = `${progress}%`;
        progressText.textContent = message || `${progress}%`;
    }
}

function getStepMessage(step) {
    const messages = {
        'starting': 'Iniciando procesamiento...',
        'generating_metadata': 'Generando metadata (33%)...',
        'metadata_complete': 'Metadata generada (33%)',
        'processing_video': 'Procesando video (66%)...',
        'video_complete': 'Video procesado (66%)',
        'generating_heatmap': 'Generando mapa de calor...',
        'completed': 'Proceso completado'
    };
    return messages[step] || 'Procesando...';
}

function clearDisplays() {
    const videoPlayer = document.getElementById('video-player');
    const heatmapContainer = document.getElementById('heatmap-container');
    const videoError = document.getElementById('video-error');
    
    if (processingMonitorInterval) {
        clearInterval(processingMonitorInterval);
    }
    
    videoPlayer.style.display = 'none';
    videoPlayer.src = '';
    heatmapContainer.innerHTML = '';
    if (videoError) {
        videoError.style.display = 'none';
    }
}

async function showProcessedVideo(videoPath) {
    const videoPlayer = document.getElementById('video-player');
    const videoError = document.getElementById('video-error');
    
    videoPlayer.style.display = 'none';
    videoError.style.display = 'none';
    
    try {
        const fullPath = `${API_URL}${videoPath}`;
        const response = await fetch(fullPath, {
            method: 'HEAD'
        });
        
        if (!response.ok) throw new Error('Video not found');
        
        videoPlayer.src = fullPath;
        videoPlayer.style.display = 'block';
        
        videoPlayer.addEventListener('loadeddata', () => {
            videoPlayer.style.display = 'block';
        });
        
    } catch (error) {
        console.error('Error:', error);
        videoError.textContent = error.message;
        videoError.style.display = 'block';
    }
}

async function checkExistingProcessedVideo() {
    const videoName = document.getElementById('video-select').value;
    if (!videoName) return;
    
    try {
        const response = await fetch(`${API_URL}/videos/status/${videoName}`);
        const data = await response.json();
        
        if (data.status === 'completed' && data.processed_video_path && data.heatmap_path) {
            await showProcessedVideo(data.processed_video_path);
            
            const heatmapContainer = document.getElementById('heatmap-container');
            heatmapContainer.innerHTML = `
                <img src="${API_URL}${data.heatmap_path}"
                     alt="Mapa de calor"
                     style="max-width: 100%; display: block; margin: 0 auto;">
            `;
            
            await loadVideoObjects();
        }
    } catch (error) {
        console.error('Error verificando video:', error);
        showError(error.message);
    }
}

async function loadVideoObjects() {
    const videoName = document.getElementById('video-select').value;
    if (!videoName) return;
    
    const objectSelect = document.getElementById('object-search');
    objectSelect.innerHTML = '<option value="">Seleccione un objeto</option>';
    
    try {
        const response = await fetch(`${API_URL}/metadata/objects/${videoName}`);
        const data = await response.json();
        
        if (data.status === 'found' && data.objects) {
            data.objects.forEach(obj => {
                const option = document.createElement('option');
                option.value = obj.label;
                option.textContent = `${obj.label} (${obj.occurrences.length} veces)`;
                objectSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error cargando objetos:', error);
        showError('Error cargando lista de objetos');
    }
}

async function searchObjects() {
    const videoName = document.getElementById('video-select').value;
    const objectLabel = document.getElementById('object-search').value;
    const searchResults = document.getElementById('search-results');
    const videoPlayer = document.getElementById('video-player');
    
    if (!videoName || !objectLabel) {
        showError('Seleccione un video y un objeto');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/metadata/objects/${videoName}`);
        const data = await response.json();
        
        if (data.status === 'found') {
            const objectData = data.objects.find(obj => obj.label === objectLabel);
            if (objectData) {
                const resultsHTML = objectData.occurrences.map(occurrence => `
                    <div class="result-card">
                        <div class="result-info">
                            <span>Frame: ${occurrence.frame}</span>
                            <span>Tiempo: ${occurrence.timestamp.toFixed(2)}s</span>
                        </div>
                        <button class="jump-button" onclick="jumpToTimestamp(${occurrence.timestamp})">
                            Ir al momento
                        </button>
                    </div>
                `).join('');
                
                searchResults.innerHTML = `
                    <h3>Resultados para "${objectLabel}"</h3>
                    <div class="results-container">
                        ${resultsHTML}
                    </div>
                `;
            } else {
                searchResults.innerHTML = `<p>No se encontró el objeto "${objectLabel}" en este video</p>`;
            }
        }
    } catch (error) {
        console.error('Error en búsqueda:', error);
        showError('Error al buscar objetos');
    }
}

function jumpToTimestamp(timestamp) {
    const videoPlayer = document.getElementById('video-player');
    if (videoPlayer) {
        videoPlayer.currentTime = timestamp;
        videoPlayer.play();
    }
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    errorDiv.style.cssText = 'color: red; padding: 10px; margin: 10px 0; background-color: #ffe6e6; border-radius: 4px;';
    
    const container = document.querySelector('.container');
    if (container) {
        container.insertBefore(errorDiv, container.firstChild);
        setTimeout(() => errorDiv.remove(), 5000);
    }
}

let streamInterval = null;

async function startStreamSimulation() {
    const videoName = document.getElementById('video-select').value;
    if (!videoName) {
        showError('Seleccione un video primero');
        return;
    }

    const streamView = document.getElementById('stream-view');
    const streamButton = document.getElementById('stream-button');
    const stopStreamButton = document.getElementById('stop-stream-button');

    streamView.style.display = 'block';
    streamView.classList.add('loading-stream');
    streamButton.style.display = 'none';
    stopStreamButton.style.display = 'inline-block';

    streamInterval = setInterval(() => {
        streamView.src = `${API_URL}/videos/rtsp/stream/${videoName}?t=${Date.now()}`;
    }, 100);
}

function stopStreamSimulation() {
    if (streamInterval) {
        clearInterval(streamInterval);
        streamInterval = null;
    }

    const streamView = document.getElementById('stream-view');
    const streamButton = document.getElementById('stream-button');
    const stopStreamButton = document.getElementById('stop-stream-button');

    streamView.style.display = 'none';
    streamView.classList.remove('loading-stream');
    streamButton.style.display = 'inline-block';
    stopStreamButton.style.display = 'none';
}