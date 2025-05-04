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
from did_video_generator import DIDVideoGenerator
import base64

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

@app.route('/news_video/<path:filename>')
def serve_video(filename):
    """Serve video files from the news_video directory"""
    return send_from_directory('news_video', filename)

@app.route('/news_videos/<path:filename>')
def serve_news_videos(filename):
    """Serve video files from the news_videos directory"""
    return send_from_directory('news_videos', filename)

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
            
            # Generate video URL
            video_dir = 'news_video'
            video_filename = f"{base_filename}.mp4"
            video_path = os.path.join(video_dir, video_filename)
            video_url = f"/news_video/{video_filename}" if os.path.exists(video_path) else None
            
            news_data.append({
                'title': title,
                'audio_url': audio_url,
                'script': script_content,
                'timestamp': formatted_time,
                'image_url': image_url,
                'voice': voice,
                'video_url': video_url
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
        
        # Generate videos for the articles
        logger.info("Starting video generation...")
        # Use the hardcoded API key with Basic authentication
        api_key = "YXNtYWltcmFuY2hhdWRocnlAZ21haWwuY29t:y_SS9YofYUdlk50ux6ygV"
        video_generator = DIDVideoGenerator(api_key)
        video_generator.generate_videos()
            
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

@app.route('/generate-video')
def generate_video():
    """Generate a video for a specific audio file"""
    try:
        audio_path = request.args.get('audio_path')
        if not audio_path:
            return jsonify({'status': 'error', 'message': 'No audio path provided'})
            
        if not os.path.exists(audio_path):
            return jsonify({'status': 'error', 'message': f'Audio file not found: {audio_path}'})
        
        # Create a D-ID video generator
        from did_video_generator import DIDVideoGenerator
        
        # Use the hardcoded API key with Basic authentication
        api_key = "YXNtYWltcmFuY2hhdWRocnlAZ21haWwuY29t:y_SS9YofYUdlk50ux6ygV"
        username, password = api_key.split(':', 1)
        auth_str = base64.b64encode(f"{username}:{password}".encode('utf-8')).decode('utf-8')
        
        video_gen = DIDVideoGenerator(api_key)
        video_gen.headers = {
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Get the title from the audio filename
        audio_filename = os.path.basename(audio_path)
        title = os.path.splitext(audio_filename)[0]
        
        # Generate the video
        logger.info(f"Generating video for audio: {audio_path}")
        video_path = video_gen.create_talk(audio_path, title)
        
        if video_path:
            # Get the relative path for the URL
            video_filename = os.path.basename(video_path)
            video_url = f"/news_videos/{video_filename}"
            return jsonify({
                'status': 'success', 
                'message': 'Video generated successfully',
                'video_url': video_url
            })
        else:
            return jsonify({
                'status': 'error', 
                'message': 'Failed to generate video. Check logs for details.'
            })
    
    except Exception as e:
        logger.error(f"Error generating video: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Error generating video: {str(e)}'
        })

@app.route('/api/top-headlines')
def get_top_headlines():
    """Get the latest top headlines summary from Gemini API"""
    try:
        # Find latest top headline summary
        summary_dir = 'news_summaries'
        if not os.path.exists(summary_dir):
            os.makedirs(summary_dir)
            return jsonify({'status': 'error', 'message': 'No top headlines available yet'})
        
        summary_files = [f for f in os.listdir(summary_dir) if f.startswith('top_headline_')]
        if not summary_files:
            return jsonify({'status': 'error', 'message': 'No top headlines available yet'})
            
        latest_summary_file = os.path.join(summary_dir, max(summary_files))
        
        # Extract timestamp from filename
        timestamp_match = re.search(r'(\d{12})', latest_summary_file)
        timestamp_str = timestamp_match.group(1) if timestamp_match else ""
        
        # Format timestamp
        formatted_time = ""
        if timestamp_str:
            try:
                timestamp = datetime.datetime.strptime(timestamp_str, '%Y%m%d%H%M')
                formatted_time = timestamp.strftime('%B %d, %Y at %I:%M %p')
            except ValueError:
                pass
        
        # Read the summary content
        with open(latest_summary_file, 'r', encoding='utf-8') as f:
            summary = f.read().strip()
        
        # Check if there's a corresponding video
        video_filename = f"Top_Headlines_Summary_{timestamp_str}.mp4"
        video_path = os.path.join("news_videos", video_filename)
        video_url = f"/news_videos/{video_filename}" if os.path.exists(video_path) else None
        
        # Check if there's a corresponding audio
        audio_filename = f"Top_Headlines_Summary_{timestamp_str}.mp3"
        audio_path = os.path.join("news_audio", audio_filename)
        audio_url = f"/news_audio/{audio_filename}" if os.path.exists(audio_path) else None
        
        return jsonify({
            'status': 'success',
            'summary': summary,
            'timestamp': formatted_time,
            'video_url': video_url,
            'audio_url': audio_url
        })
    except Exception as e:
        logger.error(f"Error getting top headlines: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Error getting top headlines: {str(e)}'})

@app.route('/generate-top-headlines')
def generate_top_headlines():
    """Generate a summarized top headlines using Gemini API"""
    try:
        # Get the selected voice from the query parameter, default to Joanna
        voice = request.args.get('voice', 'Joanna')
        use_existing = request.args.get('use_existing') == 'true'
        
        # Use hardcoded Gemini API key
        api_key = "AIzaSyArP4ANLerTCSZg5d166cviuIkYNyGwGjo"
        
        logger.info(f"Generating top headlines summary with voice: {voice}")
        
        # Initialize the headline summarizer
        from headline_summarizer import HeadlineSummarizer
        summarizer = HeadlineSummarizer(api_key=api_key)
        
        # We'll use subprocess to run the headline summarizer in a separate process
        # This avoids the async issues with Flask
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp:
            temp_path = temp.name
            
        # Run the headline summarizer as a subprocess
        subprocess_cmd = [
            'python', '-c', 
            f'''
import asyncio, json
from headline_summarizer import HeadlineSummarizer
async def main():
    summarizer = HeadlineSummarizer(api_key="{api_key}")
    summary_result = await summarizer.summarize_headlines()
    if summary_result:
        video_result = await summarizer.generate_top_headline_video(
            summary=summary_result["summary"],
            voice="{voice}"
        )
        result = {{"summary": summary_result, "video": video_result}}
        with open("{temp_path}", "w") as f:
            json.dump(result, f)
asyncio.run(main())
            '''
        ]
        
        logger.info("Starting headline summarization subprocess")
        process = subprocess.run(
            subprocess_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if process.returncode != 0:
            logger.error(f"Headline summarization failed: {process.stderr}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to generate headlines summary: {process.stderr}'
            })
            
        # Check if the temp file was created and has content
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            with open(temp_path, 'r') as f:
                result = json.load(f)
                
            # Clean up the temp file
            os.unlink(temp_path)
            
            summary_result = result.get("summary")
            video_result = result.get("video")
            
            if not summary_result:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to generate headlines summary. No summary was generated.'
                })
                
            if video_result:
                video_path = video_result['video_path']
                video_filename = os.path.basename(video_path)
                video_url = f"/news_videos/{video_filename}"
                
                return jsonify({
                    'status': 'success',
                    'message': 'Top headlines summary generated successfully',
                    'summary': summary_result['summary'],
                    'video_url': video_url,
                    'audio_url': f"/news_audio/{os.path.basename(video_result['audio_path'])}"
                })
            else:
                return jsonify({
                    'status': 'partial',
                    'message': 'Generated summary but failed to create video',
                    'summary': summary_result['summary'],
                })
        else:
            logger.error("Headline summarization produced no output")
            return jsonify({
                'status': 'error',
                'message': 'Failed to generate headlines summary. Check logs for details.'
            })
            
    except Exception as e:
        logger.error(f"Error generating top headlines: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Error generating top headlines: {str(e)}'
        })

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
            
            # Generate videos for the articles
            logger.info("Starting video generation for scheduled update...")
            # Use the hardcoded API key with Basic authentication
            api_key = "YXNtYWltcmFuY2hhdWRocnlAZ21haWwuY29t:y_SS9YofYUdlk50ux6ygV"
            video_generator = DIDVideoGenerator(api_key)
            video_generator.generate_videos()
            
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
    os.makedirs('news_video', exist_ok=True)
    
    # Start the scheduler in a background thread
    logger.info("Starting scheduler thread")
    scheduler_thread = threading.Thread(target=run_scheduled_tasks, daemon=True)
    scheduler_thread.start()
    
    # Run the Flask app
    logger.info("Starting Flask application")
    app.run(debug=True, port=5001)