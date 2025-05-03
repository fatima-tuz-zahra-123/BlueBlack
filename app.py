from flask import Flask, render_template, jsonify, send_from_directory, request
import os
import json
import datetime
import re
import subprocess
import threading
import time
from pathlib import Path
import random
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DawnNewsReader")

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
        logger.warning(f"Created missing audio directory: {audio_dir}")
        
    summary_files = [f for f in os.listdir(audio_dir) if f.startswith('audio_summary_')]
    
    if not summary_files:
        logger.warning("No audio summary files found")
        return jsonify({'error': 'No news available. Please click "Get Latest News" to fetch content.', 'articles': []})
    
    # Get the most recent summary file
    latest_summary = max(summary_files)
    summary_path = os.path.join(audio_dir, latest_summary)
    logger.info(f"Using latest summary file: {latest_summary}")
    
    try:
        with open(summary_path, 'r', encoding='utf-8') as f:
            summary = json.load(f)
            
        # For each article in the summary
        for article_info in summary.get('articles', []):
            title = article_info.get('title', '')
            audio_path = article_info.get('audio_path', '')
            
            # Skip if missing required fields
            if not title or not audio_path:
                logger.warning(f"Skipping article with missing data: {article_info}")
                continue
                
            # Check if audio file exists
            if not os.path.exists(audio_path):
                logger.warning(f"Audio file not found: {audio_path}")
                continue
            
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
            else:
                logger.warning(f"Script file not found: {script_path}")
            
            # Extract timestamp from filename
            timestamp_match = re.search(r'(\d{12})', audio_filename)
            timestamp_str = timestamp_match.group(1) if timestamp_match else ""
            
            if timestamp_str:
                try:
                    # Convert YYYYMMDDHHMI format to readable date
                    timestamp = datetime.datetime.strptime(timestamp_str, '%Y%m%d%H%M')
                    formatted_time = timestamp.strftime('%B %d, %Y at %I:%M %p')
                except ValueError as e:
                    logger.error(f"Error parsing timestamp {timestamp_str}: {str(e)}")
                    formatted_time = ""
            else:
                formatted_time = ""
            
            # Get the article image (placeholder for now)
            image_url = "/static/images/news_placeholder.jpg"
            
            # Fix the audio URL to use our route
            audio_url = f"/news_audio/{audio_filename}"
            
            # Get the voice used (if available in newer summaries)
            voice = summary.get('voice', 'Joanna')
            
            news_data.append({
                'title': title,
                'audio_url': audio_url,
                'script': script_content,
                'timestamp': formatted_time,
                'image_url': image_url,
                'voice': voice
            })
            
        logger.info(f"Retrieved {len(news_data)} articles")
    except Exception as e:
        logger.error(f"Error loading news: {str(e)}", exc_info=True)
        return jsonify({'error': f"Error loading news: {str(e)}", 'articles': []})
    
    if not news_data:
        return jsonify({'error': 'No valid news articles found. Try refreshing.', 'articles': []})
    
    return jsonify({'articles': news_data})

@app.route('/refresh-news')
def refresh_news():
    """Trigger the scraping and text-to-speech process"""
    try:
        # Get the selected voice from the query parameter, default to Matthew
        voice = request.args.get('voice', 'Matthew')
        logger.info(f"Refresh news request with voice: {voice}")
        
        # Run the scraper
        logger.info("Starting news scraper...")
        scraper_process = subprocess.run(['python', 'dawn_scraper.py', '--single-run'], 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE, 
                      text=True,
                      check=True)
        
        if scraper_process.stderr:
            logger.warning(f"Scraper warnings: {scraper_process.stderr}")
        
        # Run the text-to-speech with the selected voice
        logger.info(f"Starting TTS with voice: {voice}")
        tts_process = subprocess.run(['python', 'polly_tts.py', '--voice', voice], 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE, 
                      text=True,
                      check=True)
        
        if tts_process.stderr:
            logger.warning(f"TTS warnings: {tts_process.stderr}")
            
        logger.info("News refresh completed successfully")
        return jsonify({
            'status': 'success', 
            'message': f'News updated successfully with voice {voice}'
        })
    except subprocess.CalledProcessError as e:
        error_msg = f"Process error: {str(e)}"
        if e.stderr:
            error_msg += f" - {e.stderr}"
        logger.error(error_msg)
        return jsonify({'status': 'error', 'message': error_msg})
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Error updating news: {str(e)}'})

@app.route('/scrape-news')
def scrape_news():
    """Trigger only the scraping process to get fresh articles without generating audio"""
    try:
        # Run only the scraper to get new articles
        process = subprocess.run(['python', 'dawn_scraper.py', '--single-run'], 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE, 
                      text=True,
                      check=True)
        
        print(f"dawn_scraper.py output: {process.stdout}")
        if process.stderr:
            print(f"dawn_scraper.py errors: {process.stderr}")
            
        return jsonify({'status': 'success', 'message': 'Latest news articles fetched successfully'})
    except subprocess.CalledProcessError as e:
        print(f"Error in scraper subprocess: {e.stderr}")
        return jsonify({'status': 'error', 'message': f'Error fetching news: {str(e)}'})

@app.route('/available-voices')
def available_voices():
    """Get available Amazon Polly voice options - simplified to just 4 voices"""
    voices = [
        {"id": "Joanna", "name": "Joanna", "accent": "American Female", "quality": "Neural"},
        {"id": "Matthew", "name": "Matthew", "accent": "American Male", "quality": "Neural"},
        {"id": "Amy", "name": "Amy", "accent": "British Female", "quality": "Neural"},
        {"id": "Brian", "name": "Brian", "accent": "British Male", "quality": "Neural"}
    ]
    return jsonify(voices)

def run_scheduled_tasks():
    """Run the scraper and TTS on a schedule"""
    while True:
        try:
            current_time = datetime.datetime.now().strftime("%H:%M:%S")
            logger.info(f"Running scheduled update at {current_time}")
            
            # Run the scraper
            subprocess.run(['python', 'dawn_scraper.py', '--single-run'], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE, 
                        text=True)
            
            # Run the text-to-speech with a randomly selected voice
            polly_voices = [
                "Joanna",  # American Female
                "Matthew", # American Male
                "Amy",     # British Female
                "Brian"    # British Male
            ]
            
            # Select a voice based on time but with some randomness
            current_hour = datetime.datetime.now().hour
            voice_index = (current_hour % len(polly_voices))
            
            # 20% chance to randomly choose a different voice than the scheduled one
            if random.random() < 0.2:
                voice_index = random.randint(0, len(polly_voices) - 1)
                
            selected_voice = polly_voices[voice_index]
            
            logger.info(f"Using voice for scheduled update: {selected_voice}")
            subprocess.run(['python', 'polly_tts.py', '--voice', selected_voice], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE, 
                        text=True)
            
            logger.info(f"Scheduled update completed successfully")
        except Exception as e:
            logger.error(f"Error in scheduled update: {str(e)}", exc_info=True)
        
        # Wait for one hour before the next run
        logger.info("Waiting for next scheduled update in 1 hour")
        time.sleep(3600)  # 3600 seconds = 1 hour

if __name__ == '__main__':
    # Create directories if they don't exist
    os.makedirs('static/images', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # Start the scheduler in a background thread
    logger.info("Starting scheduler thread")
    scheduler_thread = threading.Thread(target=run_scheduled_tasks, daemon=True)
    scheduler_thread.start()
    
    # Run the Flask app
    logger.info("Starting Flask application")
    app.run(debug=True, port=5000)