#!/bin/bash
# Daily job scraper runner for cron
# Add to crontab with: crontab -e
# 0 9 * * * /Users/thyer/Documents/job-search/barcelona-ds-tracker/run_daily.sh >> /Users/thyer/Documents/job-search/barcelona-ds-tracker/data/cron.log 2>&1

cd /Users/thyer/Documents/job-search/barcelona-ds-tracker
source venv/bin/activate
python scraper.py
python generate_report.py
