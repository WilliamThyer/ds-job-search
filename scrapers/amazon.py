"""Amazon Jobs scraper."""

import logging
import requests
from typing import Optional

from models import Job
from utils import is_barcelona_role, is_data_role, is_english_posting, detect_visa_mentions

logger = logging.getLogger(__name__)

AMAZON_API_BASE = "https://www.amazon.jobs/en/search.json"


def scrape_amazon(company_id: str, location: str = "Barcelona") -> list[Job]:
    """
    Scrape jobs from Amazon Jobs API.

    Args:
        company_id: Internal company identifier
        location: City to search for (default: Barcelona)

    Returns:
        List of Job objects
    """
    jobs = []
    offset = 0
    result_limit = 100

    params = {
        "city": location,
        "country": "ESP",
        "offset": offset,
        "result_limit": result_limit,
        "sort": "recent",
    }

    try:
        response = requests.get(
            AMAZON_API_BASE,
            params=params,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (compatible; JobTracker/1.0)"},
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch Amazon jobs for {company_id}: {e}")
        return jobs

    for job_data in data.get("jobs", []):
        job = _parse_amazon_job(company_id, job_data)
        if job and job.is_barcelona and job.is_data_role:
            jobs.append(job)

    logger.info(f"Amazon [{company_id}]: Found {len(jobs)} matching jobs")
    return jobs


def _parse_amazon_job(company_id: str, data: dict) -> Optional[Job]:
    """Parse a single Amazon job posting."""
    title = data.get("title", "")
    location = data.get("normalized_location") or data.get("location", "")
    city = data.get("city", "")

    # Build description from available fields
    description_parts = [
        data.get("description_short", ""),
        data.get("basic_qualifications", ""),
        data.get("preferred_qualifications", ""),
    ]
    description = "\n\n".join(p for p in description_parts if p)

    # Build URL
    job_path = data.get("job_path", "")
    url = f"https://www.amazon.jobs{job_path}" if job_path else ""

    department = data.get("job_category", "") or data.get("business_category", "")

    # Filter: must be English
    if not is_english_posting(title, description):
        return None

    is_bcn = is_barcelona_role(location, title, description) or "barcelona" in city.lower()
    is_data = is_data_role(title, description)
    mentions_visa, mentions_relocation = detect_visa_mentions(description)

    # Parse posted date (format: "January 13, 2026")
    posted_date = data.get("posted_date", "")
    if posted_date:
        try:
            from datetime import datetime
            dt = datetime.strptime(posted_date, "%B %d, %Y")
            posted_date = dt.strftime("%Y-%m-%d")
        except ValueError:
            posted_date = None

    return Job(
        company_id=company_id,
        job_title=title,
        job_url=url,
        location=location,
        department=department,
        posted_date=posted_date,
        description_full=description,
        is_barcelona=is_bcn,
        is_data_role=is_data,
        mentions_visa=mentions_visa,
        mentions_relocation=mentions_relocation,
    )
