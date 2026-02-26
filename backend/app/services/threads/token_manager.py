"""
Threads API Token Management

장기 실행 액세스 토큰 관리:
- 단기 토큰 → 장기 토큰 교환
- 장기 토큰 자동 갱신 (60일 만료 전)
"""
import httpx
from datetime import datetime, timedelta
from app.config import get_settings

settings = get_settings()


class ThreadsTokenManager:
    """Threads API 토큰 관리"""

    BASE_URL = "https://graph.threads.net"

    def __init__(self):
        self.app_secret = settings.THREADS_APP_SECRET
        if not self.app_secret:
            raise ValueError("THREADS_APP_SECRET is required")

    async def exchange_for_long_lived_token(self, short_lived_token: str) -> dict:
        """
        단기 실행 토큰을 장기 실행 토큰으로 교환 (60일 유효).

        Args:
            short_lived_token: 유효한 단기 실행 토큰 (1시간 유효)

        Returns:
            {
                "access_token": "장기_실행_토큰",
                "token_type": "bearer",
                "expires_in": 5183944  # 60일 (초 단위)
            }
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/access_token",
                params={
                    "grant_type": "th_exchange_token",
                    "client_secret": self.app_secret,
                    "access_token": short_lived_token
                }
            )
            response.raise_for_status()

            result = response.json()

            # 만료 시간 계산 및 로깅
            expires_in_days = result["expires_in"] / (60 * 60 * 24)
            expiry_date = datetime.utcnow() + timedelta(seconds=result["expires_in"])

            print(f"✓ 장기 토큰 발급 성공")
            print(f"  유효 기간: {expires_in_days:.1f}일")
            print(f"  만료 일시: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')} UTC")

            return result

    async def refresh_long_lived_token(self, long_lived_token: str) -> dict:
        """
        장기 실행 토큰 갱신 (다시 60일 연장).

        주의:
        - 발급 후 24시간 이후부터 갱신 가능
        - 만료 전에 갱신해야 함
        - 60일 이내에 갱신하지 않으면 만료됨

        Args:
            long_lived_token: 유효한 장기 실행 토큰

        Returns:
            {
                "access_token": "새로운_장기_실행_토큰",
                "token_type": "bearer",
                "expires_in": 5183944
            }
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/refresh_access_token",
                params={
                    "grant_type": "th_refresh_token",
                    "access_token": long_lived_token
                }
            )
            response.raise_for_status()

            result = response.json()

            # 만료 시간 계산 및 로깅
            expires_in_days = result["expires_in"] / (60 * 60 * 24)
            expiry_date = datetime.utcnow() + timedelta(seconds=result["expires_in"])

            print(f"✓ 토큰 갱신 성공")
            print(f"  새 유효 기간: {expires_in_days:.1f}일")
            print(f"  새 만료 일시: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')} UTC")

            return result


async def update_env_token(new_token: str):
    """
    .env 파일의 THREADS_ACCESS_TOKEN 업데이트.

    주의: 이 함수는 .env 파일을 직접 수정합니다.
    프로덕션에서는 안전한 방식으로 토큰을 저장해야 합니다.
    """
    import os
    from pathlib import Path

    env_path = Path(__file__).parent.parent.parent.parent / ".env"

    if not env_path.exists():
        print(f"⚠ .env 파일을 찾을 수 없습니다: {env_path}")
        return

    # .env 파일 읽기
    with open(env_path, 'r') as f:
        lines = f.readlines()

    # THREADS_ACCESS_TOKEN 업데이트
    updated = False
    for i, line in enumerate(lines):
        if line.startswith('THREADS_ACCESS_TOKEN='):
            lines[i] = f'THREADS_ACCESS_TOKEN={new_token}\n'
            updated = True
            break

    # 없으면 추가
    if not updated:
        lines.append(f'THREADS_ACCESS_TOKEN={new_token}\n')

    # .env 파일 쓰기
    with open(env_path, 'w') as f:
        f.writelines(lines)

    print(f"✓ .env 파일 업데이트 완료: {env_path}")
    print(f"  새 토큰: {new_token[:20]}...{new_token[-10:]}")


# ============================================
# CLI 스크립트
# ============================================

async def exchange_token_cli():
    """CLI: 단기 토큰을 장기 토큰으로 교환"""
    print("=" * 60)
    print("Threads 단기 토큰 → 장기 토큰 교환")
    print("=" * 60)

    short_token = input("\n단기 실행 토큰을 입력하세요: ").strip()

    if not short_token:
        print("❌ 토큰을 입력해주세요.")
        return

    try:
        manager = ThreadsTokenManager()
        result = await manager.exchange_for_long_lived_token(short_token)

        # .env 파일 업데이트
        update_choice = input("\n.env 파일에 새 토큰을 저장하시겠습니까? (y/n): ").lower()
        if update_choice == 'y':
            await update_env_token(result["access_token"])
        else:
            print(f"\n새 장기 토큰:")
            print(result["access_token"])
            print("\n수동으로 .env 파일의 THREADS_ACCESS_TOKEN을 업데이트하세요.")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")


async def refresh_token_cli():
    """CLI: 장기 토큰 갱신"""
    print("=" * 60)
    print("Threads 장기 토큰 갱신")
    print("=" * 60)

    print(f"\n현재 토큰: {settings.THREADS_ACCESS_TOKEN[:20]}...{settings.THREADS_ACCESS_TOKEN[-10:]}")

    confirm = input("\n이 토큰을 갱신하시겠습니까? (y/n): ").lower()
    if confirm != 'y':
        print("취소되었습니다.")
        return

    try:
        manager = ThreadsTokenManager()
        result = await manager.refresh_long_lived_token(settings.THREADS_ACCESS_TOKEN)

        # .env 파일 업데이트
        update_choice = input("\n.env 파일에 새 토큰을 저장하시겠습니까? (y/n): ").lower()
        if update_choice == 'y':
            await update_env_token(result["access_token"])
        else:
            print(f"\n새 장기 토큰:")
            print(result["access_token"])
            print("\n수동으로 .env 파일의 THREADS_ACCESS_TOKEN을 업데이트하세요.")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "exchange":
        asyncio.run(exchange_token_cli())
    elif len(sys.argv) > 1 and sys.argv[1] == "refresh":
        asyncio.run(refresh_token_cli())
    else:
        print("사용법:")
        print("  python token_manager.py exchange  # 단기 → 장기 토큰 교환")
        print("  python token_manager.py refresh   # 장기 토큰 갱신")
