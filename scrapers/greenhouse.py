"""Greenhouse ATS scraper."""

import logging
import requests
from typing import Optional

from models import Job
from utils import is_barcelona_role, is_data_role, is_english_posting, detect_visa_mentions

logger = logging.getLogger(__name__)

GREENHOUSE_API_BASE = "https://boards-api.greenhouse.io/v1/boards"


def scrape_greenhouse(company_id: str, board_token: str) -> list[Job]:
    """
    Scrape jobs from Greenhouse API.

    Args:
        company_id: Internal company identifier
        board_token: Greenhouse board token (from URL like boards.greenhouse.io/{board_token})

    Returns:
        List of Job objects
    """
    jobs = []
    url = f"{GREENHOUSE_API_BASE}/{board_token}/jobs?content=true"

    try:
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; JobTracker/1.0)'
        })
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch Greenhouse jobs for {company_id}: {e}")
        return jobs

    for job_data in data.get('jobs', []):
        job = _parse_greenhouse_job(company_id, job_data)
        if job and job.is_barcelona and job.is_data_role:
            jobs.append(job)

    logger.info(f"Greenhouse [{company_id}]: Found {len(jobs)} matching jobs")
    return jobs


def _parse_greenhouse_job(company_id: str, data: dict) -> Optional[Job]:
    """Parse a single Greenhouse job posting."""
    title = data.get('title', '')
    location = data.get('location', {}).get('name', '')
    description = data.get('content', '')
    url = data.get('absolute_url', '')
    department = ''
    departments = data.get('departments', [])
    if departments:
        department = departments[0].get('name', '')

    # Filter: must be English
    if not is_english_posting(title, description):
        return None

    is_bcn = is_barcelona_role(location, title, description)
    is_data = is_data_role(title, description)
    mentions_visa, mentions_relocation = detect_visa_mentions(description)

    # Parse posted date
    posted_date = data.get('updated_at', '')[:10] if data.get('updated_at') else None

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
