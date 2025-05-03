import requests
from bs4 import BeautifulSoup
import json
import os
import datetime
import time
import schedule
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("DawnScraper")

class DawnNewsScraper:
    def __init__(self):
        self.base_url = "https://www.dawn.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.data_dir = "scraped_news"
        # Create directory if it doesn't exist
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
    
    def fetch_page(self, url):
        """Fetch the HTML content of a page"""
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def extract_headlines(self, html_content):
        """Extract headlines from the Dawn homepage"""
        soup = BeautifulSoup(html_content, 'html.parser')
        articles = []
        
        # Find featured articles
        featured_articles = soup.find_all('article', class_='story')
        
        for article in featured_articles:
            try:
                # Look for different heading patterns - Dawn's website might have multiple formats
                headline_elem = article.find(['h2', 'h3', 'h4'])
                if not headline_elem:
                    # Try finding direct link with title
                    link_elem = article.find('a', href=True)
                    if link_elem:
                        title = link_elem.get_text().strip() or link_elem.get('title', '').strip()
                        url = link_elem.get('href')
                        
                        # If still no title, try getting it from the URL
                        if not title:
                            title = url.split('/')[-1].replace('-', ' ').title()
                            
                        # Make sure URL is absolute
                        if not url.startswith('http'):
                            url = self.base_url + url
                        
                        articles.append({
                            'title': title,
                            'url': url
                        })
                    continue
                    
                link_elem = headline_elem.find('a')
                if not link_elem or not link_elem.get('href'):
                    continue
                    
                title = link_elem.get_text().strip()
                url = link_elem.get('href')
                
                # Make sure URL is absolute
                if not url.startswith('http'):
                    url = self.base_url + url
                
                articles.append({
                    'title': title,
                    'url': url
                })
            except Exception as e:
                logger.error(f"Error extracting headline: {e}")
        
        # If no articles found with standard approach, try alternative selectors
        if not articles:
            try:
                story_links = soup.select('a.story__link')
                for link in story_links:
                    title = link.get_text().strip()
                    url = link.get('href')
                    if url and not url.startswith('http'):
                        url = self.base_url + url
                    
                    if title and url:
                        articles.append({
                            'title': title,
                            'url': url
                        })
            except Exception as e:
                logger.error(f"Error extracting headlines with alternative method: {e}")
        
        return articles
    
    def extract_article_content(self, article_info):
        """Extract the content of an article"""
        url = article_info['url']
        html_content = self.fetch_page(url)
        if not html_content:
            return None
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        try:
            # Find article header
            header = soup.find('div', class_='story__header')
            title = article_info['title']  # Use the title from the homepage
            
            if not title:  # If title is still empty, try to extract from article page
                title_elem = soup.find(['h1', 'h2'], class_=['story__title', 'article-title'])
                if title_elem:
                    title = title_elem.get_text().strip()
            
            # Find published date
            date_elem = soup.find('span', class_='story__time')
            if not date_elem:
                date_elem = soup.find('span', class_='timestamp')
            published_date = date_elem.get_text().strip() if date_elem else ""
            
            # Find article content
            content_div = soup.find('div', class_='story__content')
            if not content_div:
                content_div = soup.find('div', class_=['article-content', 'entry-content', 'story-content'])
            
            if not content_div:
                logger.warning(f"Could not find content for article: {url}")
                return None
                
            # Extract paragraphs
            paragraphs = content_div.find_all('p')
            content = ' '.join([p.get_text().strip() for p in paragraphs])
            
            # Extract summary
            summary = ""
            summary_elem = soup.find('div', class_='story__excerpt')
            if not summary_elem:
                summary_elem = soup.find(['div', 'p'], class_=['summary', 'excerpt', 'article-summary'])
            if summary_elem:
                summary = summary_elem.get_text().strip()
                
            return {
                'title': title,
                'url': url,
                'published_date': published_date,
                'summary': summary,
                'content': content,
                'scraped_at': datetime.datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return None
    
    def save_article(self, article_data):
        """Save article data to a JSON file"""
        if not article_data:
            return
        
        # Log the title that's being saved
        logger.info(f"Saving article: {article_data['title']}")
            
        # Create a filename based on article title
        filename = "".join(c if c.isalnum() else "_" for c in article_data['title'])
        if not filename:  # If title is empty, use part of the URL
            filename = article_data['url'].split('/')[-1]
        filename = f"{filename}_{datetime.datetime.now().strftime('%Y%m%d%H%M')}.json"
        filepath = os.path.join(self.data_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(article_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved article: {article_data['title']}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving article: {e}")
            return None
    
    def get_latest_articles(self, limit=5):
        """Scrape the latest articles from Dawn News"""
        html_content = self.fetch_page(self.base_url)
        if not html_content:
            logger.error("Failed to fetch Dawn homepage")
            return []
            
        headlines = self.extract_headlines(html_content)
        logger.info(f"Found {len(headlines)} headlines")
        
        articles = []
        # Limit the number of articles to process
        for headline in headlines[:limit]:
            article_data = self.extract_article_content(headline)
            if article_data:
                filepath = self.save_article(article_data)
                if filepath:
                    articles.append(article_data)
                    
        return articles
    
    def run_scraper(self):
        """Run the scraper once"""
        logger.info("Starting Dawn News scraping job")
        try:
            articles = self.get_latest_articles()
            logger.info(f"Successfully scraped {len(articles)} articles")
            
            # Save a summary of the latest scrape
            summary = {
                'timestamp': datetime.datetime.now().isoformat(),
                'articles_count': len(articles),
                'articles': [{'title': a['title'], 'url': a['url']} for a in articles]
            }
            
            with open(os.path.join(self.data_dir, 'latest_scrape.json'), 'w') as f:
                json.dump(summary, f, indent=2)
                
            return articles
        except Exception as e:
            logger.error(f"Error in scraper job: {e}")
            return []

# Function to run the scraper job
def scrape_dawn_news():
    scraper = DawnNewsScraper()
    return scraper.run_scraper()

# Schedule the job to run every hour
def schedule_scraping():
    schedule.every(1).hour.do(scrape_dawn_news)
    logger.info("Scheduled scraping job to run every hour")
    
    # Run once immediately
    scrape_dawn_news()
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Wait one minute between checks

if __name__ == "__main__":
    logger.info("Dawn News Scraper initialized")
    schedule_scraping()