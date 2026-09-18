import os
import requests

url = 'https://media.githubusercontent.com/media/StackExchange/Survey/refs/heads/main/packages/archive/2025/results.csv'
output_path = os.path.join(os.path.dirname(__file__), 'survey_result.csv')

print(f"Downloading SO Survey CSV to {output_path}...")
try:
    response = requests.get(url, timeout=120, stream=True)
    response.raise_for_status()
except requests.RequestException as e:
    print(f"[ERROR] Failed to download SO Survey: {e}")
    raise SystemExit(1)

with open(output_path, 'wb') as result_file:
    for chunk in response.iter_content(chunk_size=8192):
        result_file.write(chunk)

size_mb = os.path.getsize(output_path) / (1024 * 1024)
print(f"Done. {size_mb:.1f} MB written to {output_path}")
