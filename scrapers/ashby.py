"""Ashby ATS scraper."""

import logging
import requests
from typing import Optional

from models import Job
from utils import is_barcelona_role, is_data_role, is_english_posting, detect_visa_mentions

logger = logging.getLogger(__name__)


def scrape_ashby(company_id: str, ashby_org: str) -> list[Job]:
    """
    Scrape jobs from Ashby API.

    Args:
        company_id: Internal company identifier
        ashby_org: Ashby organization slug (from URL like jobs.ashbyhq.com/{ashby_org})

    Returns:
        List of Job objects
    """
    jobs = []
    url = f"https://api.ashbyhq.com/posting-api/job-board/{ashby_org}"

    try:
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; JobTracker/1.0)'
        })
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch Ashby jobs for {company_id}: {e}")
        return jobs

    for job_data in data.get('jobs', []):
        job = _parse_ashby_job(company_id, ashby_org, job_data)
        if job and job.is_barcelona and job.is_data_role:
            jobs.append(job)

    logger.info(f"Ashby [{company_id}]: Found {len(jobs)} matching jobs")
    return jobs


def _parse_ashby_job(company_id: str, ashby_org: str, data: dict) -> Optional[Job]:
    """Parse a single Ashby job posting."""
    title = data.get('title', '')
    location = data.get('location', '')
    department = data.get('department', '')
    description = data.get('descriptionPlain', '') or data.get('description', '')
    job_id = data.get('id', '')

    # Construct application URL
    url = f"https://jobs.ashbyhq.com/{ashby_org}/{job_id}"

    # Filter: must be English
    if not is_english_posting(title, description):
        return None

    is_bcn = is_barcelona_role(location, title, description)
    is_data = is_data_role(title, description)
    mentions_visa, mentions_relocation = detect_visa_mentions(description)

    # Parse posted date
    posted_date = data.get('publishedAt', '')[:10] if data.get('publishedAt') else None

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
