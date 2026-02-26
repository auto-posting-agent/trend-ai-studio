# Threads API Setup Guide

## Overview
This guide walks you through setting up Meta's Threads API for publishing posts from Trend AI Studio.

## Prerequisites
- Meta Developer Account
- Instagram Professional/Creator Account (required for Threads)
- Business verification may be required for API access

## Step 1: Create a Meta App

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Click "My Apps" → "Create App"
3. Select "Business" as the app type
4. Fill in app details:
   - App name: "Trend AI Studio" (or your preferred name)
   - App contact email
   - Business account (if applicable)

## Step 2: Add Threads API Product

1. In your app dashboard, go to "Add Products"
2. Find "Threads" and click "Set Up"
3. Configure Threads permissions:
   - `threads_basic` - Basic read access
   - `threads_content_publish` - Ability to create and publish posts
   - `threads_manage_insights` - (Optional) View analytics

## Step 3: Get App Credentials

1. In your app dashboard, navigate to Settings → Basic
2. Copy these values:
   - **App ID** → `THREADS_APP_ID`
   - **App Secret** → `THREADS_APP_SECRET`

## Step 4: Generate Access Token

### Option A: Using Graph API Explorer (Testing)

1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your app from the dropdown
3. Click "Generate Access Token"
4. Select required permissions:
   - `threads_basic`
   - `threads_content_publish`
5. Copy the access token → `THREADS_ACCESS_TOKEN`

**Note:** This token expires after 1-2 hours. Use Option B for production.

### Option B: OAuth Flow (Production)

1. Implement OAuth flow to get long-lived tokens
2. Use the following endpoint:
   ```
   https://www.threads.net/oauth/authorize?
     client_id={app-id}&
     redirect_uri={redirect-uri}&
     scope=threads_basic,threads_content_publish&
     response_type=code
   ```
3. Exchange authorization code for access token:
   ```bash
   curl -X POST \
     https://graph.threads.net/oauth/access_token \
     -d client_id={app-id} \
     -d client_secret={app-secret} \
     -d grant_type=authorization_code \
     -d redirect_uri={redirect-uri} \
     -d code={authorization-code}
   ```

4. Exchange short-lived token for long-lived token (60 days):
   ```bash
   curl -X GET \
     "https://graph.threads.net/access_token?
      grant_type=th_exchange_token&
      client_secret={app-secret}&
      access_token={short-lived-token}"
   ```

## Step 5: Configure Environment Variables

Add these to your `.env` file:

```env
# Threads API Configuration
THREADS_APP_ID=your_app_id_here
THREADS_APP_SECRET=your_app_secret_here
THREADS_ACCESS_TOKEN=your_access_token_here
```

## Step 6: Verify Setup

Test the integration with this Python script:

```python
import asyncio
from app.services.threads import ThreadsPublisher

async def test_threads():
    publisher = ThreadsPublisher()

    # Get user ID
    user_id = await publisher.get_user_id()
    print(f"Threads User ID: {user_id}")

    # Create a test post
    result = await publisher.create_text_post(
        user_id=user_id,
        text="🤖 Test post from Trend AI Studio"
    )
    print(f"Post created: {result}")

asyncio.run(test_threads())
```

## API Rate Limits

- **Posts per hour:** 250 posts
- **Posts per day:** 1000 posts
- **Text length:** Max 500 characters
- **Images:** Max 10 per carousel

## Content Guidelines

1. **Text Posts:**
   - Max 500 characters
   - URLs are automatically converted to link previews
   - Hashtags and mentions supported

2. **Image Posts:**
   - Image must be publicly accessible via URL
   - Supported formats: JPG, PNG
   - Max size: 8MB
   - Aspect ratio: 4:5 recommended

3. **Best Practices:**
   - Use emojis for engagement
   - Keep posts concise and clear
   - Add relevant hashtags (max 30)
   - Include call-to-action when appropriate

## Workflow in Trend AI Studio

1. **Crawl Content** → Content discovered and saved
2. **Generate Post** → AI creates Thread-optimized post
3. **Review** → Human reviews generated post
4. **Approve & Publish** → Post goes live on Threads
5. **Track** → Monitor engagement and analytics

## Troubleshooting

### "Invalid access token"
- Token may have expired
- Regenerate using OAuth flow
- Check token has correct permissions

### "User not authorized"
- Ensure Instagram account is Professional/Creator
- Verify app is approved for Threads API
- Check app is not in Development Mode for production

### "Rate limit exceeded"
- Wait before making more requests
- Implement exponential backoff
- Consider queuing posts

## Additional Resources

- [Threads API Documentation](https://developers.facebook.com/docs/threads)
- [API Reference](https://developers.facebook.com/docs/threads/reference)
- [Best Practices](https://developers.facebook.com/docs/threads/best-practices)
- [Rate Limits](https://developers.facebook.com/docs/threads/rate-limits)

## Support

For issues specific to Trend AI Studio integration:
1. Check logs in `backend/logs/`
2. Verify credentials in `.env`
3. Test API connection with test script above

For Threads API issues:
- [Meta Developers Community](https://developers.facebook.com/community/)
- [Threads API Support](https://developers.facebook.com/support/threads-api/)
