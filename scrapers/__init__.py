"""Job scrapers for various ATS platforms."""

from .greenhouse import scrape_greenhouse
from .lever import scrape_lever
from .workable import scrape_workable
from .ashby import scrape_ashby
from .smartrecruiters import scrape_smartrecruiters
from .amazon import scrape_amazon
from .telefonica import scrape_telefonica
from .microsoft_email import scrape_microsoft_email
from .email_alerts import scrape_hp_email, scrape_revolut_email

__all__ = [
    'scrape_greenhouse',
    'scrape_lever',
    'scrape_workable',
    'scrape_ashby',
    'scrape_smartrecruiters',
    'scrape_amazon',
    'scrape_telefonica',
    'scrape_microsoft_email',
    'scrape_hp_email',
    'scrape_revolut_email',
]
