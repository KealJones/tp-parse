"""interstellarninja/hermes_reasoning_tool_use (Apache-2.0), converted to Squiggle's world.

What the corpus has: 51k conversations from When2Call, ToolAce, Glaive, xLAM and Nous-Hermes. Their tools are made-up
APIs (tmall_search_by_keyword, extract…) and their tool *results* are invented ("ABC Corporation", example.com). Keal's
rule is real data only, never invented facts, and Squiggle has its own fixed tools, so the conversations can't be
copied over as they are. What carries over honestly:

  hermes_compute  requests the reference model answered with a pure computation (word_frequency, is_prime,
                  calculate_tip…) with every input given. In Squiggle that is run_js. The teacher solves the request
                  in Squiggle's harness with the real sandbox, and the episode is kept only if run_js ran and the
                  reply carries what it computed (the computation is real, nothing is invented).
  hermes_need     requests the reference model refused to act on because an input was missing ("Reverse the given
                  sentence.", "Fetch options data for the ETF."). In Squiggle that is need. Kept only if the teacher
                  also calls need before doing anything else.

So Hermes supplies requests and the call-vs-ask label; the Squiggle-shaped thinking and calls come from the teacher
inside the real harness. Everything else in the corpus (invented API results, relevance refusals that would teach
"I have no tools" when Squiggle can search the web) is left out.
"""
import json, random, re
import families as F
from sqrun import Episode

PURE = re.compile(r"^(?:calculate_(?:tip|discount|bmi|age|area|average|percentage|loan_payment|mortgage_payment|mortgage|interest|simple_interest|"
                  r"compound_interest|gpa|factorial|fibonacci|median|mean|sum|distance_between_points|triangle_area|circle_area|grade|"
                  r"total|profit|savings|investment_return|cagr|standard_deviation|power|square_root|hypotenuse|volume|perimeter|speed|"
                  r"fuel_efficiency|calories|percent|quadratic|sales_tax|tax_amount|electricity_bill|net_salary|bmi_category)|"
                  r"word_frequency|reverse_words|reverse_string|is_palindrome|is_anagram|is_anagram_phrase|is_prime|is_power_of_two|"
                  r"is_perfect_square|is_power|is_sum_of_cubes|is_armstrong_number|is_valid_parentheses|is_rotation|is_subset|"
                  r"fibonacci|fibonacci_numbers|factorial|find_duplicate_number|find_missing_number|find_max_subarray_sum|"
                  r"find_majority_element|find_first_non_repeating_char|find_longest_word|find_missing_ranges|find_peak_element|"
                  r"find_kth_smallest_number|find_n_largest_numbers|find_pairs_with_sum|find_minimum_rotated_sorted_array|"
                  r"merge_dictionaries|merge_sorted_lists|flatten_list|remove_duplicates|count_vowels|count_occurrences|"
                  r"binary_addition|binary_search|binary_to_decimal|decimal_to_binary|gcd|greatest_common_divisor|lcm|"
                  r"least_common_multiple|average|median|std_deviation|calculate_std_deviation|matrix_multiply|dot_product|"
                  r"sort_numbers|longest_common_prefix|generate_password|generate_random_string|celsius_to_fahrenheit|"
                  r"fahrenheit_to_celsius|convert_temperature|compound_interest|future_investment_value|monthly_mortgage_payment|"
                  r"triangle_area|circle_area|polygon_area_shoelace|euclidean_distance|cosine_similarity|potential_energy|"
                  r"density|wire_resistance|permutation_count|probability_of_consecutive_rolls|dice_roll_probability|"
                  r"expand_around_center|integrate|trapezoidal_integration|least_common_multiple|prime_factorization|"
                  r"sum_of_digits|count_bits|split_list|chunk_list|get_range|format_range|word_count|character_count|"
                  r"convert_units|convert_length|convert_weight)$")
RANDOMISH = re.compile(r"random|password|generate", re.I)
NEED_REPLY = re.compile(r"\b(provide|specify|share|tell me|let me know|give me)\b", re.I)
REFUSE = re.compile(r"don't have|do not have|not able|unable|no tool|isn't available|not available|cannot|can't|none of the|available tools|"
                    r"do not include|don't include|doesn't include|does not include|don't support|doesn't support|do not support|not suitable|"
                    r"do not seem|don't seem|not designed|outside", re.I)
USERSIDE = re.compile(r"\b(sentence|text|string|list|numbers?|values?|amount|date|file|url|link|word|phrase|array|dimensions?|"
                      r"length|width|radius|price|income|weight|height|birth|age|temperature|location|address|city|name|email|"
                      r"principal|rate|loan|data|details|symbol|ticker|id)\b", re.I)


def _names(tool_json):
    try:
        tools = json.loads(tool_json) if tool_json else []
    except Exception:
        return []
    return [(x.get("name") or (x.get("function") or {}).get("name") or "") for x in tools if isinstance(x, dict)] if isinstance(tools, list) else []


def select(rows, seed=0):
    """-> (compute, need): lists of {"request", "source", "tools"}."""
    compute, need = [], []
    for r in rows:
        conv = r["conversations"]
        human = [m for m in conv if m["from"] == "human"]
        gpt = [m for m in conv if m["from"] == "gpt"]
        if not human or not gpt or r["scenario_category"] not in ("single", "relevance"):
            continue
        req = human[0]["value"].strip()
        if len(req) > 300 or "<" in req or "```" in req:
            continue
        first = gpt[0]["value"]
        calls = re.findall(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", first, re.S)
        if calls:
            try:
                names = [json.loads(c).get("name", "") for c in calls]
            except Exception:
                continue
            if names and all(PURE.match(n) for n in names) and not any(RANDOMISH.search(n) for n in names) and re.search(r"\d|'[^']+'|\"[^\"]+\"|\[", req):
                compute.append({"request": req, "source": r["source"], "tools": names})
        elif r["source"] == "Nvidia-When2Call" and len(req) <= 140:
            m = re.match(r"\s*<think>(.*?)</think>\s*(.*)", first, re.S)
            if not m:
                continue
            rep = m.group(2)
            if "?" in rep and NEED_REPLY.search(rep) and not REFUSE.search(rep) and USERSIDE.search(rep):
                need.append({"request": req, "source": r["source"], "asked": rep.strip()[:300]})
    rng = random.Random(seed)
    for xs in (compute, need):
        rng.shuffle(xs)
        seen, keep = set(), []
        for x in xs:
            k = F.norm(x["request"])
            if k not in seen:
                seen.add(k)
                keep.append(x)
        xs[:] = keep
    return compute, need


def make_compute(rng, row, i):
    text, m = F.maybe_messy(rng, row["request"], 0.35)
    return Episode(id=f"hermes_compute-{i}", family="hermes_compute", first=text, gold={"tools": row["tools"]}, meta={"messy": m, "source": row["source"]})


def make_need(rng, row, i):
    return Episode(id=f"hermes_need-{i}", family="hermes_need", first=row["request"], gold={"asked": row["asked"]}, meta={"messy": False, "source": row["source"]})


def _values(blob):
    """Short values a run_js result produced (numbers, short strings), from 'Result of run_js:' JSON."""
    try:
        d = json.loads(blob)
    except Exception:
        return []
    out = []
    for k in ("result", "stdout"):
        v = d.get(k)
        if not v:
            continue
        for line in str(v).splitlines()[:30]:
            out += re.findall(r"-?\d+(?:\.\d+)?", line)
            s = line.strip().strip('"')
            if 0 < len(s) <= 40 and not re.fullmatch(r"[\[\]{}(),\s]*", s):
                out.append(s)
    return out


def check(res):
    reasons = F.base_check(res)
    segs = F.turn_calls(res)
    seg = segs[0] if segs else []
    names = F.names(seg)
    rep = F.reply_of(res, 0)
    if res["family"] == "hermes_need":
        asked = F.asked_user(res, 0)
        acted = [n for n in names if n not in ("find", "need")]
        if not asked:
            reasons.append("didn't ask for the missing input")
        if acted:
            reasons.append("acted before asking: " + ", ".join(acted))
        ok = bool(asked) and not acted
        return {"ok": ok, "strict": ok and not reasons, "reasons": reasons}
    ran = "run_js" in names
    vals = [v for b in F.results_of(seg, "run_js") for v in _values(b)]
    errs = [b for b in F.results_of(seg, "run_js") if '"error"' in b]
    nums = {F.num(t) for t in F.toks(rep) if F.num(t) is not None}
    carried = any((F.num(v) is not None and F.num(v) in nums) or (F.num(v) is None and F.norm(v) and F.norm(v) in F.norm(rep)) for v in vals)
    if not ran:
        reasons.append("didn't compute it")
    if ran and not carried:
        reasons.append("reply doesn't carry the computed value")
    if errs and not vals:
        reasons.append("run_js failed")
    ok = ran and carried
    return {"ok": ok, "strict": ok and not reasons, "reasons": reasons}
