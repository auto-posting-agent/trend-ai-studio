from typing import TypedDict
from langgraph.graph import StateGraph, END
import json
import logging
from google import genai
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.vector.qdrant_embedder import QdrantEmbedder

settings = get_settings()
logger = logging.getLogger(__name__)

# Initialize Gemini client
client = genai.Client(api_key=settings.GEMINI_API_KEY)


class AgentState(TypedDict):
    """Enhanced state for the trend analysis agent."""

    # Input
    content_id: str
    raw_content: str
    title: str
    source_url: str
    category_hint: str
    content_type: str

    # Search results
    search_results: list[dict]
    similar_contents: list[dict]

    # Analysis
    analysis: dict
    should_publish: bool
    skip_reason: str | None

    # Generation
    generated_content: str
    thread_parts: list[str]
    images: list[str]

    # Final output
    final_output: dict

    # Error handling
    errors: list[str]
    retry_count: int


class TrendAgentWorkflow:
    """LangGraph workflow for trend analysis and content generation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow with conditional routing."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("search", self._search_node)
        workflow.add_node("analyze", self._analyze_node)
        workflow.add_node("generate", self._generate_node)

        # Set entry point
        workflow.set_entry_point("search")

        # Add edges
        workflow.add_edge("search", "analyze")

        # Conditional edge after analyze
        workflow.add_conditional_edges(
            "analyze",
            self._should_continue_to_generate,
            {
                "generate": "generate",
                "end": END
            }
        )

        workflow.add_edge("generate", END)

        return workflow.compile()

    async def _search_node(self, state: AgentState) -> AgentState:
        """
        Search Node: Build knowledge base for content analysis.

        Two-phase search strategy:
        1. Vector Search (지식 베이스): Find similar past content for context
        2. Web Search (Tavily): Get fresh external data (conditional for cost control)

        This creates a comprehensive knowledge base combining:
        - Internal: Past similar posts and trends
        - External: Latest web information
        """
        logger.info("=" * 80)
        logger.info("SEARCH NODE - START")
        logger.info(f"  Input:")
        logger.info(f"    Content ID: {state['content_id']}")
        logger.info(f"    Title: {state['title']}")
        logger.info(f"    Category: {state['category_hint']}")
        logger.info(f"    Content Type: {state['content_type']}")
        logger.info(f"    Content length: {len(state['raw_content'])} chars")

        # Phase 1: Vector Search - Knowledge Base
        # Always run to get context from past content
        logger.info("  Phase 1: Vector Search")
        embedder = QdrantEmbedder(self.session)
        similar = await embedder.search_similar(
            query=state["raw_content"],
            limit=5,
            threshold=0.7
        )
        state["similar_contents"] = similar
        logger.info(f"    Found {len(similar)} similar contents")

        # Phase 2: Web Search - Fresh External Data (Tavily)
        # Conditional based on content type for cost optimization
        if self._should_web_search(state):
            try:
                from tavily import TavilyClient

                tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
                query = self._build_search_query(state)

                results = tavily.search(
                    query=query,
                    search_depth="basic",  # Cost-efficient mode
                    max_results=3,
                    include_domains=[
                        "github.com",
                        "techcrunch.com",
                        "bloomberg.com",
                        "openai.com",
                        "anthropic.com",
                        "theverge.com",
                        "venturebeat.com"
                    ]
                )
                state["search_results"] = results.get("results", [])
                logger.info(f"    Found {len(state['search_results'])} web results")
            except Exception as e:
                error_msg = f"Web search failed: {str(e)}"
                logger.error(f"Tavily web search error:")
                logger.error(f"  Content ID: {state['content_id']}")
                logger.error(f"  Query: {query}")
                logger.error(f"  Error: {str(e)}")
                state["errors"].append(error_msg)
                state["search_results"] = []
                logger.info(f"    Web search failed, skipping")
        else:
            state["search_results"] = []
            logger.info(f"    Web search skipped (cost optimization)")

        logger.info("  Output:")
        logger.info(f"    Similar contents: {len(state['similar_contents'])}")
        logger.info(f"    Web results: {len(state['search_results'])}")
        logger.info("SEARCH NODE - END")
        logger.info("=" * 80)

        return state

    def _should_web_search(self, state: AgentState) -> bool:
        """Determine if web search needed (cost optimization)."""
        # Always search for breaking news
        if state.get("content_type") == "breaking_news":
            return True

        # Always search for market updates
        if state["category_hint"] in ["stock", "crypto"]:
            return True

        # Search for model releases (get competitor info)
        if state.get("content_type") == "model_release":
            return True

        # Skip for general tool launches and community posts
        return False

    def _build_search_query(self, state: AgentState) -> str:
        """Build targeted search query based on content type."""
        title = state["title"]
        category = state["category_hint"]

        # Extract key terms for model releases/launches
        if "release" in title.lower() or "launch" in title.lower():
            return f"{title} features pricing comparison"

        # Research papers need summary and analysis
        if category == "research":
            return f"{title} paper summary analysis"

        # Default: use title
        return title

    async def _analyze_node(self, state: AgentState) -> AgentState:
        """Analyze content and extract key insights for post generation."""
        logger.info("=" * 80)
        logger.info("ANALYZE NODE - START")
        logger.info(f"  Input:")
        logger.info(f"    Content ID: {state['content_id']}")
        logger.info(f"    Similar contents: {len(state['similar_contents'])}")
        logger.info(f"    Web results: {len(state['search_results'])}")

        from app.services.agent.prompts.analyze import ANALYZE_PROMPT

        # Prepare context summaries
        similar_summary = "\n".join([
            f"- {s['metadata'].get('title', 'Unknown')} (similarity: {s['similarity']:.2f})"
            for s in state["similar_contents"][:3]
        ]) if state["similar_contents"] else "None"

        search_summary = "\n".join([
            f"- {r.get('title', 'Unknown')}: {r.get('content', '')[:200]}"
            for r in state["search_results"][:3]
        ]) if state["search_results"] else "None"

        # Build prompt
        prompt = ANALYZE_PROMPT.format(
            title=state["title"],
            source_url=state["source_url"],
            category_hint=state["category_hint"],
            content=state["raw_content"][:2000],
            similar_contents=similar_summary,
            search_results=search_summary
        )

        # Use Gemini 3 Flash for analysis
        try:
            response = await client.aio.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            analysis = json.loads(response.text)
            state["analysis"] = analysis
            state["should_publish"] = True  # Always generate, no blocking

            logger.info("  Output:")
            logger.info(f"    Content type: {analysis.get('content_type', 'N/A')}")
            logger.info(f"    Target audience: {analysis.get('target_audience', 'N/A')}")
            logger.info(f"    Suggested angle: {analysis.get('suggested_angle', 'N/A')}")
            logger.info(f"    Key points: {len(analysis.get('key_points', []))}")
            logger.info(f"    Should publish: {state['should_publish']}")

        except Exception as e:
            error_msg = f"Analysis failed: {str(e)}"
            logger.error(f"Gemini analysis error:")
            logger.error(f"  Content ID: {state['content_id']}")
            logger.error(f"  Title: {state['title']}")
            logger.error(f"  Model: gemini-3-flash-preview")
            logger.error(f"  Error: {str(e)}", exc_info=True)
            state["errors"].append(error_msg)
            state["should_publish"] = False
            state["analysis"] = {}
            state["final_output"] = {
                "status": "error",
                "reason": "analysis_error",
                "errors": state["errors"]
            }
            logger.info("  Output: ERROR")

        logger.info("ANALYZE NODE - END")
        logger.info("=" * 80)

        return state

    async def _generate_node(self, state: AgentState) -> AgentState:
        """Generate Threads post using Gemini 1.5 Pro (better quality)."""
        logger.info("=" * 80)
        logger.info("GENERATE NODE - START")
        logger.info(f"  Input:")
        logger.info(f"    Content ID: {state['content_id']}")
        logger.info(f"    Should publish: {state['should_publish']}")

        if not state["should_publish"]:
            logger.info("  Skipping generation (should_publish=False)")
            state["final_output"] = {
                "status": "skipped",
                "reason": state["skip_reason"]
            }
            logger.info("GENERATE NODE - END (SKIPPED)")
            logger.info("=" * 80)
            return state

        from app.services.agent.prompts.generate import GENERATE_PROMPT

        analysis = state["analysis"]
        logger.info(f"    Analysis keys: {list(analysis.keys())}")
        logger.info(f"    Web results: {len(state['search_results'])}")

        # Prepare search context
        search_context = "\n".join([
            f"- {r.get('title', 'Unknown')}: {r.get('content', '')[:200]}"
            for r in state["search_results"][:3]
        ])

        # Build prompt
        prompt = GENERATE_PROMPT.format(
            title=state["title"],
            category=state["category_hint"],
            content_type=analysis.get("content_type", "general"),
            key_points="\n- ".join(analysis.get("key_points", [])),
            suggested_angle=analysis.get("suggested_angle", "Informative overview"),
            target_audience=analysis.get("target_audience", "general"),
            content=state["raw_content"][:3000],
            search_context=search_context or "None"
        )

        # Use Gemini 3 Flash (cost-effective, good quality)
        try:
            response = await client.aio.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7
                )
            )

            # Log raw response for debugging
            logger.info(f"Gemini generation response received for content_id: {state['content_id']}")
            logger.debug(f"Raw response: {response.text[:500]}...")

            generation = json.loads(response.text)

            # Handle case where response is wrapped in a list
            if isinstance(generation, list):
                if len(generation) > 0 and isinstance(generation[0], dict):
                    generation = generation[0]
                else:
                    raise ValueError(f"Unexpected list structure: {generation}")

            # Validate structure
            if not isinstance(generation, dict):
                raise ValueError(f"Expected dict but got {type(generation)}: {generation}")

            if "main_thread" not in generation:
                raise ValueError(f"Missing 'main_thread' key in generation: {list(generation.keys())}")

            # Build thread parts
            threads = [generation["main_thread"]]
            if generation.get("follow_up_thread"):
                threads.append(generation["follow_up_thread"])

            state["generated_content"] = generation["main_thread"]
            state["thread_parts"] = threads

            # Generate analysis summary
            analysis_summary = f"✓ Target: {state['analysis'].get('target_audience', 'General')}\n"
            analysis_summary += f"✓ Angle: {state['analysis'].get('suggested_angle', 'Informative')}\n"
            key_points = state['analysis'].get('key_points', [])
            if key_points:
                analysis_summary += f"✓ Key Points: {', '.join(key_points[:3])}"

            # Web search summary for frontend display
            web_search_summary = "\n".join([
                f"- {r.get('title', 'Unknown')}: {r.get('url', '')}"
                for r in state["search_results"][:5]
            ]) if state["search_results"] else "No web search performed"

            state["final_output"] = {
                "status": "generated",
                "content": threads,
                "link": generation.get("link", state["source_url"]),
                "hashtags": generation.get("hashtags", []),
                "analysis_summary": analysis_summary,
                "web_search_summary": web_search_summary
            }

            logger.info("  Output:")
            logger.info(f"    Status: generated")
            logger.info(f"    Thread parts: {len(threads)}")
            for idx, thread in enumerate(threads):
                logger.info(f"      Part {idx + 1}: {len(thread)} chars")
            logger.info(f"    Link: {generation.get('link', state['source_url'])}")
            logger.info(f"    Hashtags: {len(generation.get('hashtags', []))}")

        except json.JSONDecodeError as e:
            error_msg = f"JSON parsing failed: {str(e)}"
            logger.error(f"Gemini generation JSON parse error:")
            logger.error(f"  Content ID: {state['content_id']}")
            logger.error(f"  Raw response: {response.text if 'response' in locals() else 'N/A'}")
            logger.error(f"  Error: {str(e)}")
            state["errors"].append(error_msg)
            state["final_output"] = {
                "status": "error",
                "reason": error_msg
            }
        except ValueError as e:
            error_msg = f"Generation validation failed: {str(e)}"
            logger.error(f"Gemini generation validation error:")
            logger.error(f"  Content ID: {state['content_id']}")
            logger.error(f"  Generation type: {type(generation) if 'generation' in locals() else 'N/A'}")
            logger.error(f"  Generation keys: {list(generation.keys()) if 'generation' in locals() and isinstance(generation, dict) else 'N/A'}")
            logger.error(f"  Error: {str(e)}")
            state["errors"].append(error_msg)
            state["final_output"] = {
                "status": "error",
                "reason": error_msg
            }
        except Exception as e:
            error_msg = f"Generation failed: {str(e)}"
            logger.error(f"Gemini generation unexpected error:")
            logger.error(f"  Content ID: {state['content_id']}")
            logger.error(f"  Title: {state['title']}")
            logger.error(f"  Model: gemini-3-flash-preview")
            logger.error(f"  Error: {str(e)}", exc_info=True)
            state["errors"].append(error_msg)
            state["final_output"] = {
                "status": "error",
                "reason": error_msg
            }
            logger.info("  Output: ERROR")

        logger.info("GENERATE NODE - END")
        logger.info("=" * 80)

        return state

    def _should_continue_to_generate(self, state: AgentState) -> str:
        """Route based on analysis decision."""
        return "generate" if state.get("should_publish", False) else "end"

    async def run(self, state: AgentState) -> dict:
        """Run the agent workflow."""
        try:
            logger.info(f"Starting agent workflow for content_id: {state.get('content_id')}")
            result = await self.graph.ainvoke(state)
            logger.info(f"Agent workflow completed for content_id: {state.get('content_id')}, status: {result.get('final_output', {}).get('status')}")
            return result.get("final_output", {
                "status": "error",
                "reason": "workflow_incomplete",
                "errors": result.get("errors", [])
            })
        except Exception as e:
            logger.error(f"Agent workflow failed:")
            logger.error(f"  Content ID: {state.get('content_id')}")
            logger.error(f"  Error: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "reason": str(e),
                "errors": [str(e)]
            }

    async def run_with_retry(
        self,
        state: AgentState,
        max_retries: int = 3
    ) -> dict:
        """Run workflow with exponential backoff retry."""
        import asyncio

        for attempt in range(max_retries):
            try:
                result = await self.graph.ainvoke(state)
                return result["final_output"]

            except Exception as e:
                if attempt == max_retries - 1:
                    # Final attempt failed
                    return {
                        "status": "error",
                        "error": str(e),
                        "attempts": attempt + 1
                    }

                # Log and retry with exponential backoff
                wait_time = 2 ** attempt
                state["retry_count"] = attempt + 1
                await asyncio.sleep(wait_time)
