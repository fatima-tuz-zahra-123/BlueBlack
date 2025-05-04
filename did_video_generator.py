#!/usr/bin/env python
import os
import json
import requests
import logging
import time
import argparse
from pathlib import Path
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("did_video.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DIDVideoGenerator")

class DIDVideoGenerator:
    """Class to handle generation of news anchor videos using D-ID API"""
    
    def __init__(self, api_key, presenter_id="pexgnAgcTC"):
        """
        Initialize the D-ID video generator
        
        Args:
            api_key: The D-ID API key
            presenter_id: ID of the presenter to use (default is a professional news anchor look)
        """
        self.api_key = api_key
        self.presenter_id = presenter_id
        self.base_url = "https://api.d-id.com"
        
        # The D-ID API key in the format username:password requires Basic auth
        if ':' in api_key:
            username, password = api_key.split(':', 1)
            auth_str = base64.b64encode(f"{username}:{password}".encode('utf-8')).decode('utf-8')
            self.headers = {
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/json",
                "accept": "application/json"
            }
        else:
            # If not in username:password format, use as a normal Bearer token
            self.headers = {
                "Authorization": f"Basic {api_key}",
                "Content-Type": "application/json",
                "accept": "application/json"
            }
        
        # Create output directory
        os.makedirs("news_videos", exist_ok=True)
        logger.info("D-ID Video Generator initialized")
    
    def create_talk(self, audio_path, title, output_filename=None):
        """
        Create a talking video using the D-ID API with the provided audio file
        
        Args:
            audio_path: Path to the audio file
            title: Title of the news article
            output_filename: Output filename for the video, if None will be generated based on title
            
        Returns:
            Path to the generated video file
        """
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            return None
            
        # Create output filename if not provided
        if output_filename is None:
            audio_filename = os.path.basename(audio_path)
            base_name = os.path.splitext(audio_filename)[0]
            output_filename = f"news_videos/{base_name}.mp4"
        
        # Check if video already exists
        if os.path.exists(output_filename):
            logger.info(f"Video already exists: {output_filename}")
            return output_filename
            
        logger.info(f"Creating video for news article: {title}")
        logger.info(f"Using audio file: {audio_path}")
        
        try:
            # For now, we'll use a professional presenter image from D-ID's default presenters
            presenter_img = "https://create-images-results.d-id.com/DefaultPresenters/Anika_f/image.jpeg"
            
            # Create the talking video
            create_url = f"{self.base_url}/talks"
            
            # Read the script text if it exists
            script_path = f"{os.path.splitext(audio_path)[0]}_script.txt"
            script_text = "This is a news report from Dawn News."
            
            if os.path.exists(script_path):
                try:
                    with open(script_path, 'r', encoding='utf-8') as f:
                        raw_script = f.read().strip()
                    
                    if raw_script:
                        # Clean up the script - remove any existing SSML tags
                        script_text = raw_script.replace('<speak>', '').replace('</speak>', '')
                        logger.info(f"Using script text from: {script_path}")
                except Exception as e:
                    logger.error(f"Error reading script file: {str(e)}")
            
            # Prepare the payload for D-ID's API
            payload = {
                "script": {
                    "type": "text",
                    "input": script_text,  # Plain text without SSML tags
                    "provider": {
                        "type": "microsoft",
                        "voice_id": "en-US-JennyNeural"
                    }
                },
                "source": {
                    "type": "image",
                    "image": presenter_img
                },
                "config": {
                    "fluent": True,
                    "pad_audio": 0,
                    "stitch": True,
                    "result_format": "mp4"
                },
                "name": title
            }
            
            logger.info("Sending request to D-ID API")
            logger.info(f"Headers: {self.headers}")
            logger.info(f"Payload snippet: {json.dumps(payload)[:500]}...")  # Only log the beginning of the payload to avoid too much output
            
            response = requests.post(create_url, headers=self.headers, json=payload)
            
            # Log the detailed response for debugging
            logger.info(f"Response status code: {response.status_code}")
            logger.info(f"Response headers: {response.headers}")
            logger.info(f"Response text: {response.text}")
            
            # Check for insufficient credits error specifically
            if response.status_code == 402 and "InsufficientCreditsError" in response.text:
                logger.warning("Your D-ID account has insufficient credits. Please add credits to your account or use a different video generation service.")
                # Create a placeholder file with no content to prevent repeated attempts
                Path(output_filename).touch()
                return None
                
            response.raise_for_status()
            
            # Get the talk ID from the response
            talk_id = response.json().get("id")
            if not talk_id:
                logger.error("Failed to get talk ID from D-ID API response")
                return None
                
            logger.info(f"Video generation started with ID: {talk_id}")
            
            # Poll for completion
            return self._wait_for_completion(talk_id, output_filename)
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return None
        except requests.RequestException as e:
            logger.error(f"D-ID API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None and hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return None
    
    def _wait_for_completion(self, talk_id, output_filename, max_attempts=30, delay=10):
        """
        Poll the D-ID API until the video is ready
        
        Args:
            talk_id: The ID of the talk to check
            output_filename: Where to save the video
            max_attempts: Maximum number of polling attempts
            delay: Delay between polling attempts in seconds
            
        Returns:
            Path to the downloaded video file or None if failed
        """
        status_url = f"{self.base_url}/talks/{talk_id}"
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"Checking status of video generation (attempt {attempt+1}/{max_attempts})")
                response = requests.get(status_url, headers=self.headers)
                response.raise_for_status()
                
                status_data = response.json()
                logger.info(f"Status response: {json.dumps(status_data)}")
                
                status = status_data.get("status")
                
                if status == "done":
                    logger.info(f"Video generation completed: {talk_id}")
                    # Download the video
                    result_url = status_data.get("result_url")
                    if result_url:
                        return self._download_video(result_url, output_filename)
                    else:
                        logger.error("No result URL found in the completed response")
                        return None
                        
                elif status == "error":
                    logger.error(f"D-ID API reported an error: {status_data.get('error', 'Unknown error')}")
                    return None
                    
                logger.info(f"Current status: {status}. Waiting {delay} seconds before next check.")
                time.sleep(delay)
                
            except requests.RequestException as e:
                logger.error(f"Error checking video status: {str(e)}")
                time.sleep(delay)
                
        logger.error(f"Video generation timed out after {max_attempts} attempts")
        return None
    
    def _download_video(self, video_url, output_filename):
        """
        Download the generated video from D-ID
        
        Args:
            video_url: URL to download the video from
            output_filename: Where to save the video
            
        Returns:
            Path to the downloaded video file or None if failed
        """
        try:
            logger.info(f"Downloading video from {video_url}")
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            
            with open(output_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            logger.info(f"Video downloaded successfully to {output_filename}")
            return output_filename
            
        except requests.RequestException as e:
            logger.error(f"Error downloading video: {str(e)}")
            return None
        except IOError as e:
            logger.error(f"Error saving video file: {str(e)}")
            return None
    
    def generate_videos(self, summary_file=None):
        """Convenience method to generate videos for the latest summary"""
        if summary_file is None:
            # Find latest summary file
            audio_dir = 'news_audio'
            if os.path.exists(audio_dir):
                summary_files = [f for f in os.listdir(audio_dir) if f.startswith('audio_summary_')]
                if not summary_files:
                    logger.error(f"No audio summary files found in {audio_dir}")
                    return []
                    
                latest_summary = max(summary_files)
                summary_file = os.path.join(audio_dir, latest_summary)
            else:
                logger.error(f"Audio directory not found: {audio_dir}")
                return []
        
        return self.process_audio_summary(summary_file)
            
    def process_audio_summary(self, summary_file):
        """
        Process all audio files in a summary to create videos
        
        Args:
            summary_file: Path to the audio summary JSON file
            
        Returns:
            List of generated video paths
        """
        try:
            with open(summary_file, 'r') as f:
                summary = json.load(f)
                
            videos = []
            for article in summary.get('articles', []):
                title = article.get('title')
                audio_path = article.get('audio_path')
                
                if not title or not audio_path:
                    logger.warning(f"Skipping article with missing data: {article}")
                    continue
                    
                # Create video for this audio file
                video_path = self.create_talk(audio_path, title)
                if video_path:
                    # Add video path to the article info
                    article['video_path'] = video_path
                    videos.append(video_path)
                    
            # Update the summary with video paths
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
                
            logger.info(f"Processed {len(videos)} videos for summary {summary_file}")
            return videos
            
        except Exception as e:
            logger.error(f"Error processing audio summary: {str(e)}")
            return []

def main():
    """Main function to run the script from command line"""
    parser = argparse.ArgumentParser(description='Generate news anchor videos using D-ID API')
    parser.add_argument('--api-key', type=str, help='D-ID API key')
    parser.add_argument('--summary', type=str, help='Path to audio summary JSON file')
    parser.add_argument('--audio', type=str, help='Path to a specific audio file to process')
    parser.add_argument('--presenter', type=str, default="pexgnAgcTC", 
                        help='Presenter ID to use (default is a professional news anchor)')
    parser.add_argument('--latest', action='store_true',
                        help='Process the latest audio summary file')
    parser.add_argument('--auth-mode', choices=['bearer', 'api-key', 'basic'], default='basic',
                        help='Authentication mode to use (default: basic)')
    
    args = parser.parse_args()
    
    # Hardcoded API key as requested
    api_key = "YXNtYWltcmFuY2hhdWRocnlAZ21haWwuY29t:y_SS9YofYUdlk50ux6ygV"
    
    logger.info(f"Using {args.auth_mode} authentication")
        
    # Initialize video generator
    video_gen = DIDVideoGenerator(api_key, presenter_id=args.presenter)
    
    # Override authentication headers based on auth-mode
    if args.auth_mode == 'bearer':
        video_gen.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    elif args.auth_mode == 'api-key':
        video_gen.headers = {
            "D-ID-API-KEY": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    elif args.auth_mode == 'basic':
        # For basic auth, properly encode username and password if they're provided in a colon-separated format
        if ':' in api_key:
            username, password = api_key.split(':', 1)
            auth_str = base64.b64encode(f"{username}:{password}".encode('utf-8')).decode('utf-8')
            video_gen.headers = {
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            logger.info("Using Basic authentication with encoded credentials")
        else:
            video_gen.headers = {
                "Authorization": f"Basic {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        
    logger.info(f"Authentication headers configured: {args.auth_mode} mode")
    # Process a specific audio file
    if args.audio:
        if not os.path.exists(args.audio):
            logger.error(f"Audio file not found: {args.audio}")
            return
            
        title = os.path.splitext(os.path.basename(args.audio))[0]
        video_gen.create_talk(args.audio, title)
        return
        
    # Process the latest audio summary if --latest flag is set
    if args.latest:
        audio_dir = 'news_audio'
        if os.path.exists(audio_dir):
            summary_files = [f for f in os.listdir(audio_dir) if f.startswith('audio_summary_')]
            if not summary_files:
                logger.error(f"No audio summary files found in {audio_dir}")
                return
                
            latest_summary = max(summary_files)
            summary_file = os.path.join(audio_dir, latest_summary)
            logger.info(f"Processing latest summary file: {summary_file}")
            video_gen.process_audio_summary(summary_file)
        else:
            logger.error(f"Audio directory not found: {audio_dir}")
        return
        
    # Process a specific summary file
    if args.summary:
        if not os.path.exists(args.summary):
            logger.error(f"Summary file not found: {args.summary}")
            return
            
        video_gen.process_audio_summary(args.summary)
        return
        
    # If no specific options, show usage
    logger.info("No action specified. Use --audio, --summary, or --latest to process files.")
    parser.print_help()

if __name__ == "__main__":
    main()