
Score · PY
#!/usr/bin/env python3
"""Scores every collected response and writes a report for each person.
 
Run it locally after downloading the repo, or let the GitHub Action run it
automatically whenever a new response arrives:
 
    python3 score.py
 
Produces:
    scores.csv          one row per person, every scale score, for your own analysis
    reports/index.html  list of everyone, newest first
    reports/<id>.html   one readable report per person, printable to PDF
 
Only the standard library is used, so it runs anywhere Python runs with nothing
to install.
 
A note on what this does and does not claim. Scoring is arithmetic and is exact.
The written interpretation is a set of rules applied to those numbers: it
describes tendencies people who answer this way tend to report, hedged
accordingly. It is not a diagnosis, not a measure of ability, and not a
selection instrument. Both questionnaires are self-report snapshots taken once.
"""
 
import csv
import html
import json
import pathlib
import statistics
from collections import Counter
from datetime import datetime, timezone
 
HERE = pathlib.Path(__file__).resolve().parent
RESPONSES = HERE / "responses"
REPORTS = HERE / "reports"
 
# ─────────────────────────────────────────────────────────── scoring keys
# Section A: (scale, keyed sign). Section B: (scale, keyed sign).
# +1 scores the answer as given, -1 scores 6 - answer.
A_KEY = {
    1: ("E", 1), 2: ("A", -1), 3: ("C", 1), 4: ("S", -1), 5: ("O", 1),
    6: ("E", -1), 7: ("A", 1), 8: ("C", -1), 9: ("S", 1), 10: ("O", -1),
    11: ("E", 1), 12: ("A", -1), 13: ("C", 1), 14: ("S", -1), 15: ("O", 1),
    16: ("E", -1), 17: ("A", 1), 18: ("C", -1), 19: ("S", 1), 20: ("O", -1),
    21: ("E", 1), 22: ("A", -1), 23: ("C", 1), 24: ("S", -1), 25: ("O", 1),
    26: ("E", -1), 27: ("A", 1), 28: ("C", -1), 29: ("S", -1), 30: ("O", -1),
    31: ("E", 1), 32: ("A", -1), 33: ("C", 1), 34: ("S", -1), 35: ("O", 1),
    36: ("E", -1), 37: ("A", 1), 38: ("C", -1), 39: ("S", -1), 40: ("O", 1),
    41: ("E", 1), 42: ("A", 1), 43: ("C", 1), 44: ("S", -1), 45: ("O", 1),
    46: ("E", -1), 47: ("A", 1), 48: ("C", 1), 49: ("S", -1), 50: ("O", 1),
}
B_KEY = {
    1: ("IE", 1), 2: ("SN", 1), 3: ("FT", -1), 4: ("JP", 1), 5: ("IE", -1),
    6: ("SN", -1), 7: ("FT", 1), 8: ("JP", -1), 9: ("IE", 1), 10: ("SN", 1),
    11: ("FT", -1), 12: ("JP", 1), 13: ("IE", -1), 14: ("SN", -1), 15: ("FT", 1),
    16: ("JP", -1), 17: ("IE", 1), 18: ("SN", 1), 19: ("FT", -1), 20: ("JP", 1),
    21: ("IE", -1), 22: ("SN", -1), 23: ("FT", 1), 24: ("JP", -1), 25: ("IE", 1),
    26: ("SN", 1), 27: ("FT", -1), 28: ("JP", 1), 29: ("IE", -1), 30: ("SN", -1),
    31: ("FT", 1), 32: ("JP", -1), 33: ("IE", 1), 34: ("SN", 1), 35: ("FT", -1),
    36: ("JP", 1), 37: ("IE", -1), 38: ("SN", 1), 39: ("FT", 1), 40: ("JP", 1),
    41: ("IE", 1), 42: ("SN", 1), 43: ("FT", -1), 44: ("JP", 1), 45: ("IE", -1),
    46: ("SN", 1), 47: ("FT", 1), 48: ("JP", 1),
}
 
TRAITS = {
    "E": ("Extraversion", "outward energy and sociability", "#2F6F6B"),
    "A": ("Agreeableness", "warmth and regard for others", "#7A4A63"),
    "C": ("Conscientiousness", "order, planning and follow-through", "#3E5C76"),
    "S": ("Emotional stability", "evenness under pressure", "#5C7C4F"),
    "O": ("Openness", "appetite for ideas and novelty", "#A67C1E"),
}
# (low name, high name, low letter, high letter, note, colour)
# The letters are stated explicitly because Intuition's letter is N, not I.
DICHS = {
    "IE": ("Introversion", "Extraversion", "I", "E", "where attention and energy go", "#2F6F6B"),
    "SN": ("Sensing", "Intuition", "S", "N", "the kind of information trusted", "#A67C1E"),
    "FT": ("Feeling", "Thinking", "F", "T", "how decisions get made", "#7A4A63"),
    "JP": ("Judging", "Perceiving", "J", "P", "how the outside world is handled", "#3E5C76"),
}
MID = 36
 
# Reference percentiles for section B, pooled from the two published comparison
# datasets (2,923 complete response sets). Index 0 is a score of 12.
REF = {
    "n": 2923,
    "IE": dict(mean=29.9, alpha=.82, pct=[0.2,0.7,1.4,2.2,3.4,5.4,7.9,10.7,14.3,17.7,21.0,24.9,28.9,33.0,37.3,41.7,45.8,50.0,54.2,58.0,61.6,64.8,67.7,70.7,74.1,77.2,80.1,82.9,85.5,87.9,90.2,92.1,93.7,94.9,95.7,96.6,97.4,98.0,98.5,98.8,99.1,99.4,99.7,99.8,99.8,99.9,100,100,100]),
    "SN": dict(mean=38.3, alpha=.55, pct=[0,0,0,0,0,0,0.1,0.1,0.2,0.3,0.4,0.6,1.0,1.5,2.3,3.3,4.5,6.3,8.8,11.8,15.4,19.8,25.0,30.6,36.6,42.9,49.2,55.8,62.6,68.5,73.5,77.9,81.9,85.5,88.6,91.1,93.3,95.0,96.4,97.5,98.4,99.1,99.4,99.7,99.8,99.9,99.9,100,100]),
    "FT": dict(mean=35.8, alpha=.82, pct=[0.1,0.2,0.2,0.3,0.6,1.1,1.8,2.6,3.5,4.8,6.4,8.1,9.9,12.1,14.4,17.4,21.0,24.3,27.6,31.3,35.5,39.8,44.0,48.6,53.2,57.6,61.4,64.9,68.3,71.3,74.3,77.1,79.8,82.4,85.2,87.8,90.0,91.9,93.3,94.5,95.8,96.9,97.6,98.2,98.8,99.2,99.6,99.8,100]),
    "JP": dict(mean=35.2, alpha=.83, pct=[0.1,0.2,0.4,0.5,0.9,1.5,2.3,3.1,4.2,5.7,7.3,9.3,11.5,14.0,16.8,20.0,23.2,26.6,30.2,33.9,37.6,41.5,45.6,49.6,53.4,57.1,61.0,64.8,68.6,72.1,75.4,78.8,82.2,85.4,88.0,90.1,92.1,93.7,95.0,96.2,97.1,97.7,98.4,99.0,99.4,99.7,99.9,99.9,100]),
}
 
 
# ─────────────────────────────────────────────────────────── scoring
 
def score_response(rec):
    """Raw answers to scale scores. Blank answers count as the neutral middle."""
    ans = rec.get("answers", {})
    traits = {k: 0 for k in TRAITS}
    dichs = {k: 0 for k in DICHS}
    a_given = b_given = 0
    for n, (scale, sign) in A_KEY.items():
        v = ans.get(f"a{n}")
        if v is None:
            v = 3
        else:
            a_given += 1
        traits[scale] += v if sign == 1 else 6 - v
    for n, (scale, sign) in B_KEY.items():
        v = ans.get(f"b{n}")
        if v is None:
            v = 3
        else:
            b_given += 1
        dichs[scale] += v if sign == 1 else 6 - v
    letters = "".join(
        "-" if dichs[k] == MID else (DICHS[k][3] if dichs[k] > MID else DICHS[k][2])
        for k in ("IE", "SN", "FT", "JP"))
    return dict(traits=traits, dichs=dichs, type=letters,
                answered_a=a_given, answered_b=b_given)
 
 
def trait_band(v):
    """Five bands across the 10-50 range of a trait scale."""
    if v >= 42: return "very high"
    if v >= 35: return "high"
    if v >= 26: return "moderate"
    if v >= 19: return "low"
    return "very low"
 
 
def lean(distance):
    d = abs(distance)
    if d <= 2: return "borderline"
    if d <= 6: return "slight"
    if d <= 14: return "clear"
    return "strong"
 
 
def quality_flags(rec, scored):
    """Signals that a set of answers may not be worth interpreting."""
    flags = []
    ans = rec.get("answers", {})
    vals = [v for v in ans.values() if isinstance(v, int)]
    n = len(vals)
    secs = (rec.get("elapsed_ms") or 0) / 1000
    if n and secs and secs < n * 1.2:
        flags.append(("rushed", f"finished in {int(secs)} seconds, under 1.2 seconds per item"))
    if n > 10 and statistics.pstdev(vals) < 0.5:
        flags.append(("flat", "almost every answer was the same value"))
    if n and sum(1 for v in vals if v == 3) / n > 0.6:
        flags.append(("noncommittal", "over 60% of answers sat on the neutral middle"))
    run = best = 1
    for i in range(1, len(vals)):
        run = run + 1 if vals[i] == vals[i - 1] else 1
        best = max(best, run)
    if best >= 12:
        flags.append(("repetitive", f"{best} identical answers in a row"))
    missing = (50 - scored["answered_a"]) + (48 - scored["answered_b"])
    if missing:
        flags.append(("incomplete", f"{missing} items left blank and scored as neutral"))
    return flags
 
 
# ─────────────────────────────────────────────────────────── written interpretation
 
TRAIT_TEXT = {
    "E": {
        "very high": "Strongly outward-facing. Seeks people out, talks early and often, and gains energy from busy environments rather than spending it.",
        "high": "Sociable and forthcoming. Comfortable speaking up, generally happier working with others than alone.",
        "moderate": "Sociable in some settings and content alone in others. Neither the first nor the last to speak in a group.",
        "low": "Reserved. Prefers smaller groups and fewer, closer relationships, and recovers energy in quiet.",
        "very low": "Strongly inward-facing. Finds sustained social contact draining and does their best thinking alone.",
    },
    "A": {
        "very high": "Highly accommodating. Assumes good faith, avoids conflict, and puts others' needs high on the list, sometimes above their own.",
        "high": "Warm and cooperative. Notices how people are feeling and makes room for them.",
        "moderate": "Warm with people they trust, more measured with others. Cooperative without being deferential.",
        "low": "Direct and hard to sway. More interested in the substance of a problem than in smoothing how it lands.",
        "very low": "Blunt and sceptical of others' motives. Comfortable in open disagreement and unlikely to soften a message.",
    },
    "C": {
        "very high": "Highly organised and driven to finish. Plans in detail, keeps commitments, and holds a demanding standard for their own work.",
        "high": "Reliable and orderly. Plans ahead, follows through, and is comfortable with structure.",
        "moderate": "Organised where it counts, relaxed elsewhere. Meets deadlines without building elaborate systems.",
        "low": "Works in bursts. Keeps plans loose, decides late, and is more comfortable improvising than scheduling.",
        "very low": "Strongly unstructured. Finds routine and detailed planning genuinely difficult to sustain.",
    },
    "S": {
        "very high": "Very even-tempered. Setbacks pass quickly and pressure rarely shows outwardly.",
        "high": "Generally calm. Stress registers but does not linger long or drive behaviour.",
        "moderate": "Ordinary sensitivity to stress. Mood tends to track what is happening around them.",
        "low": "Reactive. Feels things quickly and strongly, and worry tends to stay once it arrives.",
        "very low": "Highly reactive. Reports frequent worry and mood swings, and takes longer than most to settle after a setback.",
    },
    "O": {
        "very high": "Strongly drawn to ideas and abstraction. Prefers the novel and theoretical to the established and concrete.",
        "high": "Curious and imaginative. Enjoys new ideas and thinking about how things could be different.",
        "moderate": "Open to new ideas in measured doses while staying anchored in the practical.",
        "low": "Practical and concrete. Prefers the familiar, the proven, and what can be checked.",
        "very low": "Strongly concrete. Little patience for abstraction or theory; wants specifics and precedent.",
    },
}
 
DICH_TEXT = {
    "IE": ("Draws energy from solitude, thinks before speaking, and prefers depth over breadth in relationships.",
           "Draws energy from company, thinks by talking, and prefers a wide circle of contact."),
    "SN": ("Trusts what is observable and verifiable, works from detail and precedent.",
           "Trusts patterns and possibilities, works from meaning and what something could become."),
    "FT": ("Decides by weighing the human cost, values harmony, and takes the personal dimension seriously.",
           "Decides by logic and consistency, values clarity, and will accept friction to be correct."),
    "JP": ("Closes decisions early, plans ahead, prefers matters settled.",
           "Keeps options open, decides late, prefers room to adapt."),
}
 
 
# Four themes that always appear, each driven by the trait most relevant to it,
# with the matching preference used as a modifier. Written so that a profile
# sitting in the middle of everything still gets a real reading rather than a
# blank page — mid-range is a finding, not an absence of one.
THEMES = {
    "Working style": ("C", {
        "very high": "Plans in detail and finishes what is started. Likely to build structure where none exists, and to feel real discomfort when work is left open or standards slip. The risk is over-preparing, and treating other people's looser approach as carelessness.",
        "high": "Organised and dependable. Sets out a plan, works to it, and delivers when promised. Handles routine and detail without needing to be chased.",
        "moderate": "Structured where it matters and relaxed elsewhere. Meets commitments without elaborate systems, and adapts when plans change without much friction. This middle position is genuinely common and usually easy to work with.",
        "low": "Works in bursts, often close to the deadline, and prefers deciding as things unfold to committing early. Output can be strong while progress is hard to see from outside.",
        "very low": "Finds routine and detailed planning hard to sustain. Likely to need external structure — short deadlines, visible checkpoints — rather than more encouragement.",
    }),
    "With other people": ("E", {
        "very high": "Highly sociable. Seeks contact, thinks out loud, and is usually among the first to speak. Group settings are energising rather than costly. May unintentionally crowd out quieter people.",
        "high": "Comfortable and forthcoming with people. Contributes readily in discussion and builds contact easily.",
        "moderate": "Sociable when the setting suits and content alone otherwise. Neither dominates a room nor disappears in one.",
        "low": "Reserved. Prefers fewer, deeper relationships and smaller settings, and often forms a view without volunteering it. Asking directly tends to surface more than open-floor discussion.",
        "very low": "Strongly private. Sustained social contact is genuinely draining. Written exchange is likely to suit far better than meetings, and silence should not be read as disengagement.",
    }),
    "Under pressure": ("S", {
        "very high": "Very hard to rattle. Setbacks pass quickly and pressure rarely shows. Steadying for others, though strain may go unnoticed precisely because it does not surface.",
        "high": "Generally steady. Stress registers and then passes without dominating behaviour.",
        "moderate": "Ordinary sensitivity to pressure. Mood tracks circumstances; a bad week shows, a good one does too.",
        "low": "Feels pressure keenly and holds onto it. Worry tends to persist after the cause has passed. Ambiguity and unclear expectations are likely to cost more here than for most.",
        "very low": "Highly reactive to stress, with frequent shifts in mood and a long recovery from setbacks. Predictability and clear expectations matter more than usual.",
    }),
    "Thinking and information": ("O", {
        "very high": "Strongly drawn to abstraction, theory and the untried. Generates ideas readily and tires of established methods quickly. Wants to know why before accepting what.",
        "high": "Curious and imaginative. Comfortable with ambiguity and interested in how things could be arranged differently.",
        "moderate": "Interested in new ideas without chasing novelty. Weighs a new approach on its merits and stays anchored in the practical.",
        "low": "Practical and concrete. Prefers proven methods, specifics and precedent, and wants evidence before changing an approach that works.",
        "very low": "Strongly concrete. Little appetite for theory or speculation. Most effective with defined problems, clear methods and observable results.",
    }),
}
 
DICH_MODIFIER = {
    "Working style": ("JP", "Judging", "Perceiving",
        "The preference measure agrees: settled plans over open options.",
        "The preference measure agrees: open options over settled plans."),
    "With other people": ("IE", "Introversion", "Extraversion",
        "The preference measure agrees on reserve.",
        "The preference measure agrees on outward energy."),
    "Thinking and information": ("SN", "Sensing", "Intuition",
        "The preference measure agrees, leaning to the concrete and verifiable.",
        "The preference measure agrees, leaning to patterns and possibilities."),
}
 
 
def theme_sections(t, d, band):
    """The four always-present readings, with agreement noted where it exists."""
    out = []
    for heading, (trait, texts) in THEMES.items():
        b = band(t[trait])
        text = texts[b]
        mod = DICH_MODIFIER.get(heading)
        if mod:
            key, _low, _high, low_txt, high_txt = mod
            dist = d[key] - MID
            if abs(dist) > 6:
                trait_high = b in ("high", "very high")
                # does the preference point the same way as the trait?
                same = ((heading == "Working style" and ((dist < 0) == trait_high))
                        or (heading == "With other people" and ((dist > 0) == trait_high))
                        or (heading == "Thinking and information" and ((dist > 0) == trait_high)))
                if same and b != "moderate":
                    text += " " + (low_txt if dist < 0 else high_txt)
        out.append((heading, text))
    return out
 
 
def standout(t, band):
    """Highest and lowest trait within this person's own profile."""
    order = sorted(TRAITS, key=lambda k: t[k])
    lowk, highk = order[0], order[-1]
    if t[highk] - t[lowk] < 6:
        return ("An even profile",
                "No trait stands out sharply against the others in this profile — the five scores sit within a few "
                "points of each other. That is a real result rather than a missing one: it suggests someone whose "
                "behaviour is shaped more by situation than by a dominant disposition, and it means no single "
                "section above should be weighted much more than the rest.")
    return ("Most and least characteristic",
            f"Within this profile, {TRAITS[highk][0].lower()} sits highest ({t[highk]}) and "
            f"{TRAITS[lowk][0].lower()} lowest ({t[lowk]}). Comparing someone against themselves like this is often "
            f"more useful than comparing them against other people: it points at which of the readings above is "
            f"likely to be most visible day to day, and which is least.")
 
 
# Combination rules. Each is (condition, heading, paragraph). Only the ones that
# fire appear in the report, so nobody gets a page of contradictions.
def combination_rules(t, d, band):
    hi = lambda k: band(t[k]) in ("high", "very high")
    lo = lambda k: band(t[k]) in ("low", "very low")
    n = lambda k: d[k] - MID
 
    rules = [
        (hi("C") and n("JP") < -6, "Working style",
         "Both measures point the same way on structure. Expect plans made early, work finished ahead of deadline, "
         "and visible discomfort when scope changes late. Best used where reliability matters more than improvisation; "
         "likely to find shifting priorities more costly than most."),
        (lo("C") and n("JP") > 6, "Working style",
         "Consistently unstructured across both measures. Work is likely to happen in concentrated bursts near a deadline "
         "rather than spread evenly. This is not an absence of effort, but it does mean progress is hard to observe from "
         "outside until late. Milestones help more than reminders."),
        (hi("C") and hi("S"), "Under load",
         "An unusually durable combination: organised and slow to rattle. Tends to absorb pressure others pass on, "
         "which is easy to rely on and easy to overuse. Worth checking in on directly, because strain is unlikely to show."),
        (lo("S") and hi("C"), "Under load",
         "Holds a high standard while feeling pressure keenly. Often produces careful, thorough work at real internal cost. "
         "Deadlines and ambiguity are likely to be more taxing here than the output suggests. Clear expectations reduce the load."),
        (lo("S") and lo("C"), "Under load",
         "Stress lands hard and structure is thin, a combination that tends to produce avoidance under pressure rather than "
         "acceleration. Breaking work into small, near-term commitments is likely to help more than encouragement."),
        (hi("E") and hi("A"), "With other people",
         "Sociable and accommodating. Likely to be the person keeping a group cohesive, and correspondingly reluctant to "
         "deliver bad news or hold an unpopular line."),
        (hi("E") and lo("A"), "With other people",
         "Forthcoming and direct at once. Will say the difficult thing in the room, which is valuable and occasionally costly. "
         "Impact on quieter colleagues is likely to be larger than intended."),
        (lo("E") and hi("A"), "With other people",
         "Warm but quiet. Often holds a considered view without volunteering it, so contributions can be missed in "
         "fast-moving discussions. Asking directly usually surfaces more than open-floor questions do."),
        (lo("E") and lo("A"), "With other people",
         "Reserved and unsentimental. Comfortable working independently and unlikely to spend energy on group harmony. "
         "Written communication is likely to suit them better than meetings."),
        (hi("O") and lo("C"), "Ideas and follow-through",
         "Strong appetite for ideas paired with light structure. Likely to generate more starts than finishes. "
         "Pairing with someone who closes things out tends to be more effective than asking for more discipline."),
        (hi("O") and hi("C"), "Ideas and follow-through",
         "Unusual and productive pairing: interested in new approaches and able to see them through. "
         "Suited to work that is genuinely novel but still has to ship."),
        (lo("O") and hi("C"), "Ideas and follow-through",
         "Practical and reliable, with a preference for proven methods. Strongest where consistency and accuracy matter; "
         "likely to want concrete evidence before adopting a new approach, which slows change and prevents mistakes in equal measure."),
        (hi("A") and n("FT") < -6, "Decision making",
         "Both measures agree that decisions are weighed by their effect on people. Expect reluctance to impose costs on "
         "others even when the logic is sound, and discomfort in adversarial situations."),
        (lo("A") and n("FT") > 6, "Decision making",
         "Both measures agree on impersonal decision making. Expect consistency and comfort with unpopular calls, "
         "and a tendency to underweight how a decision will land emotionally."),
        (hi("E") and n("IE") > 6, "Consistency across the two measures",
         "The two questionnaires agree closely on sociability, which is the pairing that holds up best in research. "
         "This is the most dependable single finding in the report."),
        (lo("E") and n("IE") < -6, "Consistency across the two measures",
         "The two questionnaires agree closely on reserve, which is the pairing that holds up best in research. "
         "This is the most dependable single finding in the report."),
    ]
    out = []
    seen = set()
    for cond, heading, text in rules:
        if cond and heading not in seen:
            seen.add(heading)
            out.append((heading, text))
    return out
 
 
def tensions(t, d, band):
    """Places where the two instruments disagree, stated plainly."""
    out = []
    pairs = [
        ("Extraversion", t["E"], (t["E"] - 10) / 40, "Introversion-Extraversion", d["IE"], (d["IE"] - 12) / 48, False),
        ("Openness", t["O"], (t["O"] - 10) / 40, "Sensing-Intuition", d["SN"], (d["SN"] - 12) / 48, False),
        ("Agreeableness", t["A"], (t["A"] - 10) / 40, "Feeling-Thinking", d["FT"], (d["FT"] - 12) / 48, True),
        ("Conscientiousness", t["C"], (t["C"] - 10) / 40, "Judging-Perceiving", d["JP"], (d["JP"] - 12) / 48, True),
    ]
    for tname, _, tpos, dname, _, dpos, invert in pairs:
        other = 1 - dpos if invert else dpos
        gap = abs(tpos - other) * 100
        if gap >= 30:
            out.append(f"{tname} and {dname} point in noticeably different directions "
                       f"({gap:.0f} points apart on comparable scales). Treat both as provisional on this dimension.")
    return out
 
 
# ─────────────────────────────────────────────────────────── html
 
def ordinal(n):
    n = round(n)
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }".replace(" ", "")
 
 
def bar(pos, colour, mid=True):
    return (f'<div class="bar"><span class="fill" style="width:{pos*100:.1f}%;background:{colour}"></span>'
            + ('<span class="mid"></span>' if mid else "") + "</div>")
 
 
CSS = """
:root{--form:#DDE4DF;--sheet:#FBFBF8;--alt:#F4F6F1;--ink:#22272A;--ink2:#5D686B;--ink3:#8C979A;--mark:#B3402E;
--sans:"IBM Plex Sans",-apple-system,"Segoe UI",Roboto,sans-serif;--serif:"IBM Plex Serif",Palatino,Georgia,serif}
*{box-sizing:border-box}
body{margin:0;background:var(--form);color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.55}
.wrap{max-width:820px;margin:0 auto;padding:30px 20px 70px}
.sheet{background:var(--sheet);border-radius:3px;box-shadow:0 1px 0 rgba(34,39,42,.10),0 8px 30px rgba(34,39,42,.06);padding:36px 34px;margin-bottom:20px}
@media(max-width:640px){.wrap{padding:14px 10px}.sheet{padding:22px 16px}}
h1{font-family:var(--serif);font-weight:500;font-size:1.6rem;margin:0 0 6px;letter-spacing:-.01em}
h2{font-family:var(--serif);font-weight:500;font-size:1.22rem;margin:34px 0 4px}
h2:first-of-type{margin-top:0}
h3{font-size:1rem;font-weight:600;margin:22px 0 3px}
p{margin:0 0 12px;max-width:68ch}
.sub{color:var(--ink2);font-size:.9rem;margin-bottom:26px}
.lede{font-family:var(--serif);font-size:1.1rem;line-height:1.6}
.meta{display:flex;flex-wrap:wrap;gap:18px;font-size:.84rem;color:var(--ink2);margin-bottom:4px}
.meta b{color:var(--ink);font-weight:500}
.scale{margin:0 0 24px}
.scale .top{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.scale .nm{font-weight:600}
.scale .nm small{font-weight:400;color:var(--ink3);margin-left:8px;font-size:.8rem}
.scale .val{font-variant-numeric:tabular-nums;font-weight:500;white-space:nowrap}
.scale .val i{font-style:normal;color:var(--ink3);font-size:.8rem}
.bar{height:9px;background:#E7EBE6;border-radius:5px;position:relative;overflow:hidden;margin:7px 0 5px}
.fill{position:absolute;inset:0 auto 0 0;border-radius:5px}
.mid{position:absolute;left:50%;top:0;bottom:0;width:1px;background:rgba(34,39,42,.25)}
.desc{font-family:var(--serif);font-size:1rem;margin:0}
.band{font-size:.8rem;color:var(--ink2)}
.type{font-family:var(--serif);font-size:2.6rem;letter-spacing:.06em;margin:0 0 2px;font-weight:500}
.tag{display:inline-block;font-size:.74rem;padding:2px 8px;border-radius:2px;background:#E7EBE6;color:var(--ink2);margin:0 5px 5px 0}
.tag.warn{background:#F2DED9;color:var(--mark)}
.callout{background:var(--alt);border-radius:3px;padding:16px 18px;margin:16px 0}
.callout p:last-child{margin-bottom:0}
table{border-collapse:collapse;width:100%;font-size:.88rem;margin-top:10px}
th,td{text-align:left;padding:7px 12px 7px 0}
th{font-weight:600;color:var(--ink2);font-size:.78rem}
tbody tr:nth-child(odd){background:var(--alt)}
td.n{text-align:right;font-variant-numeric:tabular-nums;padding-right:14px}
.foot{font-size:.82rem;color:var(--ink3);max-width:70ch}
a{color:var(--ink);text-decoration:underline;text-underline-offset:3px}
@media print{body{background:#fff}.sheet{box-shadow:none;page-break-inside:avoid;padding:0 0 18px}}
"""
 
HEAD = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@400;500&display=swap" rel="stylesheet">
<style>%s</style></head><body><div class="wrap">""" % CSS
 
E = html.escape
 
 
def report_html(rec, scored, sample_pct):
    t, d = scored["traits"], scored["dichs"]
    flags = quality_flags(rec, scored)
    when = (rec.get("received_at") or "")[:10]
    secs = int((rec.get("elapsed_ms") or 0) / 1000)
    ref_n = f"{REF['n']:,}"
 
    parts = [HEAD.replace("__TITLE__", f"Report {E(rec.get('id',''))}")]
 
    # cover
    parts.append('<section class="sheet"><h1>Behavioural profile</h1>')
    parts.append(f'<p class="sub">Reference {E(rec.get("id",""))} &middot; completed {E(when)}</p>')
    parts.append('<div class="meta">')
    parts.append(f'<span>Respondent <b>{E(rec.get("email",""))}</b></span>')
    if secs:
        parts.append(f'<span>Time taken <b>{secs // 60} min {secs % 60} s</b></span>')
    parts.append(f'<span>Items answered <b>{scored["answered_a"] + scored["answered_b"]} of 98</b></span>')
    parts.append("</div>")
    if flags:
        parts.append("<p style='margin-top:16px'>" + "".join(
            f'<span class="tag warn">{E(name)}</span>' for name, _ in flags) + "</p>")
        parts.append('<div class="callout"><p><b>Read this report with caution.</b> The answers show '
                     + "; ".join(E(why) for _, why in flags)
                     + ". Interpretation below assumes answers were given carefully, so treat it as unreliable "
                       "until the person completes it again.</p></div>")
    parts.append('<p class="lede" style="margin-top:18px">This report is generated from two self-report '
                 'questionnaires answered on one occasion. It describes tendencies the person reported about '
                 'themselves, not abilities, and not a diagnosis.</p></section>')
 
    # trait profile
    parts.append('<section class="sheet"><h2>Trait profile</h2>')
    parts.append('<p class="sub">Five broad traits, each scored from 10 to 50 out of ten items. The mark in the '
                 'middle of each bar is the midpoint of the scale.</p>')
    for k in ("E", "A", "C", "S", "O"):
        name, note, colour = TRAITS[k]
        v = t[k]
        b = trait_band(v)
        pct = sample_pct.get(k)
        pct_txt = f" &middot; {ordinal(pct)} percentile among your respondents" if pct is not None else ""
        parts.append('<div class="scale"><div class="top">'
                     f'<span class="nm">{name}<small>{note}</small></span>'
                     f'<span class="val">{v}<i> / 50</i></span></div>')
        parts.append(bar((v - 10) / 40, colour))
        parts.append(f'<div class="band">{b}{pct_txt}</div>')
        parts.append(f'<p class="desc">{TRAIT_TEXT[k][b]}</p></div>')
    parts.append("</section>")
 
    # type profile
    parts.append('<section class="sheet"><h2>Preference profile</h2>')
    parts.append(f'<div class="type">{E(scored["type"])}</div>')
    parts.append(f'<p class="sub">Four preferences, each scored from 12 to 60 with a midpoint of 36. '
                 f'Percentiles compare against {ref_n} previous respondents.</p>')
    for k in ("IE", "SN", "FT", "JP"):
        low, high, _ll, _hl, note, colour = DICHS[k]
        v = d[k]
        dist = v - MID
        side = "neither side" if dist == 0 else (high if dist > 0 else low)
        strength = lean(dist)
        pct = REF[k]["pct"][v - 12]
        parts.append('<div class="scale"><div class="top">'
                     f'<span class="nm">{low} or {high}<small>{note}</small></span>'
                     f'<span class="val">{v}<i> / 60</i></span></div>')
        parts.append(bar((v - 12) / 48, colour))
        parts.append(f'<div class="band">{side}, {strength} preference &middot; {ordinal(pct)} percentile of the reference sample</div>')
        parts.append(f'<p class="desc">{DICH_TEXT[k][1 if dist > 0 else 0]}</p>')
        if strength == "borderline":
            parts.append('<p class="band" style="color:var(--mark)">Within two points of the midpoint. '
                         'This letter would plausibly flip on another day and should not be relied on.</p>')
        if k == "SN":
            parts.append('<p class="band">This is the least reliable of the four scales in published data '
                         '(&alpha; = .55 against .82, .82 and .83). Weight it accordingly.</p>')
        parts.append("</div>")
    parts.append("</section>")
 
    # behavioural reading
    parts.append('<section class="sheet"><h2>What this tends to look like in practice</h2>')
    parts.append('<p class="sub">Each reading below is driven by the scores above. Where the second questionnaire '
                 'points the same way, that agreement is noted.</p>')
    for heading, text in theme_sections(t, d, trait_band):
        parts.append(f"<h3>{E(heading)}</h3><p>{text}</p>")
    sh, st = standout(t, trait_band)
    parts.append(f"<h3>{E(sh)}</h3><p>{st}</p>")
    parts.append("</section>")
 
    combos = combination_rules(t, d, trait_band)
    if combos:
        parts.append('<section class="sheet"><h2>Patterns from combinations of scores</h2>')
        parts.append('<p class="sub">These come from scores acting together rather than any single scale. '
                     'Only the patterns present in this profile appear.</p>')
        for heading, text in combos:
            parts.append(f"<h3>{E(heading)}</h3><p>{text}</p>")
        parts.append("</section>")
 
    # disagreements
    tens = tensions(t, d, trait_band)
    parts.append('<section class="sheet"><h2>Agreement between the two questionnaires</h2>')
    if tens:
        parts.append('<p>Four pairs of scales measure overlapping ground. These disagree:</p>')
        for x in tens:
            parts.append(f"<p>{E(x)}</p>")
        parts.append('<p>Disagreement is informative rather than an error. It usually means the trait sits near '
                     'the middle, where small differences in wording move the answer.</p>')
    else:
        parts.append('<p>The four overlapping pairs of scales — sociability, openness to ideas, how decisions are '
                     'weighed, and structure — agree across both questionnaires. That consistency is the main reason '
                     'to take the profile above seriously.</p>')
    parts.append("</section>")
 
    # limits
    parts.append('<section class="sheet"><h2>How far to trust this</h2>'
                 '<p class="foot">Scores are arithmetic and exact. The written interpretation applies fixed rules '
                 'to those scores and describes what people answering this way tend to report about themselves.</p>'
                 '<p class="foot">This is a single self-report taken on one day. Mood, context and how someone wants '
                 'to be seen all move the numbers. It measures preferences and tendencies, never ability, and it is '
                 'not a clinical instrument or a diagnosis.</p>'
                 '<p class="foot">Neither questionnaire is validated for hiring, promotion or any other selection '
                 'decision, and the four-letter preference measure in particular has known reliability problems: '
                 'people retested weeks later often receive different letters. Use this for reflection and '
                 'conversation, not for deciding about someone.</p>'
                 '<p class="foot">The instruments are open-source research measures. The preference measure is not '
                 'the MBTI and is not affiliated with it.</p></section>')
 
    parts.append("</div></body></html>")
    return "".join(parts)
 
 
def index_html(rows):
    parts = [HEAD.replace("__TITLE__", "Reports"), '<section class="sheet"><h1>Reports</h1>',
             f'<p class="sub">{len(rows)} response{"s" if len(rows) != 1 else ""}, newest first.</p>',
             "<table><thead><tr><th>Completed</th><th>Respondent</th><th>Type</th>"
             "<th class='n'>E</th><th class='n'>A</th><th class='n'>C</th><th class='n'>S</th><th class='n'>O</th>"
             "<th>Notes</th><th></th></tr></thead><tbody>"]
    for r in rows:
        t = r["scored"]["traits"]
        flags = "".join(f'<span class="tag warn">{E(n)}</span>' for n, _ in r["flags"])
        parts.append(f'<tr><td>{E((r["rec"].get("received_at") or "")[:10])}</td>'
                     f'<td>{E(r["rec"].get("email",""))}</td><td><b>{E(r["scored"]["type"])}</b></td>'
                     + "".join(f'<td class="n">{t[k]}</td>' for k in ("E", "A", "C", "S", "O"))
                     + f'<td>{flags}</td><td><a href="{E(r["file"])}">open</a></td></tr>')
    parts.append("</tbody></table></section></div></body></html>")
    return "".join(parts)
 
 
# ─────────────────────────────────────────────────────────── main
 
def load():
    out = []
    if not RESPONSES.exists():
        return out
    for f in sorted(RESPONSES.glob("*.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            print(f"  skipping unreadable file: {f.name}")
    return out
 
 
def percentile_rank(values, v):
    below = sum(1 for x in values if x < v)
    equal = sum(1 for x in values if x == v)
    return round((below + equal / 2) / len(values) * 100)
 
 
def main():
    records = load()
    if not records:
        print("no responses yet — nothing to score")
        return
    scored = [(r, score_response(r)) for r in records]
 
    # percentiles within your own sample, only once there are enough people
    # for the number to mean anything
    dist = {k: [s["traits"][k] for _, s in scored] for k in TRAITS}
    enough = len(scored) >= 25
 
    REPORTS.mkdir(exist_ok=True)
    rows = []
    for rec, sc in scored:
        pct = {k: percentile_rank(dist[k], sc["traits"][k]) for k in TRAITS} if enough else {}
        rid = rec.get("id") or (rec.get("received_at") or "unknown")[:19].replace(":", "-")
        fname = f"{rid}.html"
        (REPORTS / fname).write_text(report_html(rec, sc, pct), encoding="utf-8")
        rows.append(dict(rec=rec, scored=sc, flags=quality_flags(rec, sc), file=fname))
 
    rows.sort(key=lambda r: r["rec"].get("received_at") or "", reverse=True)
    (REPORTS / "index.html").write_text(index_html(rows), encoding="utf-8")
 
    cols = (["id", "received_at", "email", "elapsed_ms", "answered", "type"]
            + list(TRAITS) + list(DICHS) + ["flags"])
    with (HERE / "scores.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            rec, sc = r["rec"], r["scored"]
            w.writerow({
                "id": rec.get("id"), "received_at": rec.get("received_at"), "email": rec.get("email"),
                "elapsed_ms": rec.get("elapsed_ms"),
                "answered": sc["answered_a"] + sc["answered_b"], "type": sc["type"],
                **sc["traits"], **sc["dichs"],
                "flags": "|".join(n for n, _ in r["flags"]),
            })
 
    types = Counter(r["scored"]["type"] for r in rows)
    print(f"scored {len(rows)} response(s)")
    print(f"  reports/index.html and {len(rows)} individual report(s)")
    print(f"  scores.csv")
    if not enough:
        print(f"  percentiles within your sample start at 25 responses (currently {len(rows)})")
    flagged = sum(1 for r in rows if r["flags"])
    if flagged:
        print(f"  {flagged} response(s) carry a data-quality flag")
    if types:
        print("  most common codes: " + ", ".join(f"{t} x{c}" for t, c in types.most_common(3)))
 
 
if __name__ == "__main__":
    main()
 






