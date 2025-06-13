import requests
import feedparser
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
from datetime import datetime
import time
import random
import re
from dotenv import load_dotenv
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler

load_dotenv()  # Load environment variables from .env file

class JobScraper:
    def __init__(self):
        self.keywords = ['cinematographer', 'director of photography', 'dop', 'camera operator']

    def scrape_indeed(self):
        jobs = []
        locations = ['United Kingdom', 'Germany', 'France', 'United States', 'Canada']
        for location in locations:
            for keyword in ['cinematographer', 'director photography']:
                try:
                    url = f"https://www.indeed.com/jobs?q={keyword.replace(' ', '+')}&l={location.replace(' ', '+')}"
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    response = requests.get(url, headers=headers, timeout=10)
                    soup = BeautifulSoup(response.content, 'html.parser')
                    job_cards = soup.find_all('div', {'data-jk': True})
                    for card in job_cards[:5]:
                        try:
                            title_elem = card.find('h2', class_='jobTitle')
                            if not title_elem:
                                continue
                            title = title_elem.get_text().strip()
                            if not self.is_relevant_job(title):
                                continue
                            company = card.find('span', {'data-testid': 'company-name'})
                            location_elem = card.find('div', {'data-testid': 'job-location'})
                            job_url = f"https://www.indeed.com{title_elem.find('a')['href']}" if title_elem.find('a') else ''
                            jobs.append({
                                'title': title,
                                'company': company.get_text().strip() if company else 'Not Listed',
                                'location': location_elem.get_text().strip() if location_elem else location,
                                'salary': 'Not listed',
                                'source': 'Indeed',
                                'url': job_url,
                                'priority': self.is_priority_job(title),
                                'scraped_date': datetime.now().strftime('%Y-%m-%d')
                            })
                        except Exception as e:
                            continue
                    time.sleep(random.uniform(2, 4))
                except Exception as e:
                    print(f"Error scraping Indeed for {keyword} in {location}: {e}")
                    continue
        return jobs

    def scrape_linkedin_jobs(self):
        jobs = []
        try:
            url = "https://www.linkedin.com/jobs/search/?keywords=cinematographer"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            job_cards = soup.find_all('div', class_='base-card')
            for card in job_cards[:8]:
                try:
                    title_elem = card.find('h3', class_='base-search-card__title')
                    if not title_elem:
                        continue
                    title = title_elem.get_text().strip()
                    if not self.is_relevant_job(title):
                        continue
                    company_elem = card.find('h4', class_='base-search-card__subtitle')
                    location_elem = card.find('span', class_='job-search-card__location')
                    job_url = card.find('a', class_='base-card__full-link')['href']
                    jobs.append({
                        'title': title,
                        'company': company_elem.get_text().strip() if company_elem else 'Not Listed',
                        'location': location_elem.get_text().strip() if location_elem else 'Unspecified',
                        'salary': 'Not listed',
                        'source': 'LinkedIn',
                        'url': job_url,
                        'priority': self.is_priority_job(title),
                        'scraped_date': datetime.now().strftime('%Y-%m-%d')
                    })
                except Exception:
                    continue
            time.sleep(random.uniform(2, 4))
        except Exception as e:
            print(f"Error scraping LinkedIn: {e}")
        return jobs

    def scrape_google_alerts(self, feed_url=None):
        jobs = []
        if not feed_url:
            feed_url = os.environ.get('GOOGLE_ALERT_FEED')
        if not feed_url:
            print("❌ No Google Alerts feed URL set.")
            return jobs
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                title = entry.title
                link = entry.link
                if not self.is_relevant_job(title):
                    continue
                jobs.append({
                    'title': title,
                    'company': 'From Google Alert',
                    'location': 'Unspecified',
                    'salary': 'Not listed',
                    'source': 'Google Alerts',
                    'url': link,
                    'priority': self.is_priority_job(title),
                    'scraped_date': datetime.now().strftime('%Y-%m-%d')
                })
        except Exception as e:
            print(f"Error parsing Google Alert feed: {e}")
        return jobs

    def scrape_twine(self):
        jobs = []
        try:
            url = "https://www.twine.net/jobs/cinematographers/in/france"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            job_cards = soup.find_all('div', class_='job-card')
            for card in job_cards[:5]:
                try:
                    title_elem = card.find('h3', class_='job-title')
                    if not title_elem:
                        continue
                    title = title_elem.get_text().strip()
                    if not self.is_relevant_job(title):
                        continue
                    company_elem = card.find('p', class_='company-name')
                    location_elem = card.find('p', class_='location')
                    job_url = card.find('a', class_='job-link')['href']
                    jobs.append({
                        'title': title,
                        'company': company_elem.get_text().strip() if company_elem else 'Not Listed',
                        'location': location_elem.get_text().strip() if location_elem else 'Unspecified',
                        'salary': 'Not listed',
                        'source': 'Twine',
                        'url': job_url,
                        'priority': self.is_priority_job(title),
                        'scraped_date': datetime.now().strftime('%Y-%m-%d')
                    })
                except Exception:
                    continue
            time.sleep(random.uniform(2, 4))
        except Exception as e:
            print(f"Error scraping Twine: {e}")
        return jobs

    def is_relevant_job(self, title):
        return any(k in title.lower() for k in self.keywords)

    def is_priority_job(self, title):
        return any(k in title.lower() for k in ['tv', 'film', 'feature', 'netflix', 'drama'])

    def is_target_location(self, location):
        return any(loc in location.lower() for loc in [
            'uk', 'united kingdom', 'france', 'germany', 'usa', 'canada',
            'london', 'berlin', 'paris', 'new york', 'los angeles', 'toronto'
        ])

    def remove_duplicates(self, jobs):
        seen = set()
        unique = []
        for job in jobs:
            id = f"{job['title'].lower()}-{job['company'].lower()}"
            id = re.sub(r'[^a-z0-9-]', '', id)
            if id not in seen:
                seen.add(id)
                unique.append(job)
        return unique

    def scrape_all(self):
        all_jobs = []
        all_jobs.extend(self.scrape_indeed())
        all_jobs.extend(self.scrape_linkedin_jobs())
        all_jobs.extend(self.scrape_google_alerts())
        all_jobs.extend(self.scrape_twine())
        all_jobs = [job for job in all_jobs if self.is_target_location(job['location'])]
        all_jobs = self.remove_duplicates(all_jobs)
        return sorted(all_jobs, key=lambda j: j['priority'], reverse=True)[:15]

def send_email_alert(jobs, recipient_email):
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')

    if not sender_email or not sender_password or not recipient_email:
        print("❌ Email credentials or recipient email not set")
        return

    if not jobs:
        print("⚠️ No jobs found to email.")
        return

    subject = f"🎬 {len(jobs)} New Cinematography Jobs (Daily Digest)"
    html_body = "<h2>Today's Jobs</h2><ul>"
    for job in jobs:
        html_body += f"<li><a href='{job['url']}'>{job['title']}</a> at {job['company']} – {job['location']}</li>"
    html_body += "</ul>"

    msg = MIMEMultipart("alternative")
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            print(f"✅ Email sent to {recipient_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def main():
    print("🎬 Running Cinematographer Job Scraper...")
    scraper = JobScraper()
    jobs = scraper.scrape_all()
    print(f"✅ {len(jobs)} jobs found")
    recipient = os.environ.get('RECIPIENT_EMAIL')
    send_email_alert(jobs, recipient)
    with open('latest_jobs.json', 'w') as f:
        json.dump(jobs, f, indent=2)

if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone=pytz.timezone('Europe/Paris'))
    scheduler.add_job(main, 'cron', hour=7, minute=30)
    scheduler.start()
