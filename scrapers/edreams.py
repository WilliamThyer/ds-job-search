"""eDreams ODIGEO careers scraper (WordPress Job Manager)."""

import logging
import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from models import Job
from utils import is_barcelona_role, is_data_role, detect_visa_mentions

logger = logging.getLogger(__name__)

BASE_URL = "https://www.edreamsodigeocareers.com"
JOBS_URL = f"{BASE_URL}/jobs/"


def scrape_edreams(company_id: str) -> list[Job]:
    """
    Scrape eDreams ODIGEO jobs from their careers site.

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

        # Fetch jobs page
        resp = requests.get(JOBS_URL, headers=headers, timeout=30)
        if resp.status_code != 200:
            logger.error(f"Failed to load eDreams jobs page: {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find job listings
        job_items = soup.select("li.job_listing")

        for item in job_items:
            job_data = _parse_edreams_job(item)
            if job_data:
                all_jobs.append(job_data)

        # Deduplicate by URL
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job["url"] not in seen_urls:
                seen_urls.add(job["url"])
                unique_jobs.append(job)

        # Convert to Job objects and filter
        matching_jobs = []
        for job_data in unique_jobs:
            job = _create_job(company_id, job_data)
            if job and job.is_barcelona and job.is_data_role:
                matching_jobs.append(job)

        logger.info(f"eDreams [{company_id}]: Found {len(matching_jobs)} matching jobs from {len(unique_jobs)} total")
        return matching_jobs

    except requests.RequestException as e:
        logger.error(f"Request error scraping eDreams: {e}")
        return []
    except Exception as e:
        logger.error(f"Error scraping eDreams: {e}")
        return []


def _parse_edreams_job(item) -> Optional[dict]:
    """Parse a job listing from eDreams HTML."""
    # Get job link and title
    link = item.select_one("a[href*='/job/']")
    if not link:
        return None

    href = link.get("href", "")
    title = link.get_text(strip=True)

    # Get location if available
    location_elem = item.select_one(".location, [class*='location']")
    location = location_elem.get_text(strip=True) if location_elem else "Barcelona, Spain"

    # Get department/category if available
    category_elem = item.select_one(".job-type, [class*='category']")
    department = category_elem.get_text(strip=True) if category_elem else ""

    if not title or len(title) < 3:
        return None

    return {
        "title": title,
        "url": href,
        "location": location,
        "department": department,
    }


def _create_job(company_id: str, job_data: dict) -> Optional[Job]:
    """Create a Job object from scraped data."""
    title = job_data.get("title", "")
    url = job_data.get("url", "")
    location = job_data.get("location", "Barcelona, Spain")
    department = job_data.get("department", "")

    if not title or not url:
        return None

    # eDreams is headquartered in Barcelona
    is_bcn = is_barcelona_role(location, title, "")
    is_data = is_data_role(title, department)
    mentions_visa, mentions_relocation = detect_visa_mentions("")

    return Job(
        company_id=company_id,
        job_title=title,
        job_url=url,
        location=location,
        department=department,
        posted_date=datetime.now().strftime("%Y-%m-%d"),
        description_full="",
        is_barcelona=is_bcn,
        is_data_role=is_data,
        mentions_visa=mentions_visa,
        mentions_relocation=mentions_relocation,
    )
