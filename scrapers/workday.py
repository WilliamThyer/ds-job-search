"""Workday ATS scraper for companies using myworkdayjobs.com."""

import logging
import re
from datetime import datetime
from typing import Optional

import requests

from models import Job
from utils import is_barcelona_role, is_data_role, detect_visa_mentions

logger = logging.getLogger(__name__)

# Workday company configurations
# Format: company_id -> (tenant, wd_instance, site_id)
WORKDAY_COMPANIES = {
    "mango": ("mango", "wd3", "Mango_Work_Your_Passion"),
}


def scrape_workday(company_id: str) -> list[Job]:
    """
    Scrape jobs from a Workday careers site.

    Args:
        company_id: Internal company identifier

    Returns:
        List of Job objects matching Barcelona + data role criteria
    """
    if company_id not in WORKDAY_COMPANIES:
        logger.warning(f"No Workday config for {company_id}")
        return []

    tenant, wd_instance, site_id = WORKDAY_COMPANIES[company_id]
    base_url = f"https://{tenant}.{wd_instance}.myworkdayjobs.com"

    try:
        # Create session and get CSRF token
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })

        # Get main page to establish session
        main_url = f"{base_url}/en-US/{site_id}"
        resp = session.get(main_url, timeout=30)
        if resp.status_code != 200:
            logger.error(f"Failed to load Workday main page for {company_id}: {resp.status_code}")
            return []

        csrf_token = session.cookies.get("CALYPSO_CSRF_TOKEN")
        if not csrf_token:
            logger.warning(f"No CSRF token found for {company_id}, trying without")

        # Fetch all jobs with pagination
        all_jobs = []
        offset = 0
        limit = 20  # Workday rejects larger limits
        max_jobs = 500  # Fetch enough to find data roles
        total_jobs = None  # Will be set from first response

        api_url = f"{base_url}/wday/cxs/{tenant}/{site_id}/jobs"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if csrf_token:
            headers["X-CALYPSO-CSRF-TOKEN"] = csrf_token

        while offset < max_jobs:
            body = {
                "appliedFacets": {},
                "limit": limit,
                "offset": offset,
                "searchText": ""
            }

            resp = session.post(api_url, headers=headers, json=body, timeout=30)

            if resp.status_code != 200:
                logger.error(f"Workday API error for {company_id}: {resp.status_code}")
                break

            data = resp.json()
            jobs = data.get("jobPostings", [])

            # Only first response has accurate total
            if total_jobs is None:
                total_jobs = data.get("total", 0)

            if not jobs:
                break

            all_jobs.extend(jobs)
            logger.debug(f"Fetched {len(all_jobs)}/{total_jobs} jobs for {company_id}")

            if len(all_jobs) >= total_jobs:
                break

            offset += limit

        # Filter and convert to Job objects
        matching_jobs = []
        for job_data in all_jobs:
            job = _parse_workday_job(company_id, job_data, base_url, site_id)
            if job and job.is_barcelona and job.is_data_role:
                matching_jobs.append(job)

        logger.info(f"Workday [{company_id}]: Found {len(matching_jobs)} matching jobs from {len(all_jobs)} total")
        return matching_jobs

    except requests.RequestException as e:
        logger.error(f"Request error scraping Workday {company_id}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error scraping Workday {company_id}: {e}")
        return []


def _parse_workday_job(company_id: str, job_data: dict, base_url: str, site_id: str) -> Optional[Job]:
    """Parse a Workday job posting into a Job object."""
    title = job_data.get("title", "")
    external_path = job_data.get("externalPath", "")

    if not title or not external_path:
        return None

    # Build full URL
    job_url = f"{base_url}/en-US/{site_id}{external_path}"

    # Extract location from bulletFields
    bullet_fields = job_data.get("bulletFields", [])
    location = bullet_fields[0] if bullet_fields else "Unknown"

    # Add region/country if available
    if len(bullet_fields) > 1:
        location = f"{bullet_fields[0]}, {bullet_fields[1]}"

    # Time type (Full time, Part time, etc.)
    time_type = job_data.get("timeType", "")

    # Check Barcelona/data role
    is_bcn = is_barcelona_role(location, title, "")
    is_data = is_data_role(title, "")

    # No description available from list endpoint
    mentions_visa, mentions_relocation = False, False

    return Job(
        company_id=company_id,
        job_title=title,
        job_url=job_url,
        location=location,
        department="",
        posted_date=datetime.now().strftime("%Y-%m-%d"),  # Workday doesn't show post date in list
        description_full="",
        is_barcelona=is_bcn,
        is_data_role=is_data,
        mentions_visa=mentions_visa,
        mentions_relocation=mentions_relocation,
    )


def scrape_mango(company_id: str) -> list[Job]:
    """Convenience function for Mango."""
    return scrape_workday("mango")
