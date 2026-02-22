#!/usr/bin/env python3
"""Main scraping orchestrator - fetches jobs from all configured companies."""

import json
import logging
import sys
import time
from pathlib import Path

from models import init_db, save_job
from scrapers import (
    scrape_greenhouse,
    scrape_lever,
    scrape_workable,
    scrape_ashby,
    scrape_smartrecruiters,
    scrape_amazon,
    scrape_telefonica,
    scrape_microsoft_email,
    scrape_hp_email,
    scrape_revolut_email,
    scrape_workday,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / 'data' / 'scraper.log'),
    ]
)
logger = logging.getLogger(__name__)

COMPANIES_FILE = Path(__file__).parent / "data" / "companies.json"
RATE_LIMIT_DELAY = 2  # seconds between companies


def load_companies() -> list[dict]:
    """Load company list from JSON file."""
    if not COMPANIES_FILE.exists():
        logger.error(f"Companies file not found: {COMPANIES_FILE}")
        return []

    with open(COMPANIES_FILE) as f:
        data = json.load(f)

    return data.get('companies', [])


def scrape_company(company: dict) -> int:
    """
    Scrape jobs for a single company.
    Returns count of new jobs saved.
    """
    company_id = company['id']
    ats_platform = company.get('ats_platform', 'custom')
    ats_id = company.get('ats_id', '')

    # Manual platforms - skip silently
    if ats_platform == 'manual':
        return 0

    # Custom scrapers that don't need ats_id
    if ats_platform == 'amazon':
        jobs = scrape_amazon(company_id)
    elif ats_platform == 'telefonica':
        jobs = scrape_telefonica(company_id)
    elif ats_platform == 'microsoft_email':
        jobs = scrape_microsoft_email(company_id)
    elif ats_platform == 'hp_email':
        jobs = scrape_hp_email(company_id)
    elif ats_platform == 'revolut_email':
        jobs = scrape_revolut_email(company_id)
    elif ats_platform == 'workday':
        jobs = scrape_workday(company_id)
    elif not ats_id:
        logger.warning(f"No ATS ID configured for {company_id}, skipping")
        return 0
    elif ats_platform == 'greenhouse':
        jobs = scrape_greenhouse(company_id, ats_id)
    elif ats_platform == 'lever':
        jobs = scrape_lever(company_id, ats_id)
    elif ats_platform == 'workable':
        jobs = scrape_workable(company_id, ats_id)
    elif ats_platform == 'ashby':
        jobs = scrape_ashby(company_id, ats_id)
    elif ats_platform == 'smartrecruiters':
        jobs = scrape_smartrecruiters(company_id, ats_id)
    else:
        logger.warning(f"Unsupported ATS platform '{ats_platform}' for {company_id}")
        return 0

    # Save jobs to database
    new_count = 0
    for job in jobs:
        if save_job(job):
            new_count += 1
            logger.info(f"New job: {job.job_title} at {company_id}")

    return new_count


def main():
    """Main entry point."""
    logger.info("=" * 50)
    logger.info("Starting job scraper run")

    # Initialize database
    init_db()

    # Load companies
    companies = load_companies()
    if not companies:
        logger.error("No companies to scrape")
        sys.exit(1)

    logger.info(f"Loaded {len(companies)} companies")

    # Scrape each company
    total_new = 0
    failed = 0

    for i, company in enumerate(companies):
        try:
            new_count = scrape_company(company)
            total_new += new_count
        except Exception as e:
            logger.error(f"Failed to scrape {company['id']}: {e}")
            failed += 1

        # Rate limiting (except for last company)
        if i < len(companies) - 1:
            time.sleep(RATE_LIMIT_DELAY)

    # Summary
    logger.info("-" * 50)
    logger.info(f"Scraping complete: {total_new} new jobs found")
    logger.info(f"Companies scraped: {len(companies) - failed}/{len(companies)}")

    if failed > len(companies) * 0.2:
        logger.warning(f"High failure rate: {failed}/{len(companies)} companies failed")

    logger.info("=" * 50)


if __name__ == "__main__":
    main()
