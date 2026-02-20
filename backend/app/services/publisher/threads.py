import httpx
from app.config import get_settings

settings = get_settings()


class ThreadsPublisher:
    """Threads API client for publishing posts."""

    BASE_URL = "https://graph.threads.net/v1.0"

    def __init__(self):
        self.access_token = settings.THREADS_ACCESS_TOKEN

    async def publish_text(self, text: str) -> dict:
        """Publish a text-only thread."""
        async with httpx.AsyncClient() as client:
            # Step 1: Create media container
            container_response = await client.post(
                f"{self.BASE_URL}/me/threads",
                params={
                    "media_type": "TEXT",
                    "text": text,
                    "access_token": self.access_token,
                },
            )
            container_data = container_response.json()

            if "id" not in container_data:
                raise Exception(f"Failed to create container: {container_data}")

            container_id = container_data["id"]

            # Step 2: Publish the container
            publish_response = await client.post(
                f"{self.BASE_URL}/me/threads_publish",
                params={
                    "creation_id": container_id,
                    "access_token": self.access_token,
                },
            )
            return publish_response.json()

    async def publish_with_image(self, text: str, image_url: str) -> dict:
        """Publish a thread with an image."""
        async with httpx.AsyncClient() as client:
            # Step 1: Create media container with image
            container_response = await client.post(
                f"{self.BASE_URL}/me/threads",
                params={
                    "media_type": "IMAGE",
                    "image_url": image_url,
                    "text": text,
                    "access_token": self.access_token,
                },
            )
            container_data = container_response.json()

            if "id" not in container_data:
                raise Exception(f"Failed to create container: {container_data}")

            container_id = container_data["id"]

            # Step 2: Publish the container
            publish_response = await client.post(
                f"{self.BASE_URL}/me/threads_publish",
                params={
                    "creation_id": container_id,
                    "access_token": self.access_token,
                },
            )
            return publish_response.json()

    async def get_user_profile(self) -> dict:
        """Get the authenticated user's profile."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/me",
                params={
                    "fields": "id,username,threads_profile_picture_url",
                    "access_token": self.access_token,
                },
            )
            return response.json()
