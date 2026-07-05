import os
import json
import logging
import shutil
import requests
from dotenv import load_dotenv
from tqdm import tqdm


class APIClient:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3/"
        os.makedirs("logs", exist_ok=True)

    def _setup_logger(self, name):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        handler = logging.FileHandler(f"logs/{name}.log", mode="w")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
        return logger

    def fetch_search(self, num_pages: int = 1):
        log = self._setup_logger("search")
        folder = "Raw/Search_Results"
        shutil.rmtree(folder, ignore_errors=True)
        os.makedirs(folder, exist_ok=True)
        page_token = None

        for page in tqdm(range(num_pages), desc="Search pages"):
            params = {
                "part": "snippet",
                "q": "iPhone 17",
                "type": "video",
                "maxResults": 50,
                "key": self.api_key,
            }
            if page_token:
                params["pageToken"] = page_token

            try:
                resp = requests.get(self.base_url + "search", params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.RequestException as e:
                log.error("Search page %d failed: %s", page, e)
                if hasattr(e, "response") and e.response is not None:
                    log.error("  status=%d body=%s", e.response.status_code, e.response.text[:500])
                raise

            with open(f"{folder}/page_{page}.json", "w") as f:
                json.dump(data, f)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

    def _read_ids(self, raw_folder, id_field):
        import glob
        ids = set()
        for path in glob.glob(f"Raw/{raw_folder}/*.json"):
            with open(path) as f:
                data = json.load(f)
                for item in data.get("items", []):
                    raw_id = item.get("id")
                    if id_field == "video_id":
                        val = raw_id.get("videoId") if isinstance(raw_id, dict) else raw_id
                    elif id_field == "channel_id":
                        val = item.get("snippet", {}).get("channelId")
                    else:
                        val = item.get(id_field)
                    if val:
                        ids.add(val)
        return list(ids)

    def get_videos(self):
        log = self._setup_logger("videos")
        video_ids = set(self._read_ids("Search_Results", "video_id"))
        folder = "Raw/Video_Details"
        shutil.rmtree(folder, ignore_errors=True)
        os.makedirs(folder, exist_ok=True)
        returned = set()
        ids_list = list(video_ids)
        for i in tqdm(range(0, len(ids_list), 50), desc="Video batches", unit="batch"):
            batch = ids_list[i:i + 50]
            params = {
                "id": ",".join(batch),
                "part": "snippet,contentDetails,statistics,status",
                "key": self.api_key,
            }
            try:
                resp = requests.get(self.base_url + "videos", params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.RequestException as e:
                log.error("Videos batch %d failed: %s", i // 50, e)
                if hasattr(e, "response") and e.response is not None:
                    log.error("  status=%d body=%s", e.response.status_code, e.response.text[:500])
                raise
            for item in data.get("items", []):
                vid = item.get("id")
                if vid:
                    returned.add(vid)
            with open(f"{folder}/batch_{i // 50}.json", "w") as f:
                json.dump(data, f)

        missing = video_ids - returned
        if missing:
            log.info("VIDEOS MISSING from API response (%d):", len(missing))
            for vid in sorted(missing):
                log.info("  %s", vid)
        else:
            log.info("All %d video IDs successfully returned.", len(video_ids))

    def get_channels(self):
        log = self._setup_logger("channels")
        channel_ids = set(self._read_ids("Video_Details", "channel_id"))
        folder = "Raw/Channel_Details"
        shutil.rmtree(folder, ignore_errors=True)
        os.makedirs(folder, exist_ok=True)
        returned = set()
        ids_list = list(channel_ids)
        for i in tqdm(range(0, len(ids_list), 50), desc="Channel batches", unit="batch"):
            batch = ids_list[i:i + 50]
            params = {
                "id": ",".join(batch),
                "part": "snippet,contentDetails,statistics",
                "key": self.api_key,
            }
            try:
                resp = requests.get(self.base_url + "channels", params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.RequestException as e:
                log.error("Channels batch %d failed: %s", i // 50, e)
                if hasattr(e, "response") and e.response is not None:
                    log.error("  status=%d body=%s", e.response.status_code, e.response.text[:500])
                raise
            for item in data.get("items", []):
                cid = item.get("id")
                if cid:
                    returned.add(cid)
            with open(f"{folder}/batch_{i // 50}.json", "w") as f:
                json.dump(data, f)

        missing = channel_ids - returned
        if missing:
            log.info("CHANNELS MISSING from API response (%d):", len(missing))
            for cid in sorted(missing):
                log.info("  %s", cid)
        else:
            log.info("All %d channel IDs successfully returned.", len(channel_ids))

    def get_comments(self, max_comments_per_video: int = 100):
        log = self._setup_logger("comments")
        video_ids = self._read_ids("Video_Details", "video_id")
        folder = "Raw/Comments"
        shutil.rmtree(folder, ignore_errors=True)
        os.makedirs(folder, exist_ok=True)
        no_comments = []
        forbidden = []
        with_comments = 0
        for vid in tqdm(video_ids, desc="Comment threads", unit="video"):
            page_token = None
            fetched = 0
            page = 0
            got_items = False
            while fetched < max_comments_per_video:
                params = {
                    "part": "snippet,replies",
                    "videoId": vid,
                    "maxResults": min(100, max_comments_per_video - fetched),
                    "key": self.api_key,
                }
                if page_token:
                    params["pageToken"] = page_token
                try:
                    resp = requests.get(self.base_url + "commentThreads", params=params, timeout=30)
                    if resp.status_code in (403, 404):
                        forbidden.append(vid)
                        break
                    resp.raise_for_status()
                    data = resp.json()
                except requests.exceptions.RequestException as e:
                    log.error("Comments for video %s failed: %s", vid, e)
                    if hasattr(e, "response") and e.response is not None:
                        log.error("  status=%d body=%s", e.response.status_code, e.response.text[:500])
                    forbidden.append(vid)
                    break
                items = data.get("items", [])
                if items:
                    got_items = True
                with open(f"{folder}/{vid}_page_{page}.json", "w") as f:
                    json.dump(data, f)
                fetched += len(items)
                page_token = data.get("nextPageToken")
                page += 1
                if not page_token:
                    break
            if got_items:
                with_comments += 1
            elif vid not in forbidden:
                no_comments.append(vid)

        log.info("Videos with comments: %d | Without comments: %d | Forbidden/Error: %d",
                 with_comments, len(no_comments), len(forbidden))
        if no_comments:
            log.info("Videos with zero comments:")
            for vid in no_comments:
                log.info("  %s", vid)
        if forbidden:
            log.info("Videos with errors (403/404/other):")
            for vid in forbidden:
                log.info("  %s", vid)
