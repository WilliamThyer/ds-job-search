"""Lever ATS scraper."""

import logging
import requests
from datetime import datetime
from typing import Optional

from models import Job
from utils import is_barcelona_role, is_data_role, is_english_posting, detect_visa_mentions

logger = logging.getLogger(__name__)


def scrape_lever(company_id: str, lever_company: str) -> list[Job]:
    """
    Scrape jobs from Lever API.

    Args:
        company_id: Internal company identifier
        lever_company: Lever company slug (from URL like jobs.lever.co/{lever_company})

    Returns:
        List of Job objects
    """
    jobs = []
    url = f"https://api.lever.co/v0/postings/{lever_company}"

    try:
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; JobTracker/1.0)'
        })
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch Lever jobs for {company_id}: {e}")
        return jobs

    for job_data in data:
        job = _parse_lever_job(company_id, job_data)
        if job and job.is_barcelona and job.is_data_role:
            jobs.append(job)

    logger.info(f"Lever [{company_id}]: Found {len(jobs)} matching jobs")
    return jobs


def _parse_lever_job(company_id: str, data: dict) -> Optional[Job]:
    """Parse a single Lever job posting."""
    title = data.get('text', '')
    categories = data.get('categories', {})
    location = categories.get('location', '')
    department = categories.get('team', '')
    description = data.get('descriptionPlain', '') or data.get('description', '')
    url = data.get('hostedUrl', '')

    # Filter: must be English
    if not is_english_posting(title, description):
        return None

    is_bcn = is_barcelona_role(location, title, description)
    is_data = is_data_role(title, description)
    mentions_visa, mentions_relocation = detect_visa_mentions(description)

    # Parse posted date from timestamp
    created_at = data.get('createdAt')
    posted_date = None
    if created_at:
        posted_date = datetime.fromtimestamp(created_at / 1000).strftime('%Y-%m-%d')

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
