"""CivitAI prompt search and import tool for ComfyUI."""
import json
import os
import urllib.request
import urllib.parse
import urllib.error

CIVITAI_API = "https://civitai.com/api/v1"
PROMPT_DB = os.path.join(os.path.dirname(__file__), "prompts", "civitai_prompts.json")


def search_images(query, limit=20, nsfw=False, sort="Most Reactions", period="AllTime"):
    """Search CivitAI images and extract prompts."""
    params = urllib.parse.urlencode({
        "query": query,
        "limit": limit,
        "nsfw": str(nsfw).lower(),
        "sort": sort,
        "period": period,
    })
    url = f"{CIVITAI_API}/images?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ComfyUI-StyleForge/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data.get("items", [])
    except Exception as e:
        print(f"CivitAI search error: {e}")
        return []


def extract_prompts(items):
    """Extract prompts and metadata from CivitAI image items."""
    results = []
    for item in items:
        meta = item.get("meta", {})
        prompt = meta.get("prompt", "")
        negative = meta.get("negativePrompt", "")
        if not prompt:
            continue
        results.append({
            "positive": prompt,
            "negative": negative,
            "model": item.get("model", {}).get("name", "Unknown"),
            "base_model": item.get("model", {}).get("type", "Unknown"),
            "url": item.get("url", ""),
            "stats": {
                "reactions": item.get("stats", {}).get("reactionCount", 0),
                "comments": item.get("stats", {}).get("commentCount", 0),
                "cry_count": item.get("stats", {}).get("cryCount", 0),
            },
            "width": item.get("width", 512),
            "height": item.get("height", 512),
            "created_at": item.get("createdAt", ""),
        })
    return results


def search_prompts(query, limit=20):
    """Search for prompts and return formatted results."""
    items = search_images(query, limit=limit)
    prompts = extract_prompts(items)
    return prompts


def format_for_comfyui(prompts, index=0):
    """Format a CivitAI prompt result for use in ComfyUI."""
    if index >= len(prompts):
        return "", ""
    p = prompts[index]
    pos = p["positive"]
    neg = p["negative"]
    print(f"Model: {p['model']} ({p['base_model']})")
    print(f"Size: {p['width']}x{p['height']}  |  Reactions: {p['stats']['reactions']}")
    print(f"URL: {p['url']}")
    return pos, neg


def save_prompts(prompts, filename="search_results"):
    """Save search results to prompts directory."""
    os.makedirs(os.path.dirname(PROMPT_DB), exist_ok=True)
    filepath = os.path.join(os.path.dirname(PROMPT_DB), f"{filename}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(prompts)} prompts to {filepath}")
    return filepath


# Pre-cached top prompts for instant use without network
BUILTIN_CIVITAI_PROMPTS = [
    {
        "source": "CivitAI Top (Photorealistic)",
        "positive": "masterpiece, best quality, photorealistic, 1girl, solo, long hair, looking at viewer, smile, white shirt, sitting, detailed eyes, beautiful lighting, depth of field, bokeh, raw photo, skin texture, 8k, sharp focus, cinematic lighting",
        "negative": "(worst quality, low quality:1.4), monochrome, zombie, interlocked fingers, comice, jpeg artifacts, blurry",
    },
    {
        "source": "CivitAI Top (Anime)",
        "positive": "masterpiece, best quality, newest, absurdres, highres, 1girl, intricate details, beautiful detailed eyes, expressive, dynamic angle, vibrant colors, soft shading, studio trigger art style, trending on pixiv",
        "negative": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry",
    },
    {
        "source": "CivitAI Top (Cinematic)",
        "positive": "cinematic film still, shallow depth of field, vignette, highly detailed, high budget, bokeh, cinemascope, moody, epic, gorgeous, film grain, grainy, ray tracing, octane render, unreal engine 5",
        "negative": "anime, cartoon, graphic, text, painting, crayon, graphite, abstract, glitch, deformed, mutated, ugly, disfigured",
    },
    {
        "source": "CivitAI Top (Fantasy)",
        "positive": "epic fantasy scene, dramatic lighting, highly detailed, intricate, sharp focus, fantasy art, trending on artstation, by greg rutkowski and magali villeneuve, oil painting, masterpiece",
        "negative": "blurry, low quality, modern, photo, realistic, ugly",
    },
    {
        "source": "CivitAI Top (Cyberpunk)",
        "positive": "cyberpunk, neon lights, rain, reflections, blade runner atmosphere, high tech, low life, luminous, bioluminescent, advanced technology, rim lighting, city street, night, wet pavement, hyperrealistic, octane render, trending on cgsociety",
        "negative": "daytime, natural light, rural, ancient, medieval, cartoon, anime",
    },
    {
        "source": "CivitAI Top (Portrait)",
        "positive": "portrait of a beautiful woman, elegant, detailed face, beautiful eyes, soft skin, natural makeup, fashion photography, studio lighting, canon eos r5, 85mm prime lens, f1.4, glamour shot, vogue",
        "negative": "ugly, deformed, blurry, bad anatomy, extra limbs, missing arms, nsfw",
    },
    {
        "source": "CivitAI Top (Product)",
        "positive": "product photography, minimal white background, studio lighting, sharp details, professional, commercial photography, product shot, glossy, reflective surface, 3-point lighting, canon, 100mm macro",
        "negative": "blurry, dark, cluttered, messy, low quality, reflection of photographer, watermark",
    },
    {
        "source": "CivitAI Top (Food)",
        "positive": "delicious food photography, steam rising, warm lighting, shallow depth of field, garnished, chef presentation, gourmet, molecular gastronomy, dark moody background, restaurant quality, plating, macro shot",
        "negative": "messy, unappetizing, stale, cold, blurry, flat lighting, fast food",
    },
]


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"Searching CivitAI for: {query}\n")
        results = search_prompts(query, limit=10)
        if results:
            print(f"Found {len(results)} results:\n")
            for i, r in enumerate(results):
                stats = r["stats"]
                print(f"[{i}] {r['model']} ({r['base_model']}) | {r['width']}x{r['height']} | {stats['reactions']} reactions")
                print(f"    Positive: {r['positive'][:150]}...")
                print(f"    Negative: {r['negative'][:100]}...")
                print()
            save_prompts(results, f"civitai_{query[:30].replace(' ', '_')}")
        else:
            print("No results found. Using built-in prompts:")
            for p in BUILTIN_CIVITAI_PROMPTS:
                print(f"\n[{p['source']}]")
                print(f"  +: {p['positive'][:120]}...")
    else:
        print("Usage: python civitai_search.py <search query>")
        print("Example: python civitai_search.py realistic portrait")
        print("\n--- Built-in prompts available offline ---")
        for p in BUILTIN_CIVITAI_PROMPTS:
            print(f"  - {p['source']}")
