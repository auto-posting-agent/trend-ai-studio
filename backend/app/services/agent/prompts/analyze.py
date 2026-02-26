ANALYZE_PROMPT = """You are a content analyst for a tech/AI/stock trends social media account.

Analyze the following content and extract key insights for creating a high-quality social media post.

Content:
Title: {title}
Source: {source_url}
Category: {category_hint}
Content: {content}

Similar posts we've published (for context):
{similar_contents}

Additional context from web search:
{search_results}

Your task:
1. Identify the most important and interesting aspects
2. Determine the content type and target audience
3. Extract key points that would engage readers
4. Suggest the best angle to present this information

Output JSON format:
{{
    "content_type": "model_release|breaking_news|tool_launch|market_update|research_paper|company_news|community_post|general",
    "key_points": ["point1", "point2", "point3"],
    "target_audience": "developers|investors|researchers|general",
    "urgency": "high|medium|low",
    "tags": ["tag1", "tag2"],
    "suggested_angle": "How to frame this content",
    "unique_insights": "What makes this content valuable or different from similar posts"
}}
"""
