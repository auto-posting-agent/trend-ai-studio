import httpx
import logging
from typing import Optional, Dict, Any
from app.config import get_settings
from app.models.source import CrawledContent

settings = get_settings()
logger = logging.getLogger(__name__)


class ThreadsPublisher:
    """
    Threads API Publisher

    Publishes content to Meta's Threads platform using their API.
    Docs: https://developers.facebook.com/docs/threads
    """

    BASE_URL = "https://graph.threads.net/v1.0"

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or settings.THREADS_ACCESS_TOKEN
        if not self.access_token:
            raise ValueError("Threads access token is required")

    async def create_text_post(
        self,
        user_id: str,
        text: str,
        reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a text-only post on Threads.

        Args:
            user_id: Not used - kept for compatibility (Threads API uses /me)
            text: The post content (max 500 characters)
            reply_to: Optional post ID to reply to

        Returns:
            Dict with post_id and creation details
        """
        # Check text length (500 character limit)
        if len(text) > 500:
            raise ValueError(f"Text too long: {len(text)} characters (max 500)")

        async with httpx.AsyncClient() as client:
            # Step 1: Create a media container
            # Threads API only supports /me endpoint
            container_url = f"{self.BASE_URL}/me/threads"

            payload = {
                "media_type": "TEXT",
                "text": text,
                "access_token": self.access_token
            }

            if reply_to:
                payload["reply_to_id"] = reply_to

            logger.info(f"Creating Threads container...")
            logger.info(f"  Text length: {len(text)} chars")
            logger.info(f"  Reply to: {reply_to if reply_to else 'None (main post)'}")

            try:
                response = await client.post(container_url, data=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                # Get detailed error from Threads API
                error_detail = e.response.text
                logger.error(f"Threads API container creation failed:")
                logger.error(f"  Status: {e.response.status_code}")
                logger.error(f"  Response: {error_detail}")
                logger.error(f"  Text length: {len(text)} chars")
                raise ValueError(f"Threads API error ({e.response.status_code}): {error_detail}")

            container_data = response.json()
            logger.info(f"Container created successfully:")
            logger.info(f"  Response: {container_data}")

            container_id = container_data.get("id")

            if not container_id:
                raise ValueError(f"No container ID in response: {container_data}")

            logger.info(f"  Container ID: {container_id}")

            # Wait for server to process the upload (recommended by Threads API)
            logger.info(f"Waiting 5 seconds for Threads to process container...")
            import asyncio
            await asyncio.sleep(5)  # Wait 5 seconds before publishing

            # Step 2: Publish the container
            logger.info(f"Publishing container to Threads...")
            publish_url = f"{self.BASE_URL}/me/threads_publish"
            publish_payload = {
                "creation_id": container_id,
                "access_token": self.access_token
            }

            try:
                publish_response = await client.post(publish_url, data=publish_payload)
                publish_response.raise_for_status()
            except httpx.HTTPStatusError as e:
                error_detail = e.response.text
                logger.error(f"Threads API publish failed:")
                logger.error(f"  Status: {e.response.status_code}")
                logger.error(f"  Response: {error_detail}")
                logger.error(f"  Container ID: {container_id}")
                raise ValueError(f"Threads API publish error ({e.response.status_code}): {error_detail}")

            publish_data = publish_response.json()
            logger.info(f"Published to Threads successfully:")
            logger.info(f"  Response: {publish_data}")
            logger.info(f"  Post ID: {publish_data.get('id')}")

            return publish_data

    async def create_image_post(
        self,
        user_id: str,
        text: str,
        image_url: str,
        reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a post with an image on Threads.

        Args:
            user_id: Not used - kept for compatibility (Threads API uses /me)
            text: The post content
            image_url: Public URL of the image
            reply_to: Optional post ID to reply to

        Returns:
            Dict with post_id and creation details
        """
        async with httpx.AsyncClient() as client:
            # Threads API only supports /me endpoint
            container_url = f"{self.BASE_URL}/me/threads"

            payload = {
                "media_type": "IMAGE",
                "image_url": image_url,
                "text": text,
                "access_token": self.access_token
            }

            if reply_to:
                payload["reply_to_id"] = reply_to

            response = await client.post(container_url, data=payload)
            response.raise_for_status()

            container_data = response.json()
            container_id = container_data.get("id")

            # Publish
            publish_url = f"{self.BASE_URL}/me/threads_publish"
            publish_payload = {
                "creation_id": container_id,
                "access_token": self.access_token
            }

            publish_response = await client.post(publish_url, data=publish_payload)
            publish_response.raise_for_status()

            return publish_response.json()

    async def get_user_id(self) -> str:
        """
        Get the user ID from the access token.

        Returns:
            The Threads user ID
        """
        async with httpx.AsyncClient() as client:
            url = f"{self.BASE_URL}/me"
            params = {"access_token": self.access_token}

            try:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                return data.get("id")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400:
                    raise ValueError(
                        "Threads API access token is invalid or expired. "
                        "Please update THREADS_ACCESS_TOKEN in .env file. "
                        "Get a new token from: https://developers.facebook.com/apps"
                    )
                raise

    async def get_profile(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get Threads profile information.

        Args:
            user_id: Optional user ID (ignored - always fetches authenticated user)

        Returns:
            Dict with profile data
        """
        # Threads API only supports 'me' endpoint for profile
        async with httpx.AsyncClient() as client:
            url = f"{self.BASE_URL}/me"
            params = {
                "fields": "id,username,name,threads_profile_picture_url,threads_biography",
                "access_token": self.access_token
            }

            response = await client.get(url, params=params)
            response.raise_for_status()

            return response.json()

    async def get_threads(self, user_id: Optional[str] = None, limit: int = 25) -> Dict[str, Any]:
        """
        Get user's published threads.

        Args:
            user_id: Optional user ID (ignored - always fetches authenticated user)
            limit: Number of threads to fetch

        Returns:
            Dict with threads data
        """
        # Threads API only supports 'me' endpoint
        async with httpx.AsyncClient() as client:
            url = f"{self.BASE_URL}/me/threads"
            params = {
                "fields": "id,media_type,media_url,permalink,text,timestamp,username,is_quote_post",
                "limit": limit,
                "access_token": self.access_token
            }

            response = await client.get(url, params=params)
            response.raise_for_status()

            return response.json()

    async def get_thread_insights(self, thread_id: str) -> Dict[str, Any]:
        """
        Get insights for a specific thread.

        Args:
            thread_id: The thread ID

        Returns:
            Dict with insights data (views, likes, replies, etc.)
        """
        async with httpx.AsyncClient() as client:
            url = f"{self.BASE_URL}/{thread_id}/insights"
            params = {
                "metric": "views,likes,replies,reposts,quotes",
                "access_token": self.access_token
            }

            response = await client.get(url, params=params)
            response.raise_for_status()

            return response.json()

    async def get_conversation(self, thread_id: str) -> Dict[str, Any]:
        """
        Get conversation (replies) for a specific thread.

        Args:
            thread_id: The thread ID

        Returns:
            Dict with conversation data
        """
        async with httpx.AsyncClient() as client:
            url = f"{self.BASE_URL}/{thread_id}/conversation"
            params = {
                "fields": "id,text,timestamp,username,hide_status",
                "access_token": self.access_token
            }

            response = await client.get(url, params=params)
            response.raise_for_status()

            return response.json()

    async def get_replies(self, thread_id: str) -> Dict[str, Any]:
        """
        Get direct replies to a specific thread.

        Args:
            thread_id: The thread ID

        Returns:
            Dict with replies data
        """
        async with httpx.AsyncClient() as client:
            url = f"{self.BASE_URL}/{thread_id}/replies"
            params = {
                "fields": "id,text,timestamp,username,hide_status",
                "access_token": self.access_token
            }

            response = await client.get(url, params=params)
            response.raise_for_status()

            return response.json()


async def publish_content_to_threads(content: CrawledContent) -> Dict[str, Any]:
    """
    Publish a CrawledContent item to Threads.

    Extracts the generated post from extra_data and publishes it.

    Args:
        content: The CrawledContent instance with generated_post in extra_data

    Returns:
        Dict with publishing results
    """
    if not content.extra_data or "generated_post" not in content.extra_data:
        raise ValueError("Content must have a generated_post in extra_data")

    generated_post = content.extra_data["generated_post"]

    publisher = ThreadsPublisher()
    user_id = await publisher.get_user_id()

    # Check if there's an image URL in extra_data
    image_url = content.extra_data.get("image_url")

    if image_url:
        result = await publisher.create_image_post(
            user_id=user_id,
            text=generated_post,
            image_url=image_url
        )
    else:
        result = await publisher.create_text_post(
            user_id=user_id,
            text=generated_post
        )

    return {
        "status": "published",
        "thread_id": result.get("id"),
        "permalink": f"https://www.threads.net/@username/post/{result.get('id')}",
        "published_at": result.get("timestamp")
    }
