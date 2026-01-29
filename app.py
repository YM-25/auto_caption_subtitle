import os
import secrets
import json
from flask import Flask, render_template, request, send_file, jsonify, Response, stream_with_context
from werkzeug.utils import secure_filename
from src.pipeline import process_video

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'data', 'videos')
AUDIO_FOLDER = os.path.join(BASE_DIR, 'data', 'audios')
TRANSCRIPT_FOLDER = os.path.join(BASE_DIR, 'data', 'transcripts')
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER
app.config['TRANSCRIPT_FOLDER'] = TRANSCRIPT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB limit

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(TRANSCRIPT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_and_process', methods=['POST'])
def upload_and_process():
    # We use a streaming response to send progress updates
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not (file and allowed_file(file.filename)):
        return jsonify({'error': 'File type not allowed'}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(save_path)
    
    source_lang = request.form.get('source_language', 'auto')
    if source_lang == 'auto':
        source_lang = None
        
    target_lang = request.form.get('target_language', 'auto')
    if target_lang == 'auto':
        target_lang = None 

    def generate():
        try:
            # Yield progress messages
            yield json.dumps({'type': 'progress', 'message': f'File uploaded: {filename}'}) + '\n'
            
            import queue
            import threading
            
            q = queue.Queue()
            
            def worker():
                try:
                    def cb(msg):
                        q.put({'type': 'progress', 'message': msg})
                        
                    outputs = process_video(save_path, source_lang=source_lang, target_lang=target_lang, progress_callback=cb)
                    
                    # Prepare final result
                    files = []
                    if 'original' in outputs:
                        files.append({'label': 'Original Subtitles (.srt)', 'url': f'/download/{os.path.basename(outputs["original"])}'})
                    if 'translated' in outputs:
                        files.append({'label': 'Translated Subtitles (.srt)', 'url': f'/download/{os.path.basename(outputs["translated"])}'})
                    if 'dual' in outputs:
                        files.append({'label': 'Bilingual Subtitles (Dual .srt)', 'url': f'/download/{os.path.basename(outputs["dual"])}'})

                    q.put({'type': 'result', 'files': files})
                except Exception as e:
                    q.put({'type': 'error', 'message': str(e)})
                finally:
                    q.put(None) # Sentinel

            t = threading.Thread(target=worker)
            t.start()

            while True:
                item = q.get()
                if item is None:
                    break
                yield json.dumps(item) + '\n'
                
            t.join()

        except Exception as e:
            yield json.dumps({'type': 'error', 'message': str(e)}) + '\n'

    return Response(stream_with_context(generate()), mimetype='application/x-ndjson')

@app.route('/download/<path:filename>')
def download_file(filename):
    # Prevent path traversal: ensure resolved path stays inside TRANSCRIPT_FOLDER
    root = os.path.abspath(app.config['TRANSCRIPT_FOLDER'])
    path = os.path.abspath(os.path.join(root, filename))
    if not path.startswith(root) or not os.path.isfile(path):
        return jsonify({'error': 'File not found'}), 404
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

@app.route('/clear_history', methods=['POST'])
def clear_history():
    try:
        import shutil
        # Clear directories: videos, extracted audios, transcripts
        for folder in [app.config['UPLOAD_FOLDER'], app.config['AUDIO_FOLDER'], app.config['TRANSCRIPT_FOLDER']]:
            if not os.path.isdir(folder):
                continue
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f'Failed to delete {file_path}. Reason: {e}')
        return jsonify({'message': 'History cleared successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', '0').lower() in ('1', 'true', 'yes')
    app.run(debug=debug, port=5000)
