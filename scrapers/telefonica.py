"""Telefónica Jobs scraper (SuccessFactors/job2web)."""

import logging
import re
import requests
from bs4 import BeautifulSoup
from typing import Optional

from models import Job
from utils import is_barcelona_role, is_data_role, is_english_posting, detect_visa_mentions

logger = logging.getLogger(__name__)

TELEFONICA_BASE = "https://jobs.telefonica.com"
TELEFONICA_SEARCH = f"{TELEFONICA_BASE}/search/"


def scrape_telefonica(company_id: str, location: str = "barcelona") -> list[Job]:
    """
    Scrape jobs from Telefónica careers (SuccessFactors).

    Args:
        company_id: Internal company identifier
        location: Location to search for (default: barcelona)

    Returns:
        List of Job objects
    """
    jobs = []

    params = {
        "searchby": "location",
        "createNewAlert": "false",
        "q": "",
        "locationsearch": location,
    }

    try:
        response = requests.get(
            TELEFONICA_SEARCH,
            params=params,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (compatible; JobTracker/1.0)"},
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch Telefónica jobs for {company_id}: {e}")
        return jobs

    soup = BeautifulSoup(response.text, "html.parser")

    # Find job listings - they're typically in a results container
    job_elements = soup.select("tr.data-row") or soup.select(".job-row") or soup.select("[data-job-id]")

    # Alternative: look for links that match job URL pattern
    if not job_elements:
        job_links = soup.find_all("a", href=re.compile(r"/job/.*?/\d+/"))
        for link in job_links:
            job = _parse_telefonica_job_from_link(company_id, link, soup)
            if job and job.is_barcelona and job.is_data_role:
                jobs.append(job)
    else:
        for elem in job_elements:
            job = _parse_telefonica_job_element(company_id, elem)
            if job and job.is_barcelona and job.is_data_role:
                jobs.append(job)

    # Deduplicate by URL
    seen_urls = set()
    unique_jobs = []
    for job in jobs:
        if job.job_url not in seen_urls:
            seen_urls.add(job.job_url)
            unique_jobs.append(job)

    logger.info(f"Telefónica [{company_id}]: Found {len(unique_jobs)} matching jobs")
    return unique_jobs


def _parse_telefonica_job_from_link(company_id: str, link_elem, soup: BeautifulSoup) -> Optional[Job]:
    """Parse a job from a link element."""
    href = link_elem.get("href", "")
    if not href:
        return None

    url = href if href.startswith("http") else f"{TELEFONICA_BASE}{href}"
    title = link_elem.get_text(strip=True)

    if not title:
        return None

    # Try to find location near the link
    parent = link_elem.find_parent("tr") or link_elem.find_parent("div", class_=re.compile(r"job|result|row"))
    location = ""
    posted_date = None

    if parent:
        # Look for location text
        loc_elem = parent.find(class_=re.compile(r"location|city")) or parent.find("span", class_="job-location")
        if loc_elem:
            location = loc_elem.get_text(strip=True)

        # Look for date
        date_elem = parent.find(class_=re.compile(r"date|posted"))
        if date_elem:
            date_text = date_elem.get_text(strip=True)
            posted_date = _parse_date(date_text)

    # If no location found, try to extract from URL or default to Barcelona
    if not location:
        if "barcelona" in url.lower():
            location = "Barcelona, ES"
        else:
            location = "Spain"

    # Fetch job details page for description
    description = _fetch_job_description(url)

    # Filter: check if English (or Spanish for Telefonica)
    is_bcn = is_barcelona_role(location, title, description)
    is_data = is_data_role(title, description)
    mentions_visa, mentions_relocation = detect_visa_mentions(description)

    return Job(
        company_id=company_id,
        job_title=title,
        job_url=url,
        location=location,
        department="",
        posted_date=posted_date,
        description_full=description,
        is_barcelona=is_bcn,
        is_data_role=is_data,
        mentions_visa=mentions_visa,
        mentions_relocation=mentions_relocation,
    )


def _parse_telefonica_job_element(company_id: str, elem) -> Optional[Job]:
    """Parse a job from a table row or div element."""
    # Find the job link
    link = elem.find("a", href=re.compile(r"/job/"))
    if not link:
        return None

    href = link.get("href", "")
    url = href if href.startswith("http") else f"{TELEFONICA_BASE}{href}"
    title = link.get_text(strip=True)

    # Find location
    location = ""
    loc_elem = elem.find(class_=re.compile(r"location|city"))
    if loc_elem:
        location = loc_elem.get_text(strip=True)

    # Find date
    posted_date = None
    date_elem = elem.find(class_=re.compile(r"date|posted"))
    if date_elem:
        date_text = date_elem.get_text(strip=True)
        posted_date = _parse_date(date_text)

    description = _fetch_job_description(url)

    is_bcn = is_barcelona_role(location, title, description)
    is_data = is_data_role(title, description)
    mentions_visa, mentions_relocation = detect_visa_mentions(description)

    return Job(
        company_id=company_id,
        job_title=title,
        job_url=url,
        location=location,
        department="",
        posted_date=posted_date,
        description_full=description,
        is_barcelona=is_bcn,
        is_data_role=is_data,
        mentions_visa=mentions_visa,
        mentions_relocation=mentions_relocation,
    )


def _fetch_job_description(url: str) -> str:
    """Fetch the full job description from a job detail page."""
    try:
        response = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; JobTracker/1.0)"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Look for job description container
        desc_elem = (
            soup.find(class_=re.compile(r"job-description|jobDescription|description"))
            or soup.find("div", {"id": re.compile(r"description|job-details")})
            or soup.find("article")
        )

        if desc_elem:
            return desc_elem.get_text(separator="\n", strip=True)
        return ""
    except Exception:
        return ""


def _parse_date(date_text: str) -> Optional[str]:
    """Parse date from various formats to YYYY-MM-DD."""
    if not date_text:
        return None

    # Common formats: "26 Nov 2025", "15 Jan 2026", "January 15, 2026"
    from datetime import datetime

    formats = [
        "%d %b %Y",      # 26 Nov 2025
        "%d %B %Y",      # 26 November 2025
        "%B %d, %Y",     # November 26, 2025
        "%Y-%m-%d",      # 2025-11-26
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_text.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None
