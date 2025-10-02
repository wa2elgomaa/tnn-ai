import re
import copy

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u06D6-\u06ED]")
_CLEANR = re.compile('<.*?>') 


# Basic Arabic normalization (optional but helpful in bilingual newsrooms)
def normalize_arabic(text: str) -> str:
    if not text:
        return text
    t = text
    t = _ARABIC_DIACRITICS.sub("", t)
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    t = t.replace("ة", "ه")
    t = t.replace("ى", "ي")
    t = t.replace("ؤ", "و").replace("ئ", "ي")
    return t

def clean_html(text: str) -> str:
    if not text:
        return text
    return _CLEANR.sub("", text)

# Light keyword overlap heuristic for "reasons"
def keyword_overlap_reason(text: str, tag_text: str, top_n: int = 5) -> str:
    import re
    tok = lambda s: [w for w in re.findall(r"[\p{L}\p{Nd}]{3,}", s, flags=re.UNICODE)]
    try:
        from regex import findall  # optional: if regex module installed
        tok = lambda s: [w for w in findall(r"[\p{L}\p{Nd}]{3,}", s)]
    except Exception:
        pass
    a = set(w.lower() for w in tok(text))
    b = set(w.lower() for w in tok(tag_text))
    inter = list(a.intersection(b))[:top_n]
    if inter:
        return f"Shared terms: {', '.join(inter)}"
    return "Semantic similarity to tag description"



def deep_merge(a, b, unique_key="slug"):
    """
    Recursively merge two JSON-like dicts/lists.
    - Dicts: merge keys
    - Lists: merge and deduplicate by `unique_key` if dicts, else set()
    - Scalars: b overwrites a
    """
    if isinstance(a, dict) and isinstance(b, dict):
        merged = copy.deepcopy(a)
        for k, v in b.items():
            if k in merged:
                merged[k] = deep_merge(merged[k], v, unique_key)
            else:
                merged[k] = copy.deepcopy(v)
        return merged

    elif isinstance(a, list) and isinstance(b, list):
        # If list of dicts -> deduplicate by `unique_key`
        if all(isinstance(x, dict) for x in a+b):
            seen = {}
            for item in a + b:
                key = item.get(unique_key) if isinstance(item, dict) else None
                if key:
                    seen[key] = deep_merge(seen.get(key, {}), item, unique_key)
                else:
                    seen[id(item)] = item  # fallback for non-keyed dict
            return list(seen.values())
        else:
            # Fallback for scalars: deduplicate
            return list(dict.fromkeys(a + b))

    else:
        # Scalars: prefer `b`
        return copy.deepcopy(b)


