"""Barcelona Supercomputing Center careers scraper."""

import logging
import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from models import Job
from utils import is_barcelona_role, is_data_role, detect_visa_mentions

logger = logging.getLogger(__name__)

BASE_URL = "https://www.bsc.es"
JOBS_URL = f"{BASE_URL}/join-us/job-opportunities"


def scrape_bsc(company_id: str) -> list[Job]:
    """
    Scrape BSC jobs from their careers page.

    Args:
        company_id: Internal company identifier

    Returns:
        List of Job objects matching Barcelona + data role criteria
    """
    all_jobs = []

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

        resp = requests.get(JOBS_URL, headers=headers, timeout=30)
        if resp.status_code != 200:
            logger.error(f"Failed to load BSC jobs: {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find job links
        links = soup.select('a[href*="/job-opportunities/"]')

        seen_urls = set()
        for link in links:
            href = link.get("href", "")
            if not href or "/job-opportunities/" not in href:
                continue

            # Skip the main page link
            if href == JOBS_URL or href == "/join-us/job-opportunities":
                continue

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                continue

            # Build full URL
            full_url = href if href.startswith("http") else BASE_URL + href

            all_jobs.append({
                "title": title,
                "url": full_url,
                "location": "Barcelona, Spain",
            })

        # Convert to Job objects and filter
        matching_jobs = []
        for job_data in all_jobs:
            job = _create_job(company_id, job_data)
            if job and job.is_barcelona and job.is_data_role:
                matching_jobs.append(job)

        logger.info(f"BSC [{company_id}]: Found {len(matching_jobs)} matching jobs from {len(all_jobs)} total")
        return matching_jobs

    except requests.RequestException as e:
        logger.error(f"Request error scraping BSC: {e}")
        return []
    except Exception as e:
        logger.error(f"Error scraping BSC: {e}")
        return []


def _create_job(company_id: str, job_data: dict) -> Optional[Job]:
    """Create a Job object from scraped data."""
    title = job_data.get("title", "")
    url = job_data.get("url", "")
    location = job_data.get("location", "Barcelona, Spain")

    if not title or not url:
        return None

    is_bcn = is_barcelona_role(location, title, "")
    is_data = is_data_role(title, "")
    mentions_visa, mentions_relocation = detect_visa_mentions("")

    return Job(
        company_id=company_id,
        job_title=title,
        job_url=url,
        location=location,
        department="",
        posted_date=datetime.now().strftime("%Y-%m-%d"),
        description_full="",
        is_barcelona=is_bcn,
        is_data_role=is_data,
        mentions_visa=mentions_visa,
        mentions_relocation=mentions_relocation,
    )
