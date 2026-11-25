"""Build the analytics database the agents query.

REAL data   : employees      <- data/hr_attrition.csv (IBM HR Analytics sample, 1,470 rows)
              llm_models     <- data/llm_models.csv   (real token prices/context windows from LiteLLM, MIT)
SYNTHETIC   : customers, products, orders (sales); support_tickets (AI-platform support desk);
              token_usage (daily LLM usage per customer; cost computed from the REAL prices above).
Synthetic tables are generated deterministically (seed=42) and are clearly NOT real company data.
"""
import csv
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE.parent / "data"
DB = HERE / "sales.db"
REGIONS = ["North", "South", "East", "West"]
SEGMENTS = ["Consumer", "SMB", "Enterprise"]
CATEGORIES = {"Laptops": (500, 2200), "Phones": (200, 1300), "Accessories": (10, 150), "Monitors": (120, 900)}
DROP_HR = {"EmployeeCount", "Over18", "StandardHours"}  # constant columns

TICKET_CATEGORIES = {  # category: (weight, base resolution hours, subject templates)
    "API rate limit / quota": (22, 4, ["429 errors on {m}", "Need higher rate limit for {m}", "Quota exhausted unexpectedly"]),
    "Billing & token costs": (18, 8, ["Unexpected token charges on {m}", "Invoice does not match usage", "Request cost estimate for {m}"]),
    "Hallucination / answer quality": (16, 30, ["{m} gives wrong facts", "Answers ignore provided context", "Inconsistent output from {m}"]),
    "Latency / timeouts": (14, 10, ["{m} responses very slow", "Streaming stalls mid-response", "Timeouts at peak hours"]),
    "RAG / retrieval issues": (10, 26, ["Vector search returns irrelevant chunks", "Embedding index out of date", "Citations missing in answers"]),
    "Fine-tuning failure": (6, 48, ["Fine-tune job stuck", "Training loss diverges", "Cannot deploy fine-tuned {m}"]),
    "Agent / tool-calling bug": (8, 22, ["Tool call arguments malformed", "Agent loops without finishing", "MCP server connection drops"]),
    "Security & data privacy": (4, 36, ["Request for data retention policy", "PII appeared in logs", "SSO setup help"]),
    "Account & access": (2, 3, ["Cannot reset API key", "Add teammate to workspace"]),
}
PRIORITIES = [("Low", 0.35, 1.6), ("Medium", 0.40, 1.0), ("High", 0.20, 0.55), ("Critical", 0.05, 0.3)]
TEAMS = ["Platform Support", "ML Engineering", "Billing Ops", "Solutions Engineering"]
CHANNELS = ["Email", "Chat", "Web form", "Slack"]


def _num(v: str):
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return v


def build(path: Path = DB, seed: int = 42) -> Path:
    rnd = random.Random(seed)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT, region TEXT, segment TEXT);
    CREATE TABLE products(id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL);
    CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INTEGER, product_id INTEGER,
                        quantity INTEGER, order_date TEXT);
    CREATE TABLE support_tickets(id INTEGER PRIMARY KEY, customer_id INTEGER, created_at TEXT, category TEXT,
        priority TEXT, channel TEXT, assigned_team TEXT, model TEXT, subject TEXT, status TEXT,
        first_response_minutes INTEGER, resolution_hours REAL, csat INTEGER);
    CREATE TABLE token_usage(id INTEGER PRIMARY KEY, customer_id INTEGER, usage_date TEXT, model TEXT,
        requests INTEGER, input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL);
    """)
    # ---- synthetic sales ----
    con.executemany("INSERT INTO customers VALUES (?,?,?,?)",
                    [(i, f"Customer {i}", rnd.choice(REGIONS), rnd.choice(SEGMENTS)) for i in range(1, 201)])
    products, pid = [], 1
    for cat, (lo, hi) in CATEGORIES.items():
        for n in range(1, 9):
            products.append((pid, f"{cat[:-1]} Model {n}", cat, round(rnd.uniform(lo, hi), 2)))
            pid += 1
    con.executemany("INSERT INTO products VALUES (?,?,?,?)", products)
    start = date(2024, 1, 1)
    con.executemany("INSERT INTO orders VALUES (?,?,?,?,?)",
                    [(i, rnd.randint(1, 200), rnd.randint(1, len(products)), rnd.randint(1, 5),
                      (start + timedelta(days=rnd.randint(0, 365))).isoformat()) for i in range(1, 5001)])

    # ---- REAL: HR attrition ----
    with open(DATA / "hr_attrition.csv", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = [c for c in reader.fieldnames if c not in DROP_HR]
        rows = [[_num(r[c]) for c in cols] for r in reader]
    types = ["INTEGER" if isinstance(rows[0][i], int) else "REAL" if isinstance(rows[0][i], float) else "TEXT"
             for i in range(len(cols))]
    con.execute(f"CREATE TABLE employees({', '.join(f'{c} {t}' for c, t in zip(cols, types))})")
    con.executemany(f"INSERT INTO employees VALUES ({','.join('?' * len(cols))})", rows)

    # ---- REAL: LLM prices ----
    with open(DATA / "llm_models.csv", newline="", encoding="utf-8") as f:
        models = list(csv.DictReader(f))
    con.execute("""CREATE TABLE llm_models(model TEXT, provider TEXT, mode TEXT, input_usd_per_1m_tokens REAL,
        output_usd_per_1m_tokens REAL, max_input_tokens INTEGER, max_output_tokens INTEGER,
        supports_function_calling INTEGER, supports_vision INTEGER)""")
    con.executemany("INSERT INTO llm_models VALUES (?,?,?,?,?,?,?,?,?)", [(
        m["model"], m["provider"], m["mode"], float(m["input_usd_per_1m_tokens"]), float(m["output_usd_per_1m_tokens"]),
        int(float(m["max_input_tokens"])) if m["max_input_tokens"] else None,
        int(float(m["max_output_tokens"])) if m["max_output_tokens"] else None,
        m["supports_function_calling"] == "True", m["supports_vision"] == "True") for m in models])

    # ---- SYNTHETIC: token usage (real prices) ----
    chat = [m for m in models if m["mode"] == "chat" and float(m["output_usd_per_1m_tokens"]) > 0
            and m["provider"] in ("openai", "anthropic", "gemini", "deepseek", "mistral")]
    pool = rnd.sample(chat, min(14, len(chat)))
    usage = []
    for i in range(1, 8001):
        m = rnd.choice(pool)
        reqs = rnd.randint(1, 400)
        tin, tout = reqs * rnd.randint(300, 3000), reqs * rnd.randint(80, 900)
        cost = tin * float(m["input_usd_per_1m_tokens"]) / 1e6 + tout * float(m["output_usd_per_1m_tokens"]) / 1e6
        usage.append((i, rnd.randint(1, 200), (start + timedelta(days=rnd.randint(0, 365))).isoformat(),
                      m["model"], reqs, tin, tout, round(cost, 4)))
    con.executemany("INSERT INTO token_usage VALUES (?,?,?,?,?,?,?,?)", usage)

    # ---- SYNTHETIC: support tickets ----
    cats = list(TICKET_CATEGORIES)
    weights = [TICKET_CATEGORIES[c][0] for c in cats]
    tickets = []
    for i in range(1, 3001):
        cat = rnd.choices(cats, weights)[0]
        _, base_h, subjects = TICKET_CATEGORIES[cat]
        prio, _, mult = rnd.choices(PRIORITIES, [p[1] for p in PRIORITIES])[0]
        m = rnd.choice(pool)["model"]
        created = start + timedelta(days=rnd.randint(0, 365))
        open_ = rnd.random() < 0.08
        res = None if open_ else round(max(0.5, rnd.gauss(base_h * mult, base_h * mult * 0.35)), 1)
        csat = None if (open_ or rnd.random() < 0.25) else max(1, min(5, round(5 - res / 20 + rnd.gauss(0, 0.8))))
        tickets.append((i, rnd.randint(1, 200), created.isoformat(), cat, prio, rnd.choice(CHANNELS), rnd.choice(TEAMS), m,
                        rnd.choice(subjects).format(m=m), "Open" if open_ else "Resolved",
                        int(max(2, rnd.gauss(45 * mult, 15))), res, csat))
    con.executemany("INSERT INTO support_tickets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", tickets)
    con.commit()
    con.close()
    return path


if __name__ == "__main__":
    print("created", build())
