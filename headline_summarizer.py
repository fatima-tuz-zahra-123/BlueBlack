#!/usr/bin/env python
import os
import json
import logging
import google.generativeai as genai
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("summarizer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("HeadlineSummarizer")

class HeadlineSummarizer:
    """Class to handle summarization of news headlines using Google's Gemini API"""
    
    def __init__(self, api_key=None):
        """
        Initialize the headline summarizer
        
        Args:
            api_key: Google Gemini API key (optional if set as env var)
        """
        # Hardcoded API key as requested
        self.api_key = "AIzaSyArP4ANLerTCSZg5d166cviuIkYNyGwGjo"
        
        # Configure the Gemini API with the provided key
        genai.configure(api_key=self.api_key)
        logger.info("Headline Summarizer initialized with Gemini API")
            
        # Output directory for summaries
        os.makedirs("news_summaries", exist_ok=True)
    
    def _get_latest_summary_file(self):
        """Find the latest audio summary file"""
        audio_dir = 'news_audio'
        if not os.path.exists(audio_dir):
            logger.error(f"Audio directory not found: {audio_dir}")
            return None
        
        summary_files = [f for f in os.listdir(audio_dir) if f.startswith('audio_summary_')]
        if not summary_files:
            logger.error(f"No audio summary files found in {audio_dir}")
            return None
            
        latest_summary = max(summary_files)
        return os.path.join(audio_dir, latest_summary)
    
    def _extract_headlines_from_summary(self, summary_file):
        """Extract headlines and scripts from an audio summary file"""
        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary_data = json.load(f)
                
            headlines = []
            for article in summary_data.get('articles', []):
                title = article.get('title')
                audio_path = article.get('audio_path')
                
                if not title or not audio_path:
                    continue
                
                # Find the script file
                script_path = f"{os.path.splitext(audio_path)[0]}_script.txt"
                script_content = ""
                
                if os.path.exists(script_path):
                    with open(script_path, 'r', encoding='utf-8') as f:
                        script_content = f.read().strip()
                
                headlines.append({
                    "title": title,
                    "script": script_content,
                    "audio_path": audio_path
                })
            
            return headlines
        except Exception as e:
            logger.error(f"Error extracting headlines from summary: {str(e)}")
            return []

    async def summarize_headlines(self, summary_file=None):
        """
        Summarize the headlines from an audio summary file using Gemini API
        
        Args:
            summary_file: Path to the audio summary JSON file (optional)
            
        Returns:
            A top headline summary
        """
        if not self.api_key:
            logger.error("No Gemini API key provided. Cannot summarize headlines.")
            return None
            
        # If no specific file provided, use the latest
        if not summary_file:
            summary_file = self._get_latest_summary_file()
            if not summary_file:
                logger.error("No summary file found")
                return None
        
        logger.info(f"Using summary file: {summary_file}")
            
        # Extract headlines
        headlines = self._extract_headlines_from_summary(summary_file)
        if not headlines:
            logger.warning("No headlines found to summarize.")
            return None
            
        # Format headlines for Gemini
        headline_texts = []
        for i, h in enumerate(headlines, 1):
            headline_texts.append(f"{i}. {h['title']}")
            
        prompt = f"""
        Here are the latest news headlines:
        
        {chr(10).join(headline_texts)}
        
        Based on these headlines, create a single comprehensive news update that covers the most important story. 
        Focus on what would be the top breaking news. Create a concise and professional summary that a news anchor
        would read to introduce the day's top news. Keep it under 100 words and make it engaging.
        """
        
        try:
            # Initialize Gemini model
            model = genai.GenerativeModel('gemini-pro')
            
            logger.info(f"Sending prompt to Gemini API: {prompt[:100]}...")
            
            # Generate summary
            response = model.generate_content(prompt)
            
            if not response or not hasattr(response, 'text'):
                logger.error("Received empty response from Gemini API")
                return None
                
            top_headline_summary = response.text.strip()
            logger.info(f"Generated top headline summary ({len(top_headline_summary)} chars)")
            
            if not top_headline_summary:
                logger.error("Generated summary is empty")
                return None
            
            # Save summary to file
            timestamp = datetime.now().strftime("%Y%m%d%H%M")
            summary_output_path = f"news_summaries/top_headline_{timestamp}.txt"
            
            with open(summary_output_path, 'w', encoding='utf-8') as f:
                f.write(top_headline_summary)
            
            logger.info(f"Top headline summary saved to {summary_output_path}")
            
            return {
                "summary": top_headline_summary,
                "summary_file": summary_output_path,
                "timestamp": timestamp,
                "headlines": [h["title"] for h in headlines[:5]]  # Include top 5 headlines
            }
            
        except Exception as e:
            logger.error(f"Error generating summary with Gemini API: {str(e)}", exc_info=True)
            return None
            
    def generate_top_headline_audio(self, summary=None, voice="Joanna"):
        """
        Generate audio for a top headline summary using Amazon Polly
        
        Args:
            summary: The summary text to convert to audio (optional)
            voice: The Amazon Polly voice to use
            
        Returns:
            Path to the generated audio file
        """
        import subprocess
        
        try:
            if not summary:
                # Find latest summary file
                summary_dir = 'news_summaries'
                if not os.path.exists(summary_dir):
                    logger.error(f"Summary directory not found: {summary_dir}")
                    return None
                
                summary_files = [f for f in os.listdir(summary_dir) if f.startswith('top_headline_')]
                if not summary_files:
                    logger.error(f"No top headline summary files found")
                    return None
                    
                latest_summary_file = os.path.join(summary_dir, max(summary_files))
                
                # Read the summary content
                with open(latest_summary_file, 'r', encoding='utf-8') as f:
                    summary = f.read().strip()
            
            if not summary:
                logger.error("No summary text provided to generate audio")
                return None
            
            # Create a temporary script file for the top headline
            timestamp = datetime.now().strftime("%Y%m%d%H%M")
            headline_title = "Top_Headlines_Summary"
            script_filename = f"news_audio/{headline_title}_{timestamp}_script.txt"
            audio_filename = f"news_audio/{headline_title}_{timestamp}.mp3"
            
            # Save the script
            with open(script_filename, 'w', encoding='utf-8') as f:
                f.write(summary)
            
            logger.info(f"Saved top headline script to {script_filename}")
            
            # Use polly_tts.py to generate audio
            from polly_tts import PollyTTS
            
            # Initialize Polly TTS
            tts = PollyTTS()
            
            # Generate audio
            result = tts.synthesize_text(summary, audio_filename, voice)
            
            if result:
                logger.info(f"Generated top headline audio: {audio_filename}")
                return {
                    "audio_path": audio_filename,
                    "script_path": script_filename,
                    "title": "Breaking News Summary",
                    "timestamp": timestamp
                }
            else:
                logger.error("Failed to generate audio for top headline")
                return None
                
        except Exception as e:
            logger.error(f"Error generating top headline audio: {str(e)}")
            return None
            
    async def generate_top_headline_video(self, summary=None, voice="Joanna"):
        """
        Generate a video for the top headlines using D-ID
        
        Args:
            summary: The summary text (optional)
            voice: The voice to use for audio
            
        Returns:
            Path to the generated video file
        """
        try:
            # First generate the audio
            audio_result = self.generate_top_headline_audio(summary, voice)
            if not audio_result:
                return None
            
            # Use DID Video Generator to create a video
            from did_video_generator import DIDVideoGenerator
            
            # Initialize video generator with Basic authentication
            api_key = "YXNtYWltcmFuY2hhdWRocnlAZ21haWwuY29t:y_SS9YofYUdlk50ux6ygV"
            username, password = api_key.split(':', 1)
            auth_str = os.popen(f"echo -n '{username}:{password}' | base64").read().strip()
            
            video_gen = DIDVideoGenerator(api_key)
            video_gen.headers = {
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Generate video
            logger.info(f"Generating video for top headline with audio: {audio_result['audio_path']}")
            video_path = video_gen.create_talk(
                audio_result['audio_path'], 
                "Breaking News Summary",
                output_filename=f"news_videos/Top_Headlines_Summary_{audio_result['timestamp']}.mp4"
            )
            
            if video_path:
                logger.info(f"Generated top headline video: {video_path}")
                return {
                    "video_path": video_path,
                    "audio_path": audio_result['audio_path'],
                    "script_path": audio_result['script_path'],
                    "title": "Breaking News Summary",
                    "timestamp": audio_result['timestamp']
                }
            else:
                logger.error("Failed to generate video for top headline")
                return None
                
        except Exception as e:
            logger.error(f"Error generating top headline video: {str(e)}")
            return None

# Main function to run as a standalone script
def main():
    import argparse
    import asyncio
    
    parser = argparse.ArgumentParser(description='Generate headline summaries using Gemini API')
    parser.add_argument('--api-key', type=str, help='Google Gemini API key')
    parser.add_argument('--summary', type=str, help='Path to audio summary JSON file')
    
    args = parser.parse_args()
    
    # Initialize headline summarizer
    summarizer = HeadlineSummarizer(api_key=args.api_key)
    
    # Run the summarizer
    asyncio.run(summarizer.summarize_headlines(args.summary))

if __name__ == "__main__":
    main()