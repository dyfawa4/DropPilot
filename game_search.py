"""Canonical Twitch category search with an immediate local fallback."""
import asyncio
import time
import unicodedata

def normalized(value):
    return unicodedata.normalize("NFKC", value).casefold().strip()

def matching_games(names, query):
    unique = {normalized(name): name for name in names if name}
    term = normalized(query)
    return sorted((name for key, name in unique.items() if term in key),
                  key=lambda name: (not normalized(name).startswith(term), normalized(name)))[:30]

async def search_games(client, query, known_names):
    query = str(query).strip()[:100]
    names = set(known_names) | set(client.settings.priority)
    result = {"ok": True, "games": matching_games(names, query), "remote": False}
    if len(query) < 2 or not client._auth_state._logged_in.is_set():
        return result
    cache = getattr(client, "_game_search_cache", {})
    key = normalized(query)
    cached = cache.get(key)
    if cached and time.monotonic() - cached[0] < 120:
        result.update(games=matching_games(names | set(cached[1]), query), remote=True)
        return result
    try:
        async with asyncio.timeout(6):
            auth = await client.get_auth()
            async with client.request("GET", "https://api.twitch.tv/helix/search/categories",
                    params={"query": key, "first": 30}, headers={
                        "Client-ID": client._client_type.CLIENT_ID,
                        "Authorization": "Bearer " + auth.access_token}) as response:
                if response.status != 200:
                    raise ValueError("Category search unavailable")
                data = await response.json()
            remote = [game["name"] for game in data.get("data", []) if game.get("name")]
            cache[key] = (time.monotonic(), remote)
            # A small bounded cache prevents unbounded growth in long sessions.
            if len(cache) > 50:
                cache.pop(next(iter(cache)))
            client._game_search_cache = cache
            result.update(games=matching_games(names | set(remote), query), remote=True)
    except (TimeoutError, ValueError):
        result["notice"] = "在线搜索暂不可用，显示已发现的游戏；也可以输入完整分类名称。"
    return result
