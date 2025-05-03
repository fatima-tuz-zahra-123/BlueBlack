import os
import json
import datetime
import logging
import random
import re
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tts.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AmazonPollyTTS")

class PollyTTS:
    def __init__(self):
        self.scraped_dir = "scraped_news"
        self.audio_dir = "news_audio"
        
        # Default AWS region
        self.region = "us-east-1"
        
        # Create audio directory if it doesn't exist
        if not os.path.exists(self.audio_dir):
            os.makedirs(self.audio_dir)
            
        # Load AWS credentials from config
        self._load_aws_credentials()
        
        # Initialize Polly client
        try:
            self.polly_client = boto3.client(
                'polly',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region
            )
            logger.info("Amazon Polly client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Amazon Polly client: {e}")
            self.polly_client = None
    
    def _load_aws_credentials(self):
        """Load AWS credentials from environment variables or config file as fallback"""
        # Try loading from environment variables first (preferred method)
        self.aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        
        # If environment variables are set, use them
        if self.aws_access_key_id and self.aws_secret_access_key:
            logger.info("AWS credentials loaded from environment variables")
            return
            
        # Otherwise, fall back to config file (less secure, for development only)
        config_path = os.path.join(os.path.dirname(__file__), "aws_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    self.aws_access_key_id = config.get("AWS_ACCESS_KEY_ID")
                    self.aws_secret_access_key = config.get("AWS_SECRET_ACCESS_KEY")
                    self.region = config.get("AWS_REGION", "us-east-1")
                    
                    if self.aws_access_key_id and self.aws_secret_access_key:
                        logger.info("AWS credentials loaded from config file")
                    else:
                        logger.error("AWS credentials not found or not properly set in aws_config.json")
            except Exception as e:
                logger.error(f"Error loading AWS credentials from config: {e}")
                self.aws_access_key_id = None
                self.aws_secret_access_key = None
        else:
            logger.error(f"AWS config file not found and no environment variables set")
    
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
        """Create a simple news script without any SSML markup"""
        try:
            title = article.get('title', 'Breaking News')
            summary = article.get('summary', '')
            content = article.get('content', '')
            
            # Create a simple script format
            script = f"Welcome to Dawn News. {title}. "
            
            if summary:
                script += f"{summary} "
            
            # Take first part of content if it's long
            if len(content) > 1000:
                sentences = content.split('.')[:5]  # First 5 sentences
                content = '. '.join(sentences) + '.'
                
            script += f"{content} "
            script += "Thank you for listening to Dawn News."
            
            return script
        except Exception as e:
            logger.error(f"Error creating news script: {e}")
            return f"Welcome to Dawn News. {article.get('title', 'Breaking News')}"

    def text_to_speech(self, text, voice_id):
        """Convert text to speech using Amazon Polly with default settings"""
        if not self.polly_client:
            logger.error("Polly client not initialized")
            return None
        
        try:
            # Check if text is too long (Polly has a 3000 character limit)
            if len(text) > 3000:
                logger.warning(f"Text too long ({len(text)} chars), truncating to 3000 chars")
                # Truncate at sentence boundary
                sentences = text.split('.')
                truncated_text = ""
                for sentence in sentences:
                    if len(truncated_text) + len(sentence) < 2950:
                        truncated_text += sentence + "."
                    else:
                        break
                text = truncated_text
            
            # Simple Polly request with default settings
            response = self.polly_client.synthesize_speech(
                Text=text,
                OutputFormat="mp3",
                VoiceId=voice_id,
                Engine="neural"
            )
            
            if response and 'AudioStream' in response:
                logger.info("Successfully generated audio with Amazon Polly")
                return response['AudioStream'].read()
            else:
                logger.error(f"Amazon Polly returned unexpected response: {response}")
                return None
            
        except ClientError as e:
            logger.error(f"Amazon Polly API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error with Amazon Polly TTS: {e}")
            return None
    
    def process_articles(self, voice_id="Joanna"):
        """Process articles to generate audio files"""
        articles = self.get_latest_articles()
        logger.info(f"Found {len(articles)} articles to process")
        logger.info(f"Using voice: {voice_id}")
        
        results = []
        for article in articles:
            try:
                title = article.get('title', 'Unknown Article')
                logger.info(f"Processing article: {title}")
                
                # Create simple news script with no special formatting
                script = self.create_news_script(article)
                logger.info(f"Created script for article: {title} - Script length: {len(script)} chars")
                
                # Convert to speech using the specified voice
                audio_content = self.text_to_speech(script, voice_id=voice_id)
                if not audio_content:
                    logger.error(f"Failed to generate audio for: {title}")
                    continue
                
                # Save audio file
                filename = "".join(c if c.isalnum() else "_" for c in title)
                audio_path = os.path.join(self.audio_dir, f"{filename}_{datetime.datetime.now().strftime('%Y%m%d%H%M')}.mp3")
                
                # Write the audio content to the file
                try:
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
                        'script_path': script_path,
                        'voice': voice_id
                    })
                except Exception as e:
                    logger.error(f"Error saving audio file: {e}")
                
            except Exception as e:
                logger.error(f"Error processing article: {e}")
        
        # Save a summary of processed articles
        if results:
            summary_path = os.path.join(self.audio_dir, f"audio_summary_{datetime.datetime.now().strftime('%Y%m%d%H%M')}.json")
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.datetime.now().isoformat(),
                    'count': len(results),
                    'voice': voice_id,
                    'articles': [{'title': r['title'], 'audio_path': r['audio_path']} for r in results]
                }, f, indent=2)
            
            logger.info(f"Processed {len(results)} articles with voice {voice_id} - Summary saved to {summary_path}")
        
        return results

# Main function to run the script from command line
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate TTS for news articles using Amazon Polly')
    parser.add_argument('--voice', type=str, default="Joanna", 
                      help='Voice ID to use for TTS (default: Joanna)')
    args = parser.parse_args()
    
    # Debug output
    print(f"Command line arguments received: {args}")
    print(f"Voice ID selected: {args.voice}")
    
    # Initialize TTS
    tts = PollyTTS()
    
    # Generate audio
    results = tts.process_articles(voice_id=args.voice)
    
    if results:
        print(f"Generated {len(results)} audio files using voice {args.voice}:")
        for result in results:
            print(f"- {result['title']}")
            print(f"  Audio: {result['audio_path']}")
    else:
        print("No audio files were generated.")

if __name__ == "__main__":
    main()