from __future__ import annotations

import json
import urllib.request
from typing import Optional

MCLOGS_API = "https://api.mclo.gs/1/log"


def upload_log(content: str, source: str = "MineHoster") -> Optional[dict]:
    content = (content or "").strip()
    if not content:
        raise ValueError("There is no server log to upload.")
    lines = content.splitlines()[-25000:]
    content = "\n".join(lines)[-10 * 1024 * 1024:]
    payload = json.dumps({"content": content, "source": source}).encode("utf-8")
    request = urllib.request.Request(MCLOGS_API, data=payload, headers={"Content-Type": "application/json", "User-Agent": "MineHoster"}, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("success"):
        raise RuntimeError(result.get("error", "mclo.gs rejected the log."))
    return result
