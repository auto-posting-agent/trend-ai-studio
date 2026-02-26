from datetime import datetime
import httpx
from app.config import get_settings

settings = get_settings()


class WorkflowMonitor:
    """Monitor workflow execution and costs."""

    async def log_execution(
        self,
        content_id: str,
        status: str,
        duration: float,
        api_costs: dict
    ):
        """
        Log execution metrics.

        Args:
            content_id: Content ID
            status: Execution status (generated, skipped, error)
            duration: Execution duration in seconds
            api_costs: Dict of API costs by service
        """

        total_cost = sum(api_costs.values())

        metrics = {
            "content_id": content_id,
            "status": status,
            "duration_seconds": duration,
            "api_calls": api_costs,
            "total_cost_usd": total_cost,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Alert if cost exceeds threshold
        if total_cost > 0.10:  # $0.10 per execution
            await self.send_alert(
                f"High cost execution: ${total_cost:.4f} for {content_id}"
            )

        return metrics

    async def send_alert(self, message: str):
        """
        Send alert to Discord/Telegram.

        Args:
            message: Alert message
        """

        # Discord webhook
        if settings.DISCORD_WEBHOOK_URL:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        settings.DISCORD_WEBHOOK_URL,
                        json={"content": f"⚠️ {message}"},
                        timeout=10.0
                    )
            except Exception as e:
                print(f"Discord alert failed: {e}")

        # Telegram bot
        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": settings.TELEGRAM_CHAT_ID,
                            "text": f"⚠️ {message}"
                        },
                        timeout=10.0
                    )
            except Exception as e:
                print(f"Telegram alert failed: {e}")
