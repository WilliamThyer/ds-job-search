"""Workable ATS scraper."""

import logging
import requests
from typing import Optional

from models import Job
from utils import is_barcelona_role, is_data_role, is_english_posting, detect_visa_mentions

logger = logging.getLogger(__name__)

WORKABLE_API_BASE = "https://apply.workable.com/api/v3/accounts"


def scrape_workable(company_id: str, workable_subdomain: str) -> list[Job]:
    """
    Scrape jobs from Workable API.

    Args:
        company_id: Internal company identifier
        workable_subdomain: Workable subdomain (from URL like apply.workable.com/{subdomain})

    Returns:
        List of Job objects
    """
    jobs = []
    url = f"{WORKABLE_API_BASE}/{workable_subdomain}/jobs"

    try:
        response = requests.post(url, json={}, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; JobTracker/1.0)',
            'Content-Type': 'application/json',
        })
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch Workable jobs for {company_id}: {e}")
        return jobs

    for job_data in data.get('results', []):
        # Fetch full job details for description
        job = _fetch_and_parse_workable_job(company_id, workable_subdomain, job_data)
        if job and job.is_barcelona and job.is_data_role:
            jobs.append(job)

    logger.info(f"Workable [{company_id}]: Found {len(jobs)} matching jobs")
    return jobs


def _fetch_and_parse_workable_job(company_id: str, subdomain: str, data: dict) -> Optional[Job]:
    """Fetch full details and parse a single Workable job posting."""
    shortcode = data.get('shortcode', '')
    title = data.get('title', '')
    location_data = data.get('location', {})
    if isinstance(location_data, dict):
        location = f"{location_data.get('city', '')}, {location_data.get('country', '')}".strip(', ')
    else:
        location = str(location_data) if location_data else ''
    department = data.get('department', '')
    if isinstance(department, list):
        department = ', '.join(str(d) for d in department)
    url = f"https://apply.workable.com/{subdomain}/j/{shortcode}/"
    published_on = data.get('published_on', '')
    if isinstance(published_on, str) and published_on:
        posted_date = published_on[:10]
    else:
        posted_date = None

    # Fetch full job description
    description = ''
    try:
        detail_url = f"{WORKABLE_API_BASE}/{subdomain}/jobs/{shortcode}"
        response = requests.post(detail_url, json={}, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; JobTracker/1.0)',
            'Content-Type': 'application/json',
        })
        if response.ok:
            detail_data = response.json()
            description = detail_data.get('description', '')
    except requests.RequestException:
        pass  # Continue without full description

    # Filter: must be English
    if not is_english_posting(title, description):
        return None

    is_bcn = is_barcelona_role(location, title, description)
    is_data = is_data_role(title, description)
    mentions_visa, mentions_relocation = detect_visa_mentions(description)

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
