import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Get token from .env or environment
token = os.getenv("GitHub_access_token") or os.getenv("GITHUB_ACCESS_TOKEN")

headers = {"Authorization": f"token {token}"}

endpoint = "https://api.github.com/repos/github/explore/contents/topics"
output_file = os.path.join(os.path.dirname(__file__), "topics_with_aliases.txt")

try:
    response = requests.get(endpoint, headers=headers, timeout=15)
    response.raise_for_status()
    topics = response.json()
except Exception as e:
    print("Failed to fetch topics:", e)
    topics = []

final_list = []

if isinstance(topics, list):
    for topic in topics:
        if isinstance(topic, dict) and topic.get("type") == "dir":
            topic_name = topic["name"]
            index_url = f"https://raw.githubusercontent.com/github/explore/main/topics/{topic_name}/index.md"
            try:
                md_resp = requests.get(index_url, timeout=15)
                if md_resp.status_code == 200:
                    content = md_resp.text.splitlines()
                    # Add topic name
                    final_list.append(topic_name)
                    # Look for aliases line
                    for line in content:
                        if line.startswith("aliases:"):
                            aliases = line.replace("aliases:", "").strip()
                            for alias in aliases.split(","):
                                if alias.strip():
                                    final_list.append(alias.strip())
            except requests.exceptions.RequestException as e:
                print(f"Skipping {topic_name} due to error: {e}")

# Save as comma-separated list
with open(output_file, "w", encoding="utf-8") as f:
    f.write(", ".join(final_list))

print(f"Saved topics with aliases to {output_file}")
