"""Refresh the REAL datasets in data/ (needs internet; both are open-licensed GitHub files).
  hr_attrition.csv : IBM HR Analytics employee-attrition sample (1,470 employees)  - Apache-2.0 repo (IBM/employee-attrition-aif360)
  llm_models.csv   : real LLM token prices + context windows, from LiteLLM's public price list (MIT)
"""
import csv
import json
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "data"
HR = "https://raw.githubusercontent.com/IBM/employee-attrition-aif360/master/data/emp_attrition.csv"
PRICES = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
PROVIDERS = {"openai", "anthropic", "gemini", "mistral", "deepseek", "groq", "xai", "cohere", "together_ai", "perplexity"}


def main() -> None:
    DATA.mkdir(exist_ok=True)
    (DATA / "hr_attrition.csv").write_bytes(requests.get(HR, timeout=60).content.lstrip(b"\xef\xbb\xbf"))
    raw = requests.get(PRICES, timeout=120).json()
    rows = []
    for name, v in raw.items():
        if not isinstance(v, dict) or v.get("litellm_provider") not in PROVIDERS or name.startswith("ft:"):
            continue
        if v.get("mode") not in ("chat", "embedding") or v.get("input_cost_per_token") is None:
            continue
        rows.append({
            "model": name.split("/")[-1], "provider": v["litellm_provider"], "mode": v["mode"],
            "input_usd_per_1m_tokens": round(v["input_cost_per_token"] * 1e6, 4),
            "output_usd_per_1m_tokens": round((v.get("output_cost_per_token") or 0) * 1e6, 4),
            "max_input_tokens": v.get("max_input_tokens"), "max_output_tokens": v.get("max_output_tokens"),
            "supports_function_calling": bool(v.get("supports_function_calling")),
            "supports_vision": bool(v.get("supports_vision")),
        })
    seen, uniq = set(), []
    for r in rows:  # one row per (provider, model)
        key = (r["provider"], r["model"])
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    with open(DATA / "llm_models.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(uniq[0]))
        w.writeheader()
        w.writerows(uniq)
    print(f"hr_attrition.csv + llm_models.csv ({len(uniq)} models)")


if __name__ == "__main__":
    main()
