import os
import json
import datetime
import logging
import sys
import argparse
from pathlib import Path
import time
import random
import re
import requests
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tts.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ElevenLabsTTS")

class EnhancedTTS:
    def __init__(self):
        self.scraped_dir = "scraped_news"
        self.audio_dir = "news_audio"
        self.elevenlabs_api_key = None
        
        # Create audio directory if it doesn't exist
        if not os.path.exists(self.audio_dir):
            os.makedirs(self.audio_dir)
            
        # Load API key from config
        self._load_api_key()
    
    def _load_api_key(self):
        """Load ElevenLabs API key from config file"""
        config_path = os.path.join(os.path.dirname(__file__), "elevenlabs_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    self.elevenlabs_api_key = config.get("ELEVENLABS_API_KEY")
                    if self.elevenlabs_api_key and self.elevenlabs_api_key != "your-api-key-here":
                        logger.info("ElevenLabs API key loaded successfully")
                    else:
                        logger.error("ElevenLabs API key not found or not properly set in elevenlabs_config.json")
            except Exception as e:
                logger.error(f"Error loading ElevenLabs API key: {e}")
        else:
            logger.error(f"ElevenLabs config file not found at {config_path}")
    
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
        """Create a news anchor style script from the article with natural speech patterns"""
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
            
            # Create varied intros with more natural speech patterns
            intros = [
                "Welcome to Dawn News. I'm your host bringing you the latest updates.",
                "This is Dawn News with today's top stories.",
                "Good day, and thank you for joining us at Dawn News. Here's what's making headlines today.",
                "Hello, I'm your Dawn News presenter with the latest developments.",
                "Dawn News here with the stories that matter to you today."
            ]
            
            # Transitions for a more natural flow
            transitions = [
                "Let's take a closer look at this story.",
                "Here are the details.",
                "Let me share what we know so far.",
                "According to our sources,",
                "The article continues by stating,"
            ]
            
            # Varied conclusions for more natural endings
            outros = [
                "That's all for this update. Stay with Dawn News for more developments as they happen.",
                "We'll bring you further updates as this story develops. This is Dawn News, signing off.",
                "For more on this and other stories, visit our website. This has been a Dawn News update.",
                "Thank you for listening to Dawn News. We'll be back with more news shortly.",
                "Keep following Dawn News for the latest updates throughout the day."
            ]
            
            # Add conversational fillers that news anchors actually use
            fillers = [
                "Now,",
                "Actually,",
                "You see,",
                "Interestingly,",
                "As we understand it,"
            ]
            
            # Select random variations for more natural sounding broadcasts
            intro = random.choice(intros)
            transition = random.choice(transitions)
            outro = random.choice(outros)
            filler = random.choice(fillers)
            
            # Build the script with more natural flow and transitions
            script = f"{intro} {title}. "
            
            if summary:
                script += f"{summary} "
                
            # Add a transition phrase and filler word to make it sound more conversational
            script += f"{transition} {filler} {brief_content} "
            
            # Add a conclusion
            script += f"{outro}"
            
            # Add small variations in wording to make it sound more natural
            script = self._add_speech_variations(script)
            
            return script
        except Exception as e:
            logger.error(f"Error creating news script: {e}")
            return f"Welcome to Dawn News Update. {article.get('title', 'Breaking News')}"
            
    def _add_speech_variations(self, text):
        """Add small variations to make speech sound more natural"""
        # Common patterns in formal writing that can be made more conversational
        replacements = [
            (r'\b(?:it is)\b', "it's"),
            (r'\b(?:that is)\b', "that's"),
            (r'\b(?:there is)\b', "there's"),
            (r'\b(?:here is)\b', "here's"),
            (r'\b(?:what is)\b', "what's"),
            (r'\baccording to the\b', "according to"),
            (r'\bin order to\b', "to"),
            (r'\bdespite the fact that\b', "although"),
            (r'\bat this point in time\b', "now"),
            (r'\bfor the purpose of\b', "for"),
            (r'\bin the event that\b', "if"),
            (r'\bin the process of\b', "currently"),
        ]
        
        # Apply replacements with some randomness
        for pattern, replacement in replacements:
            # Only apply each replacement with 70% probability to maintain variety
            if random.random() < 0.7:
                text = re.sub(pattern, replacement, text)
                
        return text
    
    def _analyze_content_for_tone(self, text):
        """Analyze news content to determine appropriate speech tone"""
        # Simple keyword-based analysis for news tone
        serious_keywords = ['emergency', 'crisis', 'disaster', 'killed', 'died', 'tragedy', 'fatal', 
                           'war', 'death', 'catastrophe', 'accident', 'terrorist', 'attack', 'pandemic']
        
        positive_keywords = ['progress', 'success', 'achievement', 'improvement', 'celebrated', 'award',
                            'breakthrough', 'recovery', 'positive', 'accomplished', 'profit', 'won', 'victory']
        
        tech_keywords = ['technology', 'digital', 'software', 'app', 'computer', 'internet', 'online',
                        'smartphone', 'device', 'innovation', 'startup', 'tech', 'AI', 'artificial intelligence']
        
        # Count occurrences of keywords by category
        serious_count = sum(1 for word in serious_keywords if word.lower() in text.lower())
        positive_count = sum(1 for word in positive_keywords if word.lower() in text.lower())
        tech_count = sum(1 for word in tech_keywords if word.lower() in text.lower())
        
        # Determine tone based on content
        tone = "neutral"
        if serious_count > 2:
            tone = "serious"
        elif positive_count > 2:
            tone = "upbeat"
        elif tech_count > 2:
            tone = "professional"
            
        return tone

    def text_to_speech(self, text, voice):
        """Convert text to speech using ElevenLabs API directly"""
        if not self.elevenlabs_api_key:
            logger.error("ElevenLabs API key not set")
            return None
        
        try:
            # Analyze content tone for logging
            tone = self._analyze_content_for_tone(text)
            logger.info(f"Content tone: {tone} - Using voice: {voice}")
            
            # Set up ElevenLabs API request
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.elevenlabs_api_key
            }
            
            # Configure voice settings based on tone
            stability = 0.5
            similarity_boost = 0.5
            
            if tone == "serious":
                stability = 0.7
            elif tone == "upbeat":
                stability = 0.3
                similarity_boost = 0.7
            
            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity_boost
                }
            }
            
            # Make direct API request to get MP3
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                logger.info("Successfully generated audio with ElevenLabs API")
                return response.content
            else:
                logger.error(f"ElevenLabs API error: {response.status_code} - {response.text}")
                return None
            
        except Exception as e:
            logger.error(f"Error with ElevenLabs TTS: {e}")
            return None
    
    def process_articles(self, voice):
        """Process articles to generate audio files"""
        articles = self.get_latest_articles()
        logger.info(f"Found {len(articles)} articles to process")
        logger.info(f"Using voice: {voice}")
        
        results = []
        for article in articles:
            try:
                title = article.get('title', 'Unknown Article')
                logger.info(f"Processing article: {title}")
                
                # Create news script
                script = self.create_news_script(article)
                logger.info(f"Created script for article: {title} - Script length: {len(script)} chars")
                
                # Convert to speech using the specified voice
                audio_content = self.text_to_speech(script, voice=voice)
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
                        'voice': voice
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
                    'voice': voice,
                    'articles': [{'title': r['title'], 'audio_path': r['audio_path']} for r in results]
                }, f, indent=2)
            
            logger.info(f"Processed {len(results)} articles with voice {voice} - Summary saved to {summary_path}")
        
        return results

# Main function to run the script from command line
def main():
    parser = argparse.ArgumentParser(description='Generate TTS for news articles')
    parser.add_argument('--voice', type=str, default="JBFqnCBsd6RMkjVDRZzb", 
                      help='Voice ID to use for TTS (default: JBFqnCBsd6RMkjVDRZzb/George)')
    args = parser.parse_args()
    
    # Initialize TTS
    tts = EnhancedTTS()
    
    # Generate audio
    results = tts.process_articles(voice=args.voice)
    
    if results:
        print(f"Generated {len(results)} audio files using voice {args.voice}:")
        for result in results:
            print(f"- {result['title']}")
            print(f"  Audio: {result['audio_path']}")
    else:
        print("No audio files were generated.")

if __name__ == "__main__":
    main()