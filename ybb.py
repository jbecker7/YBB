import os
import requests
import datetime
import json
from pytube import YouTube

api_key = "REPLACE_WITH_YOUR_GOOGLE_CLOUD_API_KEY"
channel_id = "REPLACE_WITH_YOUR_CHANNEL_ID"
rented_dir = "Rented"


def ensure_dir_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


def is_dir_empty(directory):
    return not os.listdir(directory)


def get_subscriptions(api_key, channel_id, page_token=""):
    subscriptions_url = "https://www.googleapis.com/youtube/v3/subscriptions"
    params = {
        "part": "snippet",
        "channelId": channel_id,
        "key": api_key,
        "maxResults": 50,
        "pageToken": page_token,
    }
    response = requests.get(subscriptions_url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to retrieve subscriptions: {response.text}")
        return None


def list_all_subscriptions(api_key, channel_id):
    all_subscriptions = []
    next_page_token = ""
    while True:
        subscriptions_data = get_subscriptions(api_key, channel_id, next_page_token)
        if subscriptions_data is None:
            break
        all_subscriptions.extend(subscriptions_data.get("items", []))
        next_page_token = subscriptions_data.get("nextPageToken", "")
        if not next_page_token:
            break
    return all_subscriptions


def get_channel_uploads_playlist_id(api_key, channel_id):
    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {"part": "contentDetails", "id": channel_id, "key": api_key}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        items = data.get("items", [])
        if not items:
            return None
        return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    else:
        print(f"Failed to retrieve channel details: {response.text}")
        return None


def get_latest_video(api_key, uploads_playlist_id):
    url = "https://www.googleapis.com/youtube/v3/playlistItems"
    params = {
        "part": "snippet",
        "playlistId": uploads_playlist_id,
        "maxResults": 1,
        "key": api_key,
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        items = response.json().get("items", [])
        if not items:
            return "No videos found."
        latest_video = items[0]["snippet"]
        return {
            "title": latest_video["title"],
            "videoId": latest_video["resourceId"]["videoId"],
            "publishedAt": latest_video["publishedAt"],
        }
    else:
        return f"Failed to retrieve videos: {response.text}"


def can_check_out(last_checkout_time):
    if not last_checkout_time:
        return True
    return (datetime.datetime.now() - last_checkout_time) >= datetime.timedelta(days=1)


def download_video(video_id, title):
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    youtube = YouTube(video_url)
    stream = youtube.streams.get_highest_resolution()
    print(f"Downloading {title}...")
    ensure_dir_exists(rented_dir)
    filename = f"{title}.mp4".replace("/", "_").replace("\\", "_")
    stream.download(output_path=rented_dir, filename=filename)
    print("Download complete.")


try:
    with open("last_checkout_time.json", "r") as file:
        last_checkout = json.load(file)
        last_checkout_time = datetime.datetime.strptime(
            last_checkout["time"], "%Y-%m-%dT%H:%M:%S"
        )
except (FileNotFoundError, json.JSONDecodeError, KeyError):
    last_checkout_time = None

ensure_dir_exists(rented_dir)

if can_check_out(last_checkout_time) and is_dir_empty(rented_dir):
    subscriptions = list_all_subscriptions(api_key, channel_id)
    user_decision = "n"  # Default to no
    for subscription in subscriptions:
        channel_title = subscription["snippet"]["title"]
        subscribed_channel_id = subscription["snippet"]["resourceId"]["channelId"]
        uploads_playlist_id = get_channel_uploads_playlist_id(
            api_key, subscribed_channel_id
        )
        if uploads_playlist_id:
            latest_video_info = get_latest_video(api_key, uploads_playlist_id)
            try:
                with open(
                    os.path.join(rented_dir, "download_history.txt"), "r"
                ) as file:
                    history = file.read()
            except FileNotFoundError:
                history = ""
            if str(latest_video_info.get("videoId")) in history:
                print(f"You've already watched the latest video from {channel_title}.")
                continue
            if isinstance(latest_video_info, dict):
                print(
                    f"Latest video from {channel_title}: {latest_video_info['title']} (Video ID: {latest_video_info['videoId']})"
                )
                user_decision = input(
                    "Do you want to check out this video? (y/n): "
                ).lower()
                if user_decision == "y":
                    print(
                        f"Enjoy your video: {latest_video_info['title']}. Downloading now..."
                    )
                    download_video(
                        latest_video_info["videoId"], latest_video_info["title"]
                    )
                    with open("last_checkout_time.json", "w") as file:
                        json.dump(
                            {
                                "time": datetime.datetime.now().strftime(
                                    "%Y-%m-%dT%H:%M:%S"
                                )
                            },
                            file,
                        )
                    break
                elif user_decision == "n":
                    continue
                else:
                    print("Invalid input. Exiting.")
                    break
            else:
                print(f"No recent videos found for {channel_title}.")
        else:
            print(
                f"Could not retrieve uploads playlist ID for channel: {channel_title}."
            )
    if user_decision != "y":
        print("No more videos to check out or operation cancelled.")
else:
    print(
        "You cannot check out a video at this time. Please return the current video or wait if the rental period has not yet passed."
    )
