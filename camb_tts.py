import requests
import json
import os
import datetime
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("camb_tts.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CAMB_TTS")

class CambTTS:
    def __init__(self, api_key):
        self.api_key = api_key
        self.api_url = "https://api.camb.ai/v1/synthesize"
        self.scraped_dir = "scraped_news"
        self.audio_dir = "news_audio"
        
        # Create audio directory if it doesn't exist
        if not os.path.exists(self.audio_dir):
            os.makedirs(self.audio_dir)
    
    def get_latest_articles(self):
        """Get the latest scraped articles"""
        try:
            latest_summary_path = os.path.join(self.scraped_dir, 'latest_scrape.json')
            if not os.path.exists(latest_summary_path):
                logger.error("Latest scrape summary not found")
                return []
                
            with open(latest_summary_path, 'r', encoding='utf-8') as f:
                summary = json.load(f)
                
            articles = []
            for article_info in summary.get('articles', []):
                # Try to find the corresponding JSON file
                article_title = article_info.get('title', '')
                if not article_title:
                    continue
                    
                # Create a pattern that might match the filename
                title_words = article_title.split()[:3]  # Use first few words for matching
                patterns = []
                for word in title_words:
                    # Clean word to match filename pattern
                    clean_word = ''.join(c for c in word if c.isalnum())
                    if clean_word:
                        patterns.append(clean_word)
                
                # Try to find a file matching any of these patterns
                found = False
                for pattern in patterns:
                    article_files = list(Path(self.scraped_dir).glob(f"*{pattern}*.json"))
                    if article_files:
                        # Skip the latest_scrape.json file
                        article_files = [f for f in article_files if f.name != 'latest_scrape.json']
                        if article_files:
                            # Use the most recent file if multiple exist
                            article_path = max(article_files, key=os.path.getctime)
                            with open(article_path, 'r', encoding='utf-8') as f:
                                try:
                                    article_data = json.load(f)
                                    articles.append(article_data)
                                    found = True
                                    logger.info(f"Found article file: {article_path}")
                                    break
                                except json.JSONDecodeError:
                                    logger.error(f"Error parsing JSON from {article_path}")
                if not found:
                    logger.warning(f"Could not find article file for: {article_title}")
                        
            return articles
        except Exception as e:
            logger.error(f"Error retrieving latest articles: {e}")
            return []
    
    def create_news_script(self, article):
        """Create a news anchor style script from the article"""
        try:
            title = article.get('title', 'Breaking News')
            summary = article.get('summary', '')
            content = article.get('content', '')
            
            # If content is too long, use only the first few paragraphs
            paragraphs = content.split('\n')
            if len(paragraphs) > 3:
                brief_content = ' '.join(paragraphs[:3])
            else:
                # Or take first few sentences
                sentences = content.split('.')[:5]
                brief_content = '. '.join(sentences)
                if not brief_content.endswith('.'):
                    brief_content += '.'
            
            # Create a professional news anchor style script
            script = f"Welcome to Dawn News Update. {title}. "
            
            if summary:
                script += f"{summary} "
                
            script += brief_content
            script += " This is Dawn News, reporting from Pakistan."
            
            return script
        except Exception as e:
            logger.error(f"Error creating news script: {e}")
            return f"Welcome to Dawn News Update. {article.get('title', 'Breaking News')}"
    
    def text_to_speech(self, text, voice="en-US-JennyNeural"):
        """Convert text to speech using CAMB.AI API with fallback to gTTS"""
        try:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "text": text,
                "voice": voice,
                "audioFormat": "mp3",
                "speed": 1.0,
                "pitch": 1.0
            }
            
            logger.info(f"Sending TTS request to CAMB.AI - Text length: {len(text)} characters")
            
            # Add timeout to prevent long hangs
            try:
                response = requests.post(self.api_url, json=payload, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    audio_url = data.get("audioUrl")
                    
                    if audio_url:
                        # Download the audio file
                        logger.info(f"Downloading audio from URL: {audio_url}")
                        audio_response = requests.get(audio_url, timeout=10)
                        if audio_response.status_code == 200:
                            return audio_response.content
                        else:
                            logger.error(f"Failed to download audio: {audio_response.status_code}")
                    else:
                        logger.error("No audio URL in response")
                else:
                    logger.error(f"CAMB.AI API error: {response.status_code}, {response.text}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Request to CAMB.AI failed: {e}")
            
            # If we reach here, CAMB.AI failed, so use fallback
            logger.info("Falling back to gTTS for text-to-speech")
            return self.fallback_tts(text)
            
        except Exception as e:
            logger.error(f"Error calling CAMB.AI TTS API: {e}")
            logger.info("Falling back to gTTS for text-to-speech")
            return self.fallback_tts(text)
    
    def fallback_tts(self, text):
        """Fallback to Google Text-to-Speech"""
        try:
            # Import gTTS here to avoid loading it unless needed
            from gtts import gTTS
            
            # Create a temporary file
            temp_file = os.path.join(self.audio_dir, "temp_audio.mp3")
            
            # Generate speech using gTTS
            logger.info("Generating speech with gTTS")
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(temp_file)
            
            # Read the file back
            with open(temp_file, 'rb') as f:
                audio_content = f.read()
            
            # Clean up temp file
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            logger.info("Successfully generated audio with gTTS")
            return audio_content
            
        except Exception as e:
            logger.error(f"Error in fallback TTS: {e}")
            return None
    
    def process_articles(self):
        """Process articles to generate audio files"""
        articles = self.get_latest_articles()
        logger.info(f"Found {len(articles)} articles to process")
        
        results = []
        for article in articles:
            try:
                title = article.get('title', 'Unknown Article')
                logger.info(f"Processing article: {title}")
                
                # Create news script
                script = self.create_news_script(article)
                logger.info(f"Created script for article: {title} - Script length: {len(script)} chars")
                
                # Convert to speech
                audio_content = self.text_to_speech(script)
                if not audio_content:
                    logger.error(f"Failed to generate audio for: {title}")
                    continue
                
                # Save audio file
                filename = "".join(c if c.isalnum() else "_" for c in title)
                audio_path = os.path.join(self.audio_dir, f"{filename}_{datetime.datetime.now().strftime('%Y%m%d%H%M')}.mp3")
                
                with open(audio_path, 'wb') as f:
                    f.write(audio_content)
                
                logger.info(f"Generated audio for: {title} - Saved to: {audio_path}")
                
                # Save script alongside audio for reference
                script_path = os.path.join(self.audio_dir, f"{filename}_{datetime.datetime.now().strftime('%Y%m%d%H%M')}_script.txt")
                with open(script_path, 'w', encoding='utf-8') as f:
                    f.write(script)
                
                results.append({
                    'title': title,
                    'audio_path': audio_path,
                    'script_path': script_path
                })
                
            except Exception as e:
                logger.error(f"Error processing article: {e}")
        
        # Save a summary of processed articles
        if results:
            summary_path = os.path.join(self.audio_dir, f"audio_summary_{datetime.datetime.now().strftime('%Y%m%d%H%M')}.json")
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.datetime.now().isoformat(),
                    'count': len(results),
                    'articles': [{'title': r['title'], 'audio_path': r['audio_path']} for r in results]
                }, f, indent=2)
            
            logger.info(f"Processed {len(results)} articles - Summary saved to {summary_path}")
        
        return results

# Main function to run the script from command line
def main():
    # Default API key - replace with your actual key
    api_key = "3f5595e9-c824-4979-81b3-95fb6642b795"
    
    # Install gTTS if not already installed (for fallback TTS)
    try:
        import gtts
    except ImportError:
        logger.info("Installing gTTS for fallback text-to-speech...")
        import subprocess
        subprocess.check_call(["pip", "install", "gtts"])
    
    tts = CambTTS(api_key)
    results = tts.process_articles()
    
    if results:
        print(f"Generated {len(results)} audio files:")
        for result in results:
            print(f"- {result['title']}")
            print(f"  Audio: {result['audio_path']}")
    else:
        print("No audio files were generated.")

if __name__ == "__main__":
    main()