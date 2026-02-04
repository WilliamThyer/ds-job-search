"""SmartRecruiters ATS scraper."""

import logging
import requests
from typing import Optional

from models import Job
from utils import is_barcelona_role, is_data_role, is_english_posting, detect_visa_mentions

logger = logging.getLogger(__name__)

SMARTRECRUITERS_API = "https://api.smartrecruiters.com/v1/companies"


def scrape_smartrecruiters(company_id: str, sr_company: str) -> list[Job]:
    """
    Scrape jobs from SmartRecruiters API.

    Args:
        company_id: Internal company identifier
        sr_company: SmartRecruiters company identifier

    Returns:
        List of Job objects
    """
    jobs = []
    url = f"{SMARTRECRUITERS_API}/{sr_company}/postings"

    try:
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; JobTracker/1.0)'
        })
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch SmartRecruiters jobs for {company_id}: {e}")
        return jobs

    for job_data in data.get('content', []):
        job = _parse_smartrecruiters_job(company_id, sr_company, job_data)
        if job and job.is_barcelona and job.is_data_role:
            jobs.append(job)

    logger.info(f"SmartRecruiters [{company_id}]: Found {len(jobs)} matching jobs")
    return jobs


def _parse_smartrecruiters_job(company_id: str, sr_company: str, data: dict) -> Optional[Job]:
    """Parse a single SmartRecruiters job posting."""
    title = data.get('name', '')

    # Build location string
    location_data = data.get('location', {})
    city = location_data.get('city', '')
    country = location_data.get('country', '')
    location = f"{city}, {country}".strip(', ')

    department = data.get('department', {}).get('label', '')
    job_id = data.get('id', '')
    ref_number = data.get('refNumber', '')

    # Construct application URL
    url = f"https://jobs.smartrecruiters.com/{sr_company}/{job_id}"

    # Fetch full job description
    description = ''
    try:
        detail_url = f"{SMARTRECRUITERS_API}/{sr_company}/postings/{job_id}"
        response = requests.get(detail_url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; JobTracker/1.0)'
        })
        if response.ok:
            detail_data = response.json()
            # SmartRecruiters returns HTML in jobAd.sections
            sections = detail_data.get('jobAd', {}).get('sections', {})
            description_parts = []
            for section_name in ['jobDescription', 'qualifications', 'additionalInformation']:
                section = sections.get(section_name, {})
                if section.get('text'):
                    description_parts.append(section['text'])
            description = ' '.join(description_parts)
    except requests.RequestException:
        pass  # Continue without full description

    # Filter: must be English
    if not is_english_posting(title, description):
        return None

    is_bcn = is_barcelona_role(location, title, description)
    is_data = is_data_role(title, description)
    mentions_visa, mentions_relocation = detect_visa_mentions(description)

    # Parse posted date
    posted_date = data.get('releasedDate', '')[:10] if data.get('releasedDate') else None

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
