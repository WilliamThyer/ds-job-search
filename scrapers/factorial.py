"""Factorial ATS scraper."""

import logging
import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from models import Job
from utils import is_barcelona_role, is_data_role, detect_visa_mentions

logger = logging.getLogger(__name__)

# Factorial company configurations
# Format: company_id -> careers_url
FACTORIAL_COMPANIES = {
    "holaluz": "https://holaluz-1.factorial.es/",
}


def scrape_factorial(company_id: str) -> list[Job]:
    """
    Scrape jobs from a Factorial careers page.

    Args:
        company_id: Internal company identifier

    Returns:
        List of Job objects matching Barcelona + data role criteria
    """
    if company_id not in FACTORIAL_COMPANIES:
        logger.warning(f"No Factorial config for {company_id}")
        return []

    careers_url = FACTORIAL_COMPANIES[company_id]

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

        resp = requests.get(careers_url, headers=headers, timeout=30)
        if resp.status_code != 200:
            logger.error(f"Failed to load Factorial page for {company_id}: {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find job listings
        job_items = soup.select("li.job-offer-item")

        all_jobs = []
        for item in job_items:
            job_data = _parse_factorial_job(item)
            if job_data:
                all_jobs.append(job_data)

        # Convert to Job objects and filter
        matching_jobs = []
        for job_data in all_jobs:
            job = _create_job(company_id, job_data)
            if job and job.is_barcelona and job.is_data_role:
                matching_jobs.append(job)

        logger.info(f"Factorial [{company_id}]: Found {len(matching_jobs)} matching jobs from {len(all_jobs)} total")
        return matching_jobs

    except requests.RequestException as e:
        logger.error(f"Request error scraping Factorial {company_id}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error scraping Factorial {company_id}: {e}")
        return []


def _parse_factorial_job(item) -> Optional[dict]:
    """Parse a job item from Factorial HTML."""
    # Get job link
    link = item.select_one('a[href*="/job_posting/"]')
    if not link:
        return None

    href = link.get("href", "")

    # Get title (bold text)
    title_elem = item.select_one("div.font-bold")
    title = title_elem.get_text(strip=True) if title_elem else ""

    # Get department and work type (gray text divs)
    gray_divs = item.select("div.text-gray-350")
    department = gray_divs[0].get_text(strip=True) if len(gray_divs) > 0 else ""
    work_type = gray_divs[1].get_text(strip=True) if len(gray_divs) > 1 else ""

    if not title:
        return None

    return {
        "title": title,
        "url": href,
        "department": department,
        "work_type": work_type,
    }


def _create_job(company_id: str, job_data: dict) -> Optional[Job]:
    """Create a Job object from scraped data."""
    title = job_data.get("title", "")
    url = job_data.get("url", "")
    department = job_data.get("department", "")
    work_type = job_data.get("work_type", "")

    if not title or not url:
        return None

    # Holaluz is based in Barcelona, so all jobs are likely Barcelona
    # But check title for location hints
    location = "Barcelona, Spain"
    if "alicante" in title.lower():
        location = "Alicante, Spain"
    elif "madrid" in title.lower():
        location = "Madrid, Spain"
    elif "valencia" in title.lower():
        location = "Valencia, Spain"

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


def scrape_holaluz(company_id: str) -> list[Job]:
    """Convenience function for Holaluz."""
    return scrape_factorial("holaluz")
