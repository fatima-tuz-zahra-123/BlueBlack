from flask import Flask, render_template, jsonify, send_from_directory
import os
import json
import datetime
import re
import subprocess
import threading
import time
from pathlib import Path

app = Flask(__name__)

# Configure static folders for custom paths
@app.route('/news_audio/<path:filename>')
def serve_audio(filename):
    """Serve audio files from the news_audio directory"""
    return send_from_directory('news_audio', filename)

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/api/news')
def get_news():
    """Get the latest news articles with their audio files"""
    news_data = []
    
    # Find the latest audio summary file
    audio_dir = 'news_audio'
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)
        
    summary_files = [f for f in os.listdir(audio_dir) if f.startswith('audio_summary_')]
    
    if not summary_files:
        return jsonify({'error': 'No news available', 'articles': []})
    
    # Get the most recent summary file
    latest_summary = max(summary_files)
    summary_path = os.path.join(audio_dir, latest_summary)
    
    try:
        with open(summary_path, 'r', encoding='utf-8') as f:
            summary = json.load(f)
            
        # For each article in the summary
        for article_info in summary.get('articles', []):
            title = article_info.get('title', '')
            audio_path = article_info.get('audio_path', '')
            
            # Extract just the filename from the path
            audio_filename = os.path.basename(audio_path)
            
            # Find the corresponding script file
            base_filename = os.path.splitext(audio_filename)[0]
            script_filename = f"{base_filename}_script.txt"
            script_path = os.path.join(audio_dir, script_filename)
            
            script_content = ""
            if os.path.exists(script_path):
                with open(script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()
            
            # Extract timestamp from filename
            timestamp_match = re.search(r'(\d{12})', audio_filename)
            timestamp_str = timestamp_match.group(1) if timestamp_match else ""
            
            if timestamp_str:
                try:
                    # Convert YYYYMMDDHHMI format to readable date
                    timestamp = datetime.datetime.strptime(timestamp_str, '%Y%m%d%H%M')
                    formatted_time = timestamp.strftime('%B %d, %Y at %I:%M %p')
                except ValueError:
                    formatted_time = ""
            else:
                formatted_time = ""
            
            # Get the article image (placeholder for now)
            image_url = "/static/images/news_placeholder.jpg"
            
            # Fix the audio URL to use our route
            audio_url = f"/news_audio/{audio_filename}"
            
            news_data.append({
                'title': title,
                'audio_url': audio_url,
                'script': script_content,
                'timestamp': formatted_time,
                'image_url': image_url
            })
    except Exception as e:
        print(f"Error loading news: {e}")
        return jsonify({'error': str(e), 'articles': []})
    
    return jsonify({'articles': news_data})

@app.route('/refresh-news')
def refresh_news():
    """Trigger the scraping and text-to-speech process"""
    try:
        # Run the scraper
        subprocess.run(['python', 'dawn_scraper.py', '--single-run'], 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE, 
                      text=True,
                      check=True)
        
        # Run the text-to-speech
        subprocess.run(['python', 'camb_tts.py'], 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE, 
                      text=True,
                      check=True)
        
        return jsonify({'status': 'success', 'message': 'News updated successfully'})
    except subprocess.CalledProcessError as e:
        return jsonify({'status': 'error', 'message': f'Error updating news: {str(e)}'})

def run_scheduled_tasks():
    """Run the scraper and TTS on a schedule"""
    while True:
        try:
            # Run the scraper
            subprocess.run(['python', 'dawn_scraper.py', '--single-run'], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE, 
                        text=True)
            
            # Run the text-to-speech
            subprocess.run(['python', 'camb_tts.py'], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE, 
                        text=True)
            
            print(f"{datetime.datetime.now()}: Scheduled update completed successfully")
        except Exception as e:
            print(f"Error in scheduled update: {e}")
        
        # Wait for one hour before the next run
        time.sleep(3600)  # 3600 seconds = 1 hour

if __name__ == '__main__':
    # Create directories if they don't exist
    os.makedirs('static/images', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # Start the scheduler in a background thread
    scheduler_thread = threading.Thread(target=run_scheduled_tasks, daemon=True)
    scheduler_thread.start()
    
    # Run the Flask app
    app.run(debug=True, port=5000)