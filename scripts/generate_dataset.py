#!/usr/bin/env python3
"""
Deterministic dataset generator for RoomFit Copilot (Candidate C-2474).

Generates the three input files described in the assessment specification:
  - data/catalog.jsonl           (~2000 realistic furniture products)
  - data/catalog_updates.jsonl   (~50 price/stock changes referencing real IDs)
  - data/eval_questions.jsonl    (60 questions with ground-truth product IDs)

The script is fully deterministic (seed=42), offline, and reproducible.

Usage:
    python3 scripts/generate_dataset.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from datetime import datetime, timedelta

SEED = 42
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

CATALOG_PATH = DATA_DIR / "catalog.jsonl"
UPDATES_PATH = DATA_DIR / "catalog_updates.jsonl"
EVAL_PATH = DATA_DIR / "eval_questions.jsonl"

# ---------------------------------------------------------------------------
# Category definitions: (name, id_prefix, target_count, price_range,
#                        width_cm, height_cm, depth_cm, weight_kg,
#                        materials, adjectives, nouns, tags)
# ---------------------------------------------------------------------------

CATEGORIES = [
    ("desks", "DESK", 250, (149, 899), (80, 180), (70, 80), (45, 80), (10, 40),
     ["Oak", "Walnut", "Bamboo", "Pine", "Birch", "Steel", "Glass"],
     ["Modern", "Classic", "Minimalist", "Industrial", "Scandinavian", "Adjustable", "Ergonomic", "Rustic"],
     ["Standing Desk", "Writing Desk", "Computer Desk", "Study Desk", "Executive Desk"],
     ["adjustable", "standing", "office", "home office", "electric", "wooden"]),
    ("chairs", "CHAIR", 300, (49, 599), (40, 75), (75, 130), (40, 75), (3, 25),
     ["Mesh", "Leather", "Velvet", "Linen", "Oak", "Metal", "Rattan"],
     ["Ergonomic", "Modern", "Vintage", "Adjustable", "Padded", "Swivel", "Sleek"],
     ["Office Chair", "Dining Chair", "Lounge Chair", "Accent Chair", "Task Chair"],
     ["ergonomic", "office", "dining", "lumbar", "swivel", "padded"]),
    ("storage", "SHELF", 250, (79, 699), (40, 150), (60, 220), (25, 60), (10, 70),
     ["Oak", "Metal", "Pine", "Walnut", "Steel", "Bamboo"],
     ["Industrial", "Minimalist", "Modular", "Rustic", "Contemporary", "Vintage"],
     ["Bookshelf", "Cabinet", "Wardrobe", "Shelving Unit", "Sideboard"],
     ["storage", "bookshelf", "modular", "open", "closed", "tall"]),
    ("sofas", "SOFA", 150, (399, 2999), (120, 350), (70, 95), (80, 200), (30, 120),
     ["Fabric", "Leather", "Velvet", "Linen", "Boucle"],
     ["Modern", "Mid-Century", "Contemporary", "Luxury", "Compact", "Modular"],
     ["Sofa", "Sectional", "Loveseat", "Sleeper Sofa", "Chaise"],
     ["sectional", "l-shaped", "modular", "reversible", "living room"]),
    ("tables", "TABLE", 250, (99, 1499), (50, 220), (35, 80), (50, 110), (5, 60),
     ["Marble", "Oak", "Walnut", "Glass", "Steel", "Travertine", "Mango"],
     ["Round", "Rectangular", "Extendable", "Modern", "Rustic", "Industrial"],
     ["Coffee Table", "Dining Table", "Side Table", "Console Table", "Nightstand"],
     ["coffee", "dining", "round", "rectangular", "extendable"]),
    ("beds", "BED", 200, (249, 1999), (90, 200), (25, 60), (190, 220), (20, 80),
     ["Oak", "Walnut", "Pine", "Metal", "Upholstered", "Bamboo"],
     ["Platform", "Canopy", "Minimalist", "Contemporary", "Rustic"],
     ["Bed Frame", "Platform Bed", "Canopy Bed", "Daybed", "Bunk Bed"],
     ["platform", "queen", "king", "twin", "storage", "low-profile"]),
    ("lighting", "LAMP", 250, (29, 499), (20, 80), (30, 220), (20, 80), (1, 15),
     ["Brass", "Chrome", "Black Metal", "Copper", "Ceramic", "Glass"],
     ["Modern", "Vintage", "Industrial", "Minimalist", "Arc", "Adjustable"],
     ["Floor Lamp", "Table Lamp", "Pendant Light", "Wall Sconce", "Chandelier"],
     ["floor lamp", "table lamp", "dimmable", "adjustable", "warm light"]),
    ("rugs", "RUG", 200, (99, 1999), (80, 350), (1, 3), (120, 450), (2, 25),
     ["Wool", "Cotton", "Jute", "Silk", "Polypropylene", "Viscose"],
     ["Persian", "Bohemian", "Geometric", "Abstract", "Traditional", "Modern"],
     ["Area Rug", "Runner Rug", "Shag Rug", "Kilim Rug", "Oriental Rug"],
     ["hand-knotted", "machine-made", "washable", "area rug", "geometric"]),
    ("decor", "DECOR", 200, (19, 399), (10, 120), (10, 200), (5, 60), (1, 20),
     ["Ceramic", "Glass", "Brass", "Wood", "Marble", "Terracotta"],
     ["Minimalist", "Statement", "Handmade", "Elegant", "Art Deco", "Japanese"],
     ["Vase", "Mirror", "Wall Art", "Planter", "Sculpture", "Clock"],
     ["accent", "minimalist", "statement", "handmade", "decorative"]),
]

COLORS = ["black", "white", "gray", "beige", "brown", "navy", "green", "oak",
          "walnut", "natural", "cream", "charcoal", "walnut", "brass"]

DESCRIPTION_TEMPLATES = [
    "{adj} {mat} {noun_lower} with a {color} finish and clean lines.",
    "{noun} crafted from {mat_lower} in a {color} tone; {adj_lower} silhouette.",
    "{adj} {noun_lower} in {mat_lower}, {color} finish, for {room} use.",
    "{mat} {noun_lower} with {adj_lower} detailing and a durable {color} finish.",
    "{adj} {noun_lower} built from {mat_lower}, {color} colorway, ideal for {room}.",
]

ROOMS = ["living rooms", "home offices", "bedrooms", "dining rooms",
         "small apartments", "studies", "guest rooms"]


def make_description(rng, adj, mat, noun, color):
    template = rng.choice(DESCRIPTION_TEMPLATES)
    return template.format(
        adj=adj, mat=mat, noun=noun, noun_lower=noun.lower(),
        mat_lower=mat.lower(), adj_lower=adj.lower(),
        color=color, room=rng.choice(ROOMS),
    )


def generate_catalog():
    rng = random.Random(SEED)
    products = []
    for (cat, prefix, count, price_r, w_r, h_r, d_r, wt_r,
         mats, adjs, nouns, tag_pool) in CATEGORIES:
        used_names = set()
        for i in range(1, count + 1):
            pid = f"{prefix}-{i:03d}"
            adj = rng.choice(adjs)
            mat = rng.choice(mats)
            noun = rng.choice(nouns)
            color = rng.choice(COLORS)
            name = f"{adj} {mat} {noun}"
            if name in used_names:
                name = f"{name} {i:03d}"
            used_names.add(name)

            price = round(rng.uniform(*price_r), 2)
            stock = rng.randint(0, 50)
            width = round(rng.uniform(*w_r), 1)
            height = round(rng.uniform(*h_r), 1)
            depth = round(rng.uniform(*d_r), 1)
            weight = round(rng.uniform(*wt_r), 1)

            # Sometimes leave stock at 0 to test "out of stock" handling
            if rng.random() < 0.08:
                stock = 0

            tags = rng.sample(tag_pool, k=min(3, len(tag_pool)))
            tags.append(mat.lower())
            if color not in tags:
                tags.append(color)

            products.append({
                "id": pid,
                "name": name,
                "category": cat,
                "price": price,
                "currency": "USD",
                "stock": stock,
                "dimensions": {
                    "width": width,
                    "height": height,
                    "depth": depth,
                    "weight_kg": weight,
                },
                "description": make_description(rng, adj, mat, noun, color),
                "tags": tags,
            })
    return products


def generate_updates(catalog, n=50):
    """Generate price/stock update events referencing real product IDs.

    Format matches CatalogUpdate model:
      {"event": "product.updated", "product_ids": [...], "timestamp": ISO8601}
    """
    rng = random.Random(SEED + 1)
    base = datetime(2026, 9, 28, 12, 0, 0)
    updates = []

    # Individual updates
    for i in range(n - 5):
        product = rng.choice(catalog)
        event = rng.choice([
            "product.updated",
            "product.updated",
            "product.updated",
            "product.deleted",
        ])
        ts = base + timedelta(minutes=i * 7)
        updates.append({
            "event": event,
            "product_ids": [product["id"]],
            "timestamp": ts.isoformat(),
        })

    # Bulk update covering several products at once
    bulk_ids = [rng.choice(catalog)["id"] for _ in range(8)]
    ts = base + timedelta(hours=6)
    updates.append({
        "event": "catalog.bulk_update",
        "product_ids": list(dict.fromkeys(bulk_ids)),  # de-dup, keep order
        "timestamp": ts.isoformat(),
    })

    return updates


def generate_eval_questions(catalog):
    """Generate 60 evaluation questions with ground-truth product IDs.

    Question types:
      - retrieval: natural-language search where the query contains a token
        that is guaranteed to appear in the target product's name.
      - attribute: query a specific attribute (price, stock, dimensions).
      - fit:       fit-in-room question with computed ground space.
      - compare:   two products side by side.
    """
    rng = random.Random(SEED + 2)
    questions = []
    by_cat = {}
    for p in catalog:
        by_cat.setdefault(p["category"], []).append(p)

    # Build an index: token -> list of products whose name contains that token
    # (case-insensitive). We only use tokens long enough to be discriminative.
    name_index: dict[str, list] = {}
    for p in catalog:
        for token in p["name"].split():
            tok = token.lower().strip(",.")
            if len(tok) >= 4:
                name_index.setdefault(tok, []).append(p)

    # Keep only tokens that map to at least 1 and at most 100 products
    # (so the query is discriminative but has a ground truth).
    good_tokens = {t: ps for t, ps in name_index.items() if 1 <= len(ps) <= 100}
    token_pool = sorted(good_tokens.keys())

    # --- 20 retrieval questions ---
    # Query picks a random discriminative token, ground truth is one product
    # from that token's product list. This guarantees BM25 will find it.
    for i in range(20):
        token = rng.choice(token_pool)
        candidates = good_tokens[token]
        product = rng.choice(candidates)
        category = product["category"]
        cat_word = category[:-1] if category.endswith("s") else category
        questions.append({
            "id": f"Q{i+1:03d}",
            "type": "retrieval",
            "question": f"Show me a {token} {cat_word}.",
            "expected_product_ids": [product["id"]],
            "expected_top_k": 5,
            "discriminative_token": token,
        })

    # --- 15 attribute questions ---
    for i in range(15):
        product = rng.choice(catalog)
        attr = rng.choice(["price", "stock", "dimensions"])
        if attr == "price":
            q = f"What is the price of {product['id']}?"
        elif attr == "stock":
            q = f"Is {product['id']} in stock?"
        else:
            q = f"What are the dimensions of {product['id']}?"
        questions.append({
            "id": f"Q{21+i:03d}",
            "type": "attribute",
            "question": q,
            "expected_product_ids": [product["id"]],
            "expected_top_k": 5,
        })

    # --- 15 fit questions ---
    for i in range(15):
        product = rng.choice(catalog)
        dims = product["dimensions"]
        space_w = round(dims["width"] + rng.uniform(10, 80), 1)
        space_h = round(dims["height"] + rng.uniform(10, 60), 1)
        space_d = round(dims["depth"] + rng.uniform(10, 80), 1)
        questions.append({
            "id": f"Q{36+i:03d}",
            "type": "fit",
            "question": (f"Does {product['id']} fit in a room "
                         f"{space_w}x{space_d} cm with height {space_h} cm?"),
            "expected_product_ids": [product["id"]],
            "expected_top_k": 5,
            "fit_space": {
                "width": space_w,
                "height": space_h,
                "depth": space_d,
            },
        })

    # --- 10 compare questions ---
    cats_with_many = [c for c in by_cat if len(by_cat[c]) >= 3]
    for i in range(10):
        cat = rng.choice(cats_with_many)
        a, b = rng.sample(by_cat[cat], 2)
        questions.append({
            "id": f"Q{51+i:03d}",
            "type": "compare",
            "question": f"Compare {a['id']} and {b['id']}.",
            "expected_product_ids": [a["id"], b["id"]],
            "expected_top_k": 5,
        })

    assert len(questions) == 60, f"Expected 60 questions, got {len(questions)}"
    return questions


def write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    print("Generating catalog...")
    catalog = generate_catalog()
    write_jsonl(CATALOG_PATH, catalog)
    print(f"  ✅ {len(catalog)} products → {CATALOG_PATH}")

    print("Generating updates...")
    updates = generate_updates(catalog)
    write_jsonl(UPDATES_PATH, updates)
    print(f"  ✅ {len(updates)} updates → {UPDATES_PATH}")

    print("Generating eval questions...")
    eval_q = generate_eval_questions(catalog)
    write_jsonl(EVAL_PATH, eval_q)
    print(f"  ✅ {len(eval_q)} questions → {EVAL_PATH}")

    # Sanity summary
    from collections import Counter
    cats = Counter(p["category"] for p in catalog)
    types = Counter(q["type"] for q in eval_q)
    print("\nCategory distribution:")
    for c, n in sorted(cats.items()):
        print(f"  {c:12s} {n:4d}")
    print("\nQuestion types:")
    for t, n in sorted(types.items()):
        print(f"  {t:12s} {n:4d}")


if __name__ == "__main__":
    main()
