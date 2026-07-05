import os
import json
import glob
import pandas as pd
from deltalake import write_deltalake


class DataIngest:

    def ingest(self, source_name: str):
        raw_folder = f"Raw/{source_name}"
        l1_folder = f"L1/{source_name}"

        all_items = []
        for path in sorted(glob.glob(f"{raw_folder}/*.json")):
            with open(path) as f:
                data = json.load(f)
                all_items.extend(data.get("items", []))

        if not all_items:
            return

        flatten_fn = self._get_flattener(source_name)
        if flatten_fn == "comments":
            comments = []
            for item in all_items:
                comments.append(self._flatten_comment(item))
                for reply in item.get("replies", {}).get("comments", []):
                    comments.append(self._flatten_reply(reply, item))
            df = pd.DataFrame(comments)
        else:
            df = pd.DataFrame([flatten_fn(i) for i in all_items])

        write_deltalake(l1_folder, df, mode="overwrite")
        return df

    def _get_flattener(self, source_name):
        mapping = {
            "Search_Results": self._flatten_search_item,
            "Video_Details": self._flatten_video,
            "Channel_Details": self._flatten_channel,
            "Comments": "comments",
        }
        return mapping[source_name]

    def _flatten_search_item(self, item):
        flat = {
            "kind": item.get("kind"),
            "etag": item.get("etag"),
            "video_kind": item.get("id", {}).get("kind"),
            "video_id": item.get("id", {}).get("videoId"),
        }
        snippet = item.get("snippet", {})
        flat["published_at"] = snippet.get("publishedAt")
        flat["channel_id"] = snippet.get("channelId")
        flat["title"] = snippet.get("title")
        flat["description"] = snippet.get("description")
        flat["channel_title"] = snippet.get("channelTitle")
        flat["live_broadcast_content"] = snippet.get("liveBroadcastContent")
        flat["publish_time"] = snippet.get("publishTime")
        for size in ["default", "medium", "high"]:
            thumb = snippet.get("thumbnails", {}).get(size, {})
            flat[f"thumbnail_{size}_url"] = thumb.get("url")
            flat[f"thumbnail_{size}_width"] = thumb.get("width")
            flat[f"thumbnail_{size}_height"] = thumb.get("height")
        return flat

    def _flatten_video(self, item):
        flat = {
            "video_id": item.get("id"),
            "kind": item.get("kind"),
            "etag": item.get("etag"),
        }
        snippet = item.get("snippet", {})
        flat["published_at"] = snippet.get("publishedAt")
        flat["channel_id"] = snippet.get("channelId")
        flat["title"] = snippet.get("title")
        flat["description"] = snippet.get("description")
        flat["category_id"] = snippet.get("categoryId")
        for size in ["default", "medium", "high"]:
            thumb = snippet.get("thumbnails", {}).get(size, {})
            flat[f"thumbnail_{size}_url"] = thumb.get("url")
        details = item.get("contentDetails", {})
        flat["duration"] = details.get("duration")
        flat["aspect_ratio"] = details.get("aspectRatio")
        stats = item.get("statistics", {})
        flat["view_count"] = stats.get("viewCount")
        flat["like_count"] = stats.get("likeCount")
        flat["dislike_count"] = stats.get("dislikeCount")
        flat["favorite_count"] = stats.get("favoriteCount")
        flat["comment_count"] = stats.get("commentCount")
        status = item.get("status", {})
        flat["upload_status"] = status.get("uploadStatus")
        flat["privacy_status"] = status.get("privacyStatus")
        return flat

    def _flatten_channel(self, item):
        flat = {
            "channel_id": item.get("id"),
            "kind": item.get("kind"),
            "etag": item.get("etag"),
        }
        snippet = item.get("snippet", {})
        flat["title"] = snippet.get("title")
        flat["description"] = snippet.get("description")
        flat["custom_url"] = snippet.get("customUrl")
        flat["published_at"] = snippet.get("publishedAt")
        flat["country"] = snippet.get("country")
        for size in ["default", "medium", "high"]:
            thumb = snippet.get("thumbnails", {}).get(size, {})
            flat[f"thumbnail_{size}_url"] = thumb.get("url")
            flat[f"thumbnail_{size}_width"] = thumb.get("width")
            flat[f"thumbnail_{size}_height"] = thumb.get("height")
        details = item.get("contentDetails", {})
        playlists = details.get("relatedPlaylists", {})
        flat["likes_playlist"] = playlists.get("likes")
        flat["uploads_playlist"] = playlists.get("uploads")
        stats = item.get("statistics", {})
        flat["view_count"] = stats.get("viewCount")
        flat["subscriber_count"] = stats.get("subscriberCount")
        flat["hidden_subscriber_count"] = stats.get("hiddenSubscriberCount")
        flat["video_count"] = stats.get("videoCount")
        return flat

    def _flatten_comment(self, item):
        snippet = item.get("snippet", {})
        top = snippet.get("topLevelComment", {})
        top_snip = top.get("snippet", {})
        auth_channel_id = top_snip.get("authorChannelId", {})
        return {
            "thread_id": item.get("id"),
            "kind": item.get("kind"),
            "etag": item.get("etag"),
            "video_id": snippet.get("videoId"),
            "channel_id": snippet.get("channelId"),
            "can_reply": snippet.get("canReply"),
            "total_reply_count": snippet.get("totalReplyCount"),
            "is_public": snippet.get("isPublic"),
            "comment_id": top.get("id"),
            "comment_kind": top.get("kind"),
            "comment_etag": top.get("etag"),
            "text_display": top_snip.get("textDisplay"),
            "text_original": top_snip.get("textOriginal"),
            "author_display_name": top_snip.get("authorDisplayName"),
            "author_profile_image_url": top_snip.get("authorProfileImageUrl"),
            "author_channel_url": top_snip.get("authorChannelUrl"),
            "author_channel_id": auth_channel_id.get("value"),
            "like_count": top_snip.get("likeCount"),
            "published_at": top_snip.get("publishedAt"),
            "updated_at": top_snip.get("updatedAt"),
            "parent_comment_id": None,
        }

    def _flatten_reply(self, reply, parent_item):
        snip = reply.get("snippet", {})
        auth_channel_id = snip.get("authorChannelId", {})
        thread_id = parent_item.get("id")
        video_id = parent_item.get("snippet", {}).get("videoId")
        return {
            "thread_id": thread_id,
            "kind": reply.get("kind"),
            "etag": reply.get("etag"),
            "video_id": video_id,
            "channel_id": snip.get("channelId"),
            "can_reply": None,
            "total_reply_count": None,
            "is_public": None,
            "comment_id": reply.get("id"),
            "comment_kind": reply.get("kind"),
            "comment_etag": reply.get("etag"),
            "text_display": snip.get("textDisplay"),
            "text_original": snip.get("textOriginal"),
            "author_display_name": snip.get("authorDisplayName"),
            "author_profile_image_url": snip.get("authorProfileImageUrl"),
            "author_channel_url": snip.get("authorChannelUrl"),
            "author_channel_id": auth_channel_id.get("value"),
            "like_count": snip.get("likeCount"),
            "published_at": snip.get("publishedAt"),
            "updated_at": snip.get("updatedAt"),
            "parent_comment_id": snip.get("parentId"),
        }
