import os
import logging
import pandas as pd
from deltalake import write_deltalake, DeltaTable


class DataCleaner:

    def __init__(self):
        os.makedirs("logs", exist_ok=True)
        self._dropped_videos_log = self._setup_logger("dropped_videos")
        self._dropped_comments_log = self._setup_logger("dropped_comments")

    def _setup_logger(self, name):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        handler = logging.FileHandler(f"logs/{name}.log", mode="w")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
        return logger

    def clean_videos(self, columns_to_drop=None):
        if columns_to_drop is None:
            columns_to_drop = ["kind", "live_broadcast_content" , "etag", "thumbnail_default_url","thumbnail_medium_url", "thumbnail_high_url",  "upload_status" ,"favorite_count", "duration", "aspect_ratio"]

        videos = DeltaTable("L1/Video_Details").to_pandas()
        channels = DeltaTable("L1/Channel_Details").to_pandas()
        comments = DeltaTable("L1/Comments").to_pandas()

        videos = videos.drop(columns=[c for c in columns_to_drop if c in videos.columns])

        channels_subset = channels[["channel_id", "title"]].rename(columns={"title": "channel"})
        videos = videos.merge(channels_subset, on="channel_id", how="left")

        comment_counts = comments.groupby("video_id").size().reset_index(name="fetched_comments_count")
        videos = videos.merge(comment_counts, on="video_id", how="left")

        self._dropped_video_ids = set()

        dup_mask = videos["video_id"].duplicated(keep="first")
        dup_df = videos[dup_mask]
        if not dup_df.empty:
            self._dropped_videos_log.info("Dropped %d duplicate video rows", len(dup_df))
            for _, row in dup_df.iterrows():
                self._dropped_videos_log.info("video_id= %s (duplicate)", row["video_id"])
                self._dropped_video_ids.add(row["video_id"])
        videos = videos[~dup_mask]

        required = ["title", "channel", "published_at", "view_count", "like_count", "fetched_comments_count"]
        mask = videos[required].isna().any(axis=1)
        dropped_df = videos[mask]
        if not dropped_df.empty:
            self._dropped_videos_log.info("Dropped %d videos with missing required fields", len(dropped_df))
            for _, row in dropped_df.iterrows():
                missing = [c for c in required if pd.isna(row[c])]
                self._dropped_videos_log.info("video_id= %s | missing= %s", row.get("video_id", "?"), missing)
                self._dropped_video_ids.add(row["video_id"])
        videos = videos[~mask]

        print(f"Dropped {len(dup_df)} duplicate videos and {len(dropped_df)} videos with missing fields.")

        os.makedirs("L2/Video_Details", exist_ok=True)
        write_deltalake("L2/Video_Details", videos.reset_index(drop=True), mode="overwrite", schema_mode="overwrite")
        return videos

    def transform_comments(self, columns_to_drop=None):
        if columns_to_drop is None:
            columns_to_drop = ["kind", "comment_kind",  "is_public" , "channel_id",  "etag",  "comment_etag" , "author_profile_image_url"  ,"author_channel_url" , "parent_comment_id", "can_reply", "total_reply_count", "text_original", "updated_at"]

        comments = DeltaTable("L1/Comments").to_pandas()

        comments = comments.drop(columns=[c for c in columns_to_drop if c in comments.columns])

        dup_mask = comments["comment_id"].duplicated(keep="first")
        dup_df = comments[dup_mask]
        if not dup_df.empty:
            self._dropped_comments_log.info("Dropped %d duplicate comment rows", len(dup_df))
            for _, row in dup_df.iterrows():
                self._dropped_comments_log.info("comment_id= %s | video_id= %s (duplicate)",
                                                row["comment_id"], row.get("video_id", "?"))
        comments = comments[~dup_mask]

        required = ["text_display", "author_display_name", "published_at", "video_id"]
        mask = comments[required].isna().any(axis=1)
        dropped_df = comments[mask]
        if not dropped_df.empty:
            self._dropped_comments_log.info("Dropped %d comments with missing required fields", len(dropped_df))
            for _, row in dropped_df.iterrows():
                missing = [c for c in required if pd.isna(row[c])]
                self._dropped_comments_log.info("comment_id= %s | video_id= %s | missing= %s",
                                                row.get("comment_id", "?"), row.get("video_id", "?"), missing)
        comments = comments[~mask]

        orphan_mask = comments["video_id"].isin(self._dropped_video_ids)
        orphan_df = comments[orphan_mask]
        if not orphan_df.empty:
            self._dropped_comments_log.info("Dropped %d comments belonging to dropped videos", len(orphan_df))
            for _, row in orphan_df.iterrows():
                self._dropped_comments_log.info("comment_id= %s | video_id= %s (orphaned)",
                                                row.get("comment_id", "?"), row.get("video_id", "?"))
        comments = comments[~orphan_mask]

        print(f"Dropped {len(dup_df)} duplicate comments, {len(dropped_df)} comments with missing fields, and {len(orphan_df)} orphaned comments.")

        os.makedirs("L2/Comments", exist_ok=True)
        write_deltalake("L2/Comments", comments.reset_index(drop=True), mode="overwrite", schema_mode="overwrite")
        return comments
