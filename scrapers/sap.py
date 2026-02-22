"""SAP SuccessFactors careers scraper."""

import logging
import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from models import Job
from utils import is_barcelona_role, is_data_role, detect_visa_mentions

logger = logging.getLogger(__name__)

BASE_URL = "https://jobs.sap.com"
SEARCH_URL = f"{BASE_URL}/search/"


def scrape_sap(company_id: str) -> list[Job]:
    """
    Scrape SAP jobs from their careers site.

    Args:
        company_id: Internal company identifier

    Returns:
        List of Job objects matching Barcelona + data role criteria
    """
    all_jobs = []

    # Search for data-related jobs in Barcelona
    search_terms = ["data", "machine learning", "AI", "analyst", "scientist"]

    for term in search_terms:
        try:
            jobs = _search_sap_jobs(term, "barcelona")
            all_jobs.extend(jobs)
        except Exception as e:
            logger.error(f"Error searching SAP for '{term}': {e}")

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

    logger.info(f"SAP [{company_id}]: Found {len(matching_jobs)} matching jobs from {len(unique_jobs)} total")
    return matching_jobs


def _search_sap_jobs(query: str, location: str) -> list[dict]:
    """Search SAP careers for jobs."""
    jobs = []

    params = {
        "q": query,
        "locationsearch": location,
        "locale": "en_US"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    try:
        resp = requests.get(SEARCH_URL, params=params, headers=headers, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"SAP search returned {resp.status_code}")
            return jobs

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find job rows
        job_rows = soup.select("tr.data-row")

        for row in job_rows:
            title_elem = row.select_one("a.jobTitle-link")
            loc_elem = row.select_one("span.jobLocation")
            date_elem = row.select_one("span.jobDate")

            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            href = title_elem.get("href", "")
            location = loc_elem.get_text(strip=True) if loc_elem else ""
            posted = date_elem.get_text(strip=True) if date_elem else ""

            # Build full URL
            if href and not href.startswith("http"):
                href = BASE_URL + href

            jobs.append({
                "title": title,
                "url": href,
                "location": location,
                "posted": posted
            })

    except requests.RequestException as e:
        logger.error(f"Request error searching SAP: {e}")

    return jobs


def _create_job(company_id: str, job_data: dict) -> Optional[Job]:
    """Create a Job object from scraped data."""
    title = job_data.get("title", "")
    url = job_data.get("url", "")
    location = job_data.get("location", "")

    if not title or not url:
        return None

    # Parse posted date (SAP uses formats like "Feb 20, 2026")
    posted_date = _parse_date(job_data.get("posted", ""))

    is_bcn = is_barcelona_role(location, title, "")
    is_data = is_data_role(title, "")
    mentions_visa, mentions_relocation = detect_visa_mentions("")

    return Job(
        company_id=company_id,
        job_title=title,
        job_url=url,
        location=location,
        department="",
        posted_date=posted_date,
        description_full="",
        is_barcelona=is_bcn,
        is_data_role=is_data,
        mentions_visa=mentions_visa,
        mentions_relocation=mentions_relocation,
    )


def _parse_date(date_str: str) -> str:
    """Parse SAP date format to YYYY-MM-DD."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")

    try:
        # Try common formats
        for fmt in ["%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
    except Exception:
        pass

    return datetime.now().strftime("%Y-%m-%d")
