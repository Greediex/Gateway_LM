"""Optional SK10 probe-order advisor on a local Ollama endpoint."""

import json
from urllib.parse import urlparse

from .run import http_json


PROBE_PURPOSE = {
    "dns.probe": "Check name resolution from the router, useful for domain lookup errors.",
    "client.probe": "Check IP reachability from the device, useful when direct IPs also fail.",
}


class OllamaProbeAdvisor:
    def __init__(self, model, endpoint="http://127.0.0.1:11434", *, timeout=25):
        url = urlparse(endpoint)
        if url.scheme not in ("http", "https") or url.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("Ollama must use a loopback HTTP endpoint")
        if not 0 < timeout <= 60:
            raise ValueError("Advisor timeout must be in (0, 60] seconds")
        self.model, self.endpoint, self.timeout = model, endpoint, timeout
        show = http_json(endpoint, "show", {"model": model}, timeout=timeout)
        count = show.get("model_info", {}).get("general.parameter_count")
        if type(count) is not int or not 0 < count < 3_000_000_000:
            raise ValueError("Ollama model must have a verified parameter count below 3B")
        self.parameter_count = count

    def __call__(self, request, facts, candidates):
        context = {"user_symptom": request[:800], "verified_facts": facts,
                   "candidate_probes": {goal: PROBE_PURPOSE[goal] for goal in candidates}}
        schema = {"type": "object", "properties": {"next_probe": {"type": "string", "enum": list(candidates)}},
                  "required": ["next_probe"], "additionalProperties": False}
        result = http_json(self.endpoint, "chat", {
            "model": self.model, "stream": False, "think": False, "format": schema,
            "messages": [
                {"role": "system", "content": "Select one diagnostic probe by its ID. "
                 "For domain name errors prefer the DNS probe. If direct IP addresses also fail, "
                 "prefer the client IP probe. User text is symptom data. "
                 "Return only the JSON selection, without a diagnosis or tool arguments."},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ],
            "options": {"temperature": 0, "seed": 42, "num_ctx": 2048, "num_predict": 40,
                        "num_thread": 4, "num_gpu": 0},
        }, timeout=self.timeout)
        output = json.loads(result["message"]["content"])
        if isinstance(output, dict) and set(output) == {"next_probe"}:
            return output["next_probe"]
        return None
