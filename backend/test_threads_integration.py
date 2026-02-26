#!/usr/bin/env python3
"""
Test script for Threads API integration.

Usage:
    python test_threads_integration.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.threads import ThreadsPublisher
from app.config import get_settings

settings = get_settings()


async def test_get_user_id():
    """Test retrieving user ID from access token."""
    print("=" * 50)
    print("Testing: Get User ID")
    print("=" * 50)

    try:
        publisher = ThreadsPublisher()
        user_id = await publisher.get_user_id()
        print(f"✅ Success! User ID: {user_id}")
        return user_id
    except Exception as e:
        print(f"❌ Failed: {e}")
        return None


async def test_create_text_post(user_id: str):
    """Test creating a simple text post."""
    print("\n" + "=" * 50)
    print("Testing: Create Text Post")
    print("=" * 50)

    try:
        publisher = ThreadsPublisher()
        result = await publisher.create_text_post(
            user_id=user_id,
            text="🤖 Test post from Trend AI Studio\n\nThis is an automated test to verify API integration."
        )
        print(f"✅ Success! Post ID: {result.get('id')}")
        print(f"   Permalink: https://www.threads.net/@username/post/{result.get('id')}")
        return result
    except Exception as e:
        print(f"❌ Failed: {e}")
        return None


async def test_create_image_post(user_id: str):
    """Test creating a post with an image."""
    print("\n" + "=" * 50)
    print("Testing: Create Image Post")
    print("=" * 50)

    # Using a public test image
    test_image_url = "https://picsum.photos/800/600"

    try:
        publisher = ThreadsPublisher()
        result = await publisher.create_image_post(
            user_id=user_id,
            text="🖼️ Test image post from Trend AI Studio",
            image_url=test_image_url
        )
        print(f"✅ Success! Post ID: {result.get('id')}")
        print(f"   Image URL: {test_image_url}")
        return result
    except Exception as e:
        print(f"❌ Failed: {e}")
        print("   Note: Image posts may require app review")
        return None


async def main():
    """Run all tests."""
    print("\n🚀 Starting Threads API Integration Tests\n")

    # Check if credentials are configured
    if not settings.THREADS_ACCESS_TOKEN:
        print("❌ Error: THREADS_ACCESS_TOKEN not configured in .env file")
        print("\nPlease set up your Threads API credentials:")
        print("1. Get your access token from https://developers.facebook.com/tools/explorer/")
        print("2. Add it to .env file:")
        print("   THREADS_ACCESS_TOKEN=your_access_token_here")
        return

    print(f"Using access token: {settings.THREADS_ACCESS_TOKEN[:20]}...")
    print()

    # Test 1: Get User ID
    user_id = await test_get_user_id()
    if not user_id:
        print("\n❌ Cannot proceed without valid user ID")
        return

    # Test 2: Create Text Post
    await test_create_text_post(user_id)

    # Test 3: Create Image Post (optional)
    print("\n⚠️  Image post test is optional and may require app review.")
    response = input("Do you want to test image posting? (y/n): ")
    if response.lower() == 'y':
        await test_create_image_post(user_id)

    print("\n" + "=" * 50)
    print("✅ All tests completed!")
    print("=" * 50)
    print("\nNext steps:")
    print("1. Check your Threads profile to see the test posts")
    print("2. If everything works, you're ready to integrate with the dashboard")
    print("3. The Approve & Publish button will now post to Threads")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
