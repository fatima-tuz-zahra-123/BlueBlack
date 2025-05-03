# Dawn AI News Reader

An application that scrapes Dawn News articles and converts them to audio using Amazon Polly.

## Setup

1. Install the required packages:
```
pip install -r requirements.txt
```

2. Set up AWS credentials:

Option 1: Use environment variables (recommended):
```
# Windows
set AWS_ACCESS_KEY_ID=your_access_key_here
set AWS_SECRET_ACCESS_KEY=your_secret_key_here
set AWS_REGION=us-east-1

# Unix/MacOS
export AWS_ACCESS_KEY_ID=your_access_key_here
export AWS_SECRET_ACCESS_KEY=your_secret_key_here
export AWS_REGION=us-east-1
```

Option 2: Copy the example config:
```
copy aws_config.example.json aws_config.json
```
Then edit `aws_config.json` with your AWS credentials (not recommended for shared repositories).

3. Run the application:
```
python app.py
```

4. Open a browser and go to:
```
http://localhost:5000
```

## Features

- Scrapes the latest news articles from Dawn News
- Converts articles to speech using Amazon Polly
- Multiple voice options (Joanna, Matthew, Amy, Brian)
- Responsive web interface
- Automatic updates on a schedule

## Development Notes

- Never commit AWS credentials to the repository
- The application prioritizes environment variables over config files
- Always test credential loading before pushing changes