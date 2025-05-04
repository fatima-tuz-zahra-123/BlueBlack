# Setting up D-ID API for the Dawn News Video Generator

This document provides step-by-step instructions for setting up and using the D-ID API with the Dawn News application to generate news anchor videos.

## Getting a D-ID API Key

1. Sign up for an account at [D-ID](https://www.d-id.com/)
2. After creating an account, go to the D-ID dashboard
3. Navigate to the API section or Developer settings
4. Create a new API key (you might need to provide payment information for API usage)
5. Copy the API key for use with the application

## Using the D-ID API Key

Use the API key with the `did_video_generator.py` script in one of these ways:

### Option 1: Command line argument

```bash
python did_video_generator.py --audio news_audio/your_audio_file.mp3 --api-key YOUR_API_KEY
```

### Option 2: Environment variable

```bash
export DID_API_KEY=YOUR_API_KEY
python did_video_generator.py --audio news_audio/your_audio_file.mp3
```

## Understanding API Usage and Costs

D-ID's API is a paid service with different pricing tiers:

- Free tier: Usually includes a limited number of API calls
- Paid tiers: Based on volume of API usage

Be aware that generating videos consumes API credits, so monitor your usage to avoid unexpected charges.

## Troubleshooting Authentication Issues

If you encounter authentication errors:

1. Verify your API key is correct and not expired
2. Try different authentication modes:
   ```bash
   python did_video_generator.py --audio your_audio.mp3 --api-key YOUR_API_KEY --auth-mode bearer
   # or
   python did_video_generator.py --audio your_audio.mp3 --api-key YOUR_API_KEY --auth-mode api-key
   ```
3. Check the D-ID dashboard to ensure your account is active and in good standing

## Advanced: Customizing the News Presenter

You can customize the presenter used in the videos:

```bash
python did_video_generator.py --audio your_audio.mp3 --api-key YOUR_API_KEY --presenter PRESENTER_ID
```

Popular presenter IDs:

- `pexgnAgcTC`: Default male presenter
- `txTQmS07aV`: Female presenter
- Visit the D-ID website to find more presenter options
