import requests
import json
import os

from dotenv import load_dotenv
from datetime import date
import time

load_dotenv()
app_id = (os.getenv("Adzuna_app_id") or os.getenv("ADZUNA_APP_ID") or "").strip()
app_key = (os.getenv("Adzuna_api") or os.getenv("ADZUNA_API") or "").strip()

if not app_id or not app_key:
    print("[WARN] Adzuna_app_id or Adzuna_api is missing or empty. Skipping daily API fetch.")
    exit(0)

today = str(date.today())
file_path = os.path.join(os.path.dirname(__file__), f"{today}.json")
progress_path = os.path.join(os.path.dirname(__file__), f"progess-{today}.json")


def fetch_with_retry(url, max_retries=5, timeout=10):
    """Try to fetch a URL. On failure, retry with exponential backoff.
    Returns the response if successful, None if all retries fail."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                return response
            elif response.status_code == 429 or 500 <= response.status_code < 600:
                wait_time = 2 ** (attempt + 1)
                print(f'Status {response.status_code}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})')
                time.sleep(wait_time)
            elif 400 <= response.status_code < 500:
                print(f'Client error {response.status_code}, not retryable')
                return None
        except (requests.Timeout, requests.ConnectionError, requests.RequestException) as e:
            wait_time = 2 ** (attempt + 1)
            print(f'{type(e).__name__}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})')
            time.sleep(wait_time)
    print('All retries exhausted')
    return None
    
def load_progress():
    """Load previously saved progress (data + page number) if a crash happened mid-run."""
    if os.path.exists(progress_path):
        with open(progress_path, 'r') as f:
            progress = json.load(f)
        print(f'Resuming from page {progress["next_page"]} ({len(progress["data"])} results already saved)')
        return progress['data'], progress['next_page']
    return [], 1


def save_progress(data, next_page):
    """Save current progress after each page so we can resume on crash."""
    with open(progress_path, 'w') as f:
        json.dump({'data': data, 'next_page': next_page}, f)


if not os.path.exists(file_path):
    # Load any existing progress from a previous crashed run
    data, page_no = load_progress()

    while True:
        endpoint = f'https://api.adzuna.com/v1/api/jobs/in/search/{page_no}?app_id={app_id}&app_key={app_key}&results_per_page=50&max_days_old=1&category=it-jobs&salary_include_unknown=1&full_time=1&permanent=1'

        response = fetch_with_retry(endpoint)
        if response is None:
            if data:
                save_progress(data, page_no)
            print(f'Failed on page {page_no}.')
            break

        try:
            job = response.json()
        except json.JSONDecodeError:
            save_progress(data, page_no)  # explicitly persist before exiting
            print('Invalid JSON response, progress saved. Re-run to resume.')
            break

        if not job.get('results'):
            break

        data.extend(job['results'])
        page_no += 1

        # Save progress after each successful page
        save_progress(data, page_no)
        print(f'Page {page_no - 1} done — {len(data)} total results so far')

        if len(job['results']) < 50:
            break

    # Only write the final file if we got all the data
    if data:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        # Clean up progress file — extraction is complete
        if os.path.exists(progress_path):
            os.remove(progress_path)
        print(f'Done. {len(data)} total jobs saved to output.json')
else:
    print('File already exists')