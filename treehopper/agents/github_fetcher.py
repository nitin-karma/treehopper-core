import httpx
from treehopper.treehopper import agent


@agent(
    "/api/v1/agents/github",
    method="GET",
    goal="Fetch GitHub repo metadata",
    tags=["Example Agents"],
)
async def github(repo: str):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"https://api.github.com/repos/{repo}")
            data = r.json()
            return {
                "name": data["full_name"],
                "description": data["description"],
                "stars": data["stargazers_count"],
                "forks": data["forks_count"],
                "language": data["language"],
                "url": data["html_url"],
            }
    except Exception as e:
        return {"error": str(e)}
