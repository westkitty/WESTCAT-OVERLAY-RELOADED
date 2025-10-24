from __future__ import annotations

import re
from typing import Dict, List, Optional

Step = Dict[str, object]

FALLBACK_STEPS: List[Step] = [
    {
        "type": "ack",
        "text": "Hi Bryan! I'm WestCat, eh! I'm here to conduct a very important poll with you... Have you got your Timbits ready?",
        "auto_ms": 3000,
    },
    {
        "type": "mcq",
        "text": "If WestCat were trained on purely Canadian data, what would be the single most common embedding vector?",
        "choices": [
            "Maple Syrup",
            "A 'Sorry' that sounds like a question",
            "The smell of fresh snow",
            "The exact sound of a loon calling",
        ],
    },
    {
        "type": "mcq",
        "text": "Which component translates cat-bounces into names like 'idle' or 'blink'?",
        "choices": [
            "The PySide6 Event Loop",
            "The $6,000 gaming GPU (j/k, CPU-only!)",
            "The ResNet18 + KMeans clustering pass",
            "Andrew's massive manifest file",
        ],
    },
    {
        "type": "mcq",
        "text": "As the 'City of Totems', about how many totem poles are on display in Duncan, BC?",
        "choices": ["12", "44", "43", "187"],
    },
    {
        "type": "ack",
        "text": "Pro-tip: follow the yellow footprints to the nearest Tim Hortons for a refuel.",
        "auto_ms": 4000,
    },
    {
        "type": "mcq",
        "text": "Which is the most Canadian way to spell my helper's name?",
        "choices": ["Andrew", "Androo", "Andréw", "Aendrue"],
    },
    {
        "type": "mcq",
        "text": "What is the average airspeed velocity of an unladen swallow?",
        "choices": [
            "15 miles per hour",
            "African or European?",
            "The one that lives in Duncan BC",
            "Faster than a beaver can slap its tail",
        ],
    },
    {
        "type": "mcq",
        "text": "Duncan vibe check—what’s today like?",
        "choices": [
            "Stunning Coastal Walk",
            "Stay Inside, Rainy/Misty",
            "It's Too Nice, I'm Suspicious",
            "The owls just dropped off a Timbits order.",
        ],
    },
    {
        "type": "mcq",
        "text": "Rate your business partner, Andrew:",
        "choices": [
            "Cool",
            "Cooler",
            "Coolest",
            "He's busy making amazing tech, not soup.",
        ],
    },
    {
        "type": "text",
        "text": "Final Q: What feature or custom reaction should WestCat add next?",
    },
    {
        "type": "ack_trigger",
        "text": "That was fun! When you’re ready, click me five times to finish and export.",
    },
]


def parse_bryan_text(txt: str) -> List[Step]:
    """Parse the Bryan conversation document, falling back to baked-in steps if needed."""

    try:
        steps: List[Step] = []
        raw = re.split(r"(?m)(?=^\s*\d+\s|\bStep\s*\d+)", txt)
        filtered = [section.strip() for section in raw if section.strip()]
        if len(filtered) < 5:
            return FALLBACK_STEPS

        for chunk in filtered:
            step_type: Optional[str] = None
            if re.search(r"\bAcknowledge\b", chunk, re.IGNORECASE):
                step_type = "ack"
            elif re.search(r"\bShort Text Input\b", chunk, re.IGNORECASE) or re.search(
                r"\bopen text input\b", chunk, re.IGNORECASE
            ):
                step_type = "text"
            elif re.search(r"\bMultiple Choice\b", chunk, re.IGNORECASE):
                step_type = "mcq"

            match_text = re.search(r"WestCat Line(.*?)(?:Options|Outcome|$)", chunk, re.IGNORECASE | re.DOTALL)
            if match_text:
                text = match_text.group(1).strip()
            else:
                text = chunk.splitlines()[0].strip()
            text = re.sub(r'^\W+|"|”|“', '', text).strip()

            auto_ms = None
            match_auto = re.search(r"Advances automatically after\s*(\d+)\s*seconds?", chunk, re.IGNORECASE)
            if match_auto:
                auto_ms = int(match_auto.group(1)) * 1000

            choices: List[str] = []
            if step_type == "mcq":
                match_opts = re.search(r"Options(.*)$", chunk, re.IGNORECASE | re.DOTALL)
                body = match_opts.group(1) if match_opts else chunk
                for label in ["A", "B", "C", "D", "E", "F"]:
                    choice_match = re.search(rf"\b{label}\.\s*([^\n\r]+)", body)
                    if choice_match:
                        choices.append(choice_match.group(1).strip())

            ack_trigger = bool(re.search(r"click.*five.*(trigger|dev|export)", chunk, re.IGNORECASE))

            if step_type == "ack" and ack_trigger:
                steps.append({"type": "ack_trigger", "text": text or "Click five times to export."})
            elif step_type == "ack":
                steps.append({"type": "ack", "text": text, "auto_ms": auto_ms or 3000})
            elif step_type == "mcq" and choices:
                steps.append({"type": "mcq", "text": text, "choices": choices})
            elif step_type == "text":
                steps.append({"type": "text", "text": text})

        return steps if len(steps) >= 6 else FALLBACK_STEPS
    except Exception:
        return FALLBACK_STEPS


def load_bryan_steps(path: str) -> List[Step]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            doc = handle.read()
        return parse_bryan_text(doc)
    except Exception:
        return FALLBACK_STEPS
