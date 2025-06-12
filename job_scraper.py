import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
from datetime import datetime, timedelta
import time
import random
import re
from urllib.parse import urljoin, quote_plus
import hashlib
from dataclasses import dataclass
from typing import List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Job:
    title: str
    company: str
    location: str
    salary: str
    source: str
    url: str
    description: str
    priority: bool
    scraped_date: str
    job_id: str

class EnhancedJobScraper:
    def __init__(self):
        self.jobs = []
        self.keywords = [
            'cinematographer', 'director of photography', 'dop', 'dp',
            'camera operator', 'camera assistant', 'focus puller',
            'gaffer', 'lighting director', 'steadicam operator'
        ]
        
        # Rotating user agents to avoid blocks
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        self.session = requests.Session()
        self.setup_session()
    
    def setup_session(self):
        """Configure session with appropriate settings"""
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def get_random_headers(self):
        """Get random headers to avoid detection"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
    
    def make_request(self, url, retries=3, delay=2):
        """Make HTTP request with retries and error handling"""
        for attempt in range(retries):
            try:
                headers = self.get_random_headers()
                response = self.session.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # Rate limited
                    wait_time = delay * (2 ** attempt) + random.uniform(1, 3)
                    logger.warning(f"Rate limited, waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < retries - 1:
                    time.sleep(delay * (attempt + 1))
        
        return None
    
    def generate_job_id(self, title, company, location):
        """Generate unique job ID"""
        content = f"{title}-{company}-{location}".lower()
        return hashlib.md5(content.encode()).hexdigest()[:10]
    
    def scrape_staffmeup(self):
        """Scrape StaffMeUp - Premier film industry job board"""
        jobs = []
        base_url = "https://www.staffmeup.com"
        
        try:
            # StaffMeUp camera department jobs
            search_urls = [
                f"{base_url}/jobs?dept=camera",
                f"{base_url}/jobs?dept=camera&keywords=cinematographer",
                f"{base_url}/jobs?dept=camera&keywords=director+photography",
            ]
            
            for url in search_urls:
                logger.info(f"Scraping StaffMeUp: {url}")
                response = self.make_request(url)
                
                if not response:
                    continue
                
                soup = BeautifulSoup(response.content, 'html.parser')
                job_cards = soup.find_all('div', class_='job-card') or soup.find_all('div', {'data-job-id': True})
                
                for card in job_cards[:10]:
                    try:
                        title_elem = card.find('h3') or card.find('h2') or card.find('a', class_='job-title')
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text().strip()
                        
                        if not self.is_relevant_job(title):
                            continue
                        
                        company_elem = card.find('div', class_='company') or card.find('span', class_='company-name')
                        company = company_elem.get_text().strip() if company_elem else 'Company Not Listed'
                        
                        location_elem = card.find('div', class_='location') or card.find('span', class_='location')
                        location = location_elem.get_text().strip() if location_elem else 'Location Not Listed'
                        
                        link_elem = card.find('a')
                        job_url = urljoin(base_url, link_elem['href']) if link_elem and link_elem.get('href') else ''
                        
                        # Get job description if available
                        desc_elem = card.find('div', class_='description') or card.find('p')
                        description = desc_elem.get_text().strip()[:200] if desc_elem else ''
                        
                        jobs.append(Job(
                            title=title,
                            company=company,
                            location=location,
                            salary='Check listing',
                            source='StaffMeUp',
                            url=job_url,
                            description=description,
                            priority=self.is_priority_job(title),
                            scraped_date=datetime.now().strftime('%Y-%m-%d'),
                            job_id=self.generate_job_id(title, company, location)
                        ))
                        
                    except Exception as e:
                        logger.error(f"Error parsing StaffMeUp job card: {e}")
                        continue
                
                time.sleep(random.uniform(3, 6))
            
        except Exception as e:
            logger.error(f"Error scraping StaffMeUp: {e}")
        
        logger.info(f"Found {len(jobs)} jobs from StaffMeUp")
        return jobs
    
    def scrape_productionhub(self):
        """Scrape ProductionHUB jobs"""
        jobs = []
        base_url = "https://www.productionhub.com"
        
        try:
            search_terms = ['cinematographer', 'director-of-photography', 'camera-operator']
            
            for term in search_terms:
                url = f"{base_url}/jobs/search?q={term}"
                logger.info(f"Scraping ProductionHUB: {url}")
                
                response = self.make_request(url)
                if not response:
                    continue
                
                soup = BeautifulSoup(response.content, 'html.parser')
                job_listings = soup.find_all('div', class_='job-listing') or soup.find_all('article')
                
                for listing in job_listings[:8]:
                    try:
                        title_elem = listing.find('h2') or listing.find('h3') or listing.find('a', class_='job-title')
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text().strip()
                        
                        if not self.is_relevant_job(title):
                            continue
                        
                        company_elem = listing.find('div', class_='company') or listing.find('span', class_='employer')
                        company = company_elem.get_text().strip() if company_elem else 'Company Not Listed'
                        
                        location_elem = listing.find('div', class_='location') or listing.find('span', class_='location')
                        location = location_elem.get_text().strip() if location_elem else 'Location Not Listed'
                        
                        link_elem = listing.find('a')
                        job_url = urljoin(base_url, link_elem['href']) if link_elem and link_elem.get('href') else ''
                        
                        jobs.append(Job(
                            title=title,
                            company=company,
                            location=location,
                            salary='Check listing',
                            source='ProductionHUB',
                            url=job_url,
                            description='',
                            priority=self.is_priority_job(title),
                            scraped_date=datetime.now().strftime('%Y-%m-%d'),
                            job_id=self.generate_job_id(title, company, location)
                        ))
                        
                    except Exception as e:
                        logger.error(f"Error parsing ProductionHUB job: {e}")
                        continue
                
                time.sleep(random.uniform(2, 4))
            
        except Exception as e:
            logger.error(f"Error scraping ProductionHUB: {e}")
        
        logger.info(f"Found {len(jobs)} jobs from ProductionHUB")
        return jobs
    
    def scrape_mandy_network(self):
        """Scrape Mandy Network (UK/European focus)"""
        jobs = []
        base_url = "https://www.mandy.com"
        
        try:
            # Mandy Network crew jobs
            urls = [
                f"{base_url}/uk/crew-jobs/camera",
                f"{base_url}/uk/crew-jobs/lighting",
                f"{base_url}/us/crew-jobs/camera",
            ]
            
            for url in urls:
                logger.info(f"Scraping Mandy Network: {url}")
                response = self.make_request(url)
                
                if not response:
                    continue
                
                soup = BeautifulSoup(response.content, 'html.parser')
                job_items = soup.find_all('div', class_='job') or soup.find_all('article', class_='job-listing')
                
                for item in job_items[:8]:
                    try:
                        title_elem = item.find('h2') or item.find('h3') or item.find('a', class_='job-title')
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text().strip()
                        
                        if not self.is_relevant_job(title):
                            continue
                        
                        company_elem = item.find('div', class_='company') or item.find('span', class_='client')
                        company = company_elem.get_text().strip() if company_elem else 'Production Company'
                        
                        location_elem = item.find('div', class_='location') or item.find('span', class_='location')
                        location = location_elem.get_text().strip() if location_elem else 'UK/Europe'
                        
                        link_elem = item.find('a')
                        job_url = urljoin(base_url, link_elem['href']) if link_elem and link_elem.get('href') else ''
                        
                        jobs.append(Job(
                            title=title,
                            company=company,
                            location=location,
                            salary='Negotiable',
                            source='Mandy Network',
                            url=job_url,
                            description='',
                            priority=self.is_priority_job(title),
                            scraped_date=datetime.now().strftime('%Y-%m-%d'),
                            job_id=self.generate_job_id(title, company, location)
                        ))
                        
                    except Exception as e:
                        logger.error(f"Error parsing Mandy Network job: {e}")
                        continue
                
                time.sleep(random.uniform(3, 5))
            
        except Exception as e:
            logger.error(f"Error scraping Mandy Network: {e}")
        
        logger.info(f"Found {len(jobs)} jobs from Mandy Network")
        return jobs
    
    def scrape_glassdoor(self):
        """Scrape Glassdoor for studio and production company jobs"""
        jobs = []
        
        try:
            search_terms = ['cinematographer', 'director of photography', 'camera operator']
            locations = ['United States', 'United Kingdom', 'Canada']
            
            for term in search_terms[:2]:  # Limit to avoid rate limiting
                for location in locations[:2]:
                    url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={quote_plus(term)}&locT=N&locId={quote_plus(location)}"
                    
                    logger.info(f"Scraping Glassdoor: {term} in {location}")
                    response = self.make_request(url)
                    
                    if not response:
                        continue
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    job_cards = soup.find_all('div', {'data-test': 'jobListing'}) or soup.find_all('li', class_='react-job-listing')
                    
                    for card in job_cards[:5]:
                        try:
                            title_elem = card.find('a', {'data-test': 'job-title'}) or card.find('h2')
                            if not title_elem:
                                continue
                            
                            title = title_elem.get_text().strip()
                            
                            if not self.is_relevant_job(title):
                                continue
                            
                            company_elem = card.find('div', {'data-test': 'employer-name'}) or card.find('span', class_='employerName')
                            company = company_elem.get_text().strip() if company_elem else 'Company Not Listed'
                            
                            location_elem = card.find('div', {'data-test': 'job-location'}) or card.find('div', class_='compactLocation')
                            job_location = location_elem.get_text().strip() if location_elem else location
                            
                            link_elem = title_elem if title_elem.name == 'a' else card.find('a')
                            job_url = urljoin('https://www.glassdoor.com', link_elem['href']) if link_elem and link_elem.get('href') else ''
                            
                            jobs.append(Job(
                                title=title,
                                company=company,
                                location=job_location,
                                salary='Check listing',
                                source='Glassdoor',
                                url=job_url,
                                description='',
                                priority=self.is_priority_job(title),
                                scraped_date=datetime.now().strftime('%Y-%m-%d'),
                                job_id=self.generate_job_id(title, company, job_location)
                            ))
                            
                        except Exception as e:
                            logger.error(f"Error parsing Glassdoor job: {e}")
                            continue
                    
                    time.sleep(random.uniform(4, 7))
            
        except Exception as e:
            logger.error(f"Error scraping Glassdoor: {e}")
        
        logger.info(f"Found {len(jobs)} jobs from Glassdoor")
        return jobs
    
    def scrape_indeed_enhanced(self):
        """Enhanced Indeed scraper with better error handling"""
        jobs = []
        
        try:
            locations = ['United Kingdom', 'Germany', 'France', 'United States', 'Canada', 'Australia']
            search_terms = ['cinematographer', 'director of photography', 'camera operator']
            
            for location in locations[:3]:  # Limit locations
                for term in search_terms[:2]:  # Limit terms
                    try:
                        url = f"https://www.indeed.com/jobs?q={quote_plus(term)}&l={quote_plus(location)}"
                        logger.info(f"Scraping Indeed: {term} in {location}")
                        
                        response = self.make_request(url)
                        if not response:
                            continue
                        
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Multiple selectors for Indeed's changing structure
                        job_cards = (soup.find_all('div', {'data-jk': True}) or 
                                   soup.find_all('div', class_='job_seen_beacon') or
                                   soup.find_all('div', class_='slider_container'))
                        
                        for card in job_cards[:5]:
                            try:
                                # Try multiple title selectors
                                title_elem = (card.find('h2', class_='jobTitle') or
                                            card.find('a', {'data-jk': True}) or
                                            card.find('span', {'title': True}))
                                
                                if not title_elem:
                                    continue
                                
                                title = title_elem.get('title') or title_elem.get_text().strip()
                                
                                if not self.is_relevant_job(title):
                                    continue
                                
                                # Company name
                                company_elem = (card.find('span', {'data-testid': 'company-name'}) or
                                              card.find('a', {'data-testid': 'company-name'}) or
                                              card.find('div', class_='companyName'))
                                company = company_elem.get_text().strip() if company_elem else 'Company Not Listed'
                                
                                # Location
                                location_elem = (card.find('div', {'data-testid': 'job-location'}) or
                                               card.find('div', class_='compactLocation'))
                                job_location = location_elem.get_text().strip() if location_elem else location
                                
                                # Job URL
                                link_elem = card.find('a', {'data-jk': True}) or title_elem
                                job_url = f"https://www.indeed.com{link_elem['href']}" if link_elem and link_elem.get('href') else ''
                                
                                # Salary
                                salary_elem = (card.find('span', class_='estimated-salary') or
                                             card.find('div', class_='salary-snippet'))
                                salary = salary_elem.get_text().strip() if salary_elem else 'Salary not listed'
                                
                                jobs.append(Job(
                                    title=title,
                                    company=company,
                                    location=job_location,
                                    salary=salary,
                                    source='Indeed',
                                    url=job_url,
                                    description='',
                                    priority=self.is_priority_job(title),
                                    scraped_date=datetime.now().strftime('%Y-%m-%d'),
                                    job_id=self.generate_job_id(title, company, job_location)
                                ))
                                
                            except Exception as e:
                                logger.error(f"Error parsing Indeed job card: {e}")
                                continue
                        
                        time.sleep(random.uniform(3, 6))
                        
                    except Exception as e:
                        logger.error(f"Error scraping Indeed for {term} in {location}: {e}")
                        continue
            
        except Exception as e:
            logger.error(f"Error in Indeed scraper: {e}")
        
        logger.info(f"Found {len(jobs)} jobs from Indeed")
        return jobs
    
    def scrape_social_media_jobs(self):
        """
        Social media scraping placeholder - NOTE: This requires special handling
        
        IMPORTANT: Facebook, Instagram, and Threads require:
        1. API access (not web scraping)
        2. Authentication tokens
        3. Compliance with their Terms of Service
        
        For production use, you should:
        1. Use Facebook Graph API for Facebook Groups
        2. Use Instagram Graph API (limited access)
        3. Use Threads API when available
        4. Consider RSS feeds from public film job groups
        """
        jobs = []
        
        # This is a placeholder - in real implementation you would:
        # 1. Use official APIs
        # 2. Get proper authentication
        # 3. Follow rate limits and ToS
        
        logger.info("Social media scraping requires API access - placeholder implementation")
        
        # Example structure for when you implement API-based scraping:
        sample_social_jobs = [
            Job(
                title="Cinematographer Needed - Short Film",
                company="Independent Filmmaker",
                location="Los Angeles, CA",
                salary="$500/day",
                source="Film Jobs Facebook Group",
                url="https://facebook.com/groups/filmjobs",
                description="Looking for experienced DP for narrative short film",
                priority=True,
                scraped_date=datetime.now().strftime('%Y-%m-%d'),
                job_id=self.generate_job_id("Cinematographer Needed", "Independent", "LA")
            )
        ]
        
        return sample_social_jobs
    
    def is_relevant_job(self, title):
        """Enhanced relevance checking"""
        relevant_keywords = [
            'cinematographer', 'director of photography', 'dop', 'dp',
            'camera operator', 'camera assistant', 'focus puller',
            'steadicam', 'gaffer', 'lighting director', 'camera department',
            'video production', 'film production', 'camera crew'
        ]
        
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in relevant_keywords)
    
    def is_priority_job(self, title):
        """Enhanced priority detection"""
        priority_keywords = [
            'tv series', 'television', 'feature film', 'netflix', 'hbo', 'amazon',
            'disney', 'apple tv', 'paramount', 'warner', 'universal', 'sony',
            'drama series', 'narrative', 'cinema', 'movie', 'theatrical',
            'streaming', 'limited series', 'pilot', 'season'
        ]
        
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in priority_keywords)
    
    def is_target_location(self, location):
        """Enhanced location filtering"""
        target_locations = [
            # North America
            'usa', 'united states', 'california', 'los angeles', 'hollywood',
            'new york', 'atlanta', 'chicago', 'toronto', 'vancouver', 'montreal',
            'canada', 'texas', 'florida', 'georgia', 'north carolina',
            # Europe
            'uk', 'united kingdom', 'london', 'england', 'scotland', 'wales',
            'france', 'paris', 'germany', 'berlin', 'munich', 'spain', 'madrid',
            'italy', 'rome', 'milan', 'netherlands', 'amsterdam', 'belgium',
            'sweden', 'norway', 'denmark', 'ireland', 'dublin',
            # Other
            'australia', 'sydney', 'melbourne', 'new zealand', 'auckland'
        ]
        
        location_lower = location.lower()
        return any(loc in location_lower for loc in target_locations)
    
    def remove_duplicates(self, jobs: List[Job]) -> List[Job]:
        """Remove duplicate jobs based on job_id"""
        seen_ids = set()
        unique_jobs = []
        
        for job in jobs:
            if job.job_id not in seen_ids:
                seen_ids.add(job.job_id)
                unique_jobs.append(job)
        
        return unique_jobs
    
    def scrape_all(self):
        """Scrape all job sources"""
        logger.info("🎬 Starting comprehensive job scraping...")
        
        all_jobs = []
        
        # Scrape all sources
        scrapers = [
            self.scrape_staffmeup,
            self.scrape_productionhub,
            self.scrape_mandy_network,
            self.scrape_glassdoor,
            self.scrape_indeed_enhanced,
            self.scrape_social_media_jobs,
        ]
        
        for scraper in scrapers:
            try:
                jobs = scraper()
                all_jobs.extend(jobs)
                logger.info(f"Total jobs so far: {len(all_jobs)}")
            except Exception as e:
                logger.error(f"Error in scraper {scraper.__name__}: {e}")
                continue
        
        # Filter and process jobs
        logger.info("Processing and filtering jobs...")
        
        # Filter for target locations
        location_filtered = [job for job in all_jobs if self.is_target_location(job.location)]
        logger.info(f"After location filtering: {len(location_filtered)} jobs")
        
        # Remove duplicates
        unique_jobs = self.remove_duplicates(location_filtered)
        logger.info(f"After removing duplicates: {len(unique_jobs)} jobs")
        
        # Sort by priority and date
        sorted_jobs = sorted(unique_jobs, key=lambda x: (x.priority, x.scraped_date), reverse=True)
        
        # Limit to top 20 jobs
        final_jobs = sorted_jobs[:20]
        
        logger.info(f"✅ Final job count: {len(final_jobs)}")
        return final_jobs

def send_email_alert(jobs: List[Job], recipient_email: str):
    """Enhanced email sending with better formatting"""
    
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')
    
    if not sender_email or not sender_password:
        logger.error("Email credentials not configured")
        return
    
    if not jobs:
        logger.warning("No jobs to send")
        return
    
    # Count priority jobs and sources
    priority_count = sum(1 for job in jobs if job.priority)
    sources = list(set(job.source for job in jobs))
    
    # Create email content
    subject = f"🎬 Cinematographer Jobs Alert - {len(jobs)} Opportunities ({priority_count} Priority)"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; background-color: #f5f7fa; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px 30px; text-align: center; }}
            .header h1 {{ margin: 0 0 10px 0; font-size: 28px; font-weight: 600; }}
            .header p {{ margin: 0; opacity: 0.9; font-size: 16px; }}
            .stats {{ background: #f8f9fc; padding: 20px 30px; border-bottom: 1px solid #e1e5e9; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; text-align: center; }}
            .stat {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .stat-number {{ font-size: 24px; font-weight: bold; color: #4c51bf; }}
            .stat-label {{ font-size: 12px; color: #6b7280; text-transform: uppercase; }}
            .sources {{ padding: 20px 30px; background: #f0f4f8; }}
            .sources-list {{ display: flex; flex-wrap: wrap; gap: 10px; }}
            .source-tag {{ background: #4c51bf; color: white; padding: 5px 10px; border-radius: 15px; font-size: 12px; }}
            .job-card {{ margin: 0 30px 20px 30px; padding: 25px; border-left: 4px solid #e1e5e9; background: #fafbfc; }}
            .job-card.priority {{ border-left-color: #f56565; background: #fef5f5; }}
            .job-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px; }}
            .job-title {{ font-size: 18px; font-weight: 600; color: #2d3748; margin: 0; }}
            .priority-badge {{ background: #f56565; color: white; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: 500; }}
            .job-company {{ font-size: 16px; color: #4a5568; margin: 5px 0; }}
            .job-details {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 15px 0; }}
            .detail-item {{ font-size: 14px; color: #6b7280; }}
            .detail-label {{ font-weight: 500; color: #374151; }}
            .job-description {{ font-size: 14px; color: #4a5568; margin: 10px 0; font-style
