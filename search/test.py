import asyncio

from search.api_client import WikiApiClient
from search.path_finder import WikiPathFinder

async def run_demo():
    start = "Йота Персея"
    end = "Чемпионат Уругвая по футболу"

    async with WikiApiClient() as client:
        finder = WikiPathFinder(client, time_limit=30)
        result = await finder.find_path(start, end)
        print(result.format(time_limit=30, max_len=1200))


if __name__ == "__main__":
    asyncio.run(run_demo())