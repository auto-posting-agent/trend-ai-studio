#!/usr/bin/env python3
"""Delete generated posts from database."""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete
from app.core.database import get_session
from app.models.source import GeneratedPost


async def delete_all_posts():
    """Delete all generated posts."""
    async for session in get_session():
        result = await session.execute(delete(GeneratedPost))
        await session.commit()
        print(f"Deleted {result.rowcount} generated posts")
        break


async def delete_failed_posts():
    """Delete only failed posts."""
    async for session in get_session():
        result = await session.execute(
            delete(GeneratedPost).where(GeneratedPost.status == "failed")
        )
        await session.commit()
        print(f"Deleted {result.rowcount} failed posts")
        break


async def list_posts():
    """List all generated posts."""
    from sqlalchemy import select

    async for session in get_session():
        result = await session.execute(select(GeneratedPost))
        posts = result.scalars().all()

        print(f"\nTotal posts: {len(posts)}\n")
        for post in posts:
            print(f"ID: {post.id}")
            print(f"Status: {post.status}")
            print(f"Permalink: {post.threads_permalink}")
            print(f"Created: {post.created_at}")
            print("-" * 50)
        break


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python delete_posts.py list           - List all posts")
        print("  python delete_posts.py delete-all     - Delete all posts")
        print("  python delete_posts.py delete-failed  - Delete only failed posts")
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        asyncio.run(list_posts())
    elif command == "delete-all":
        confirm = input("Delete ALL generated posts? (yes/no): ")
        if confirm.lower() == "yes":
            asyncio.run(delete_all_posts())
        else:
            print("Cancelled")
    elif command == "delete-failed":
        confirm = input("Delete failed posts? (yes/no): ")
        if confirm.lower() == "yes":
            asyncio.run(delete_failed_posts())
        else:
            print("Cancelled")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
