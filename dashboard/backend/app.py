#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import random
import re
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
import fcntl
import hashlib
import mimetypes
import uuid
import urllib.request
import psutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parents[2]
STORAGE_ROOT = ROOT / "dashboard_storage"
RUNS_ROOT = STORAGE_ROOT / "runs"
RUNTIME_ROOT = ROOT / "runtime"
ENV_PATH = ROOT / ".env.dashboard"

DEFAULT_PRODUCT_MASTER = ROOT / "product master doc.txt"
DEFAULT_PLAYBOOK = ROOT / "AD_CREATIVE_SYSTEM_PLAYBOOK.md"
DEFAULT_IMAGE_SOURCES_FILE = ROOT / "input" / "image_sources.txt"
LEGACY_ACTIVE_IMAGES_FILE = ROOT / "input" / "activeimages.txt"
INPUT_IMAGES_DIR = ROOT / "input" / "images"
GENERATED_IMAGES_ROOT = ROOT / "generated_images"


FORMATS = ["HERO", "BA", "TEST", "FEAT", "UGC"]
DEFAULT_OPENCODE_API_URL = os.getenv("OPENCODE_API_URL", "http://127.0.0.1:4090")
OPENCODE_MAX_CONCURRENT = 2
OPENCODE_QUEUE_DIR = RUNTIME_ROOT / "opencode_queue"
OPENCODE_QUEUE_LOG = OPENCODE_QUEUE_DIR / "queue.log"

HEADLINE_CONCEPT_FRAMEWORK = {
    "audience_stage": [
        {"id": "unaware", "direction": "Name a hidden or ignored weight-loss friction before presenting the product."},
        {"id": "problem_aware", "direction": "Start from the known problem and make the fix feel clearer."},
        {"id": "solution_aware", "direction": "Assume they know fixes exist; show why this system is easier, safer, or more guided."},
        {"id": "product_aware", "direction": "Assume they know the kit; give the push through proof, urgency, trust, or simplicity."},
    ],
    "lead_angle": [
        {"id": "pain_point", "direction": "Lead with the specific problem or friction."},
        {"id": "desired_outcome", "direction": "Lead with the result or felt outcome."},
        {"id": "social_proof", "direction": "Lead with others' trust, usage, or testimonial logic."},
        {"id": "authority", "direction": "Lead with expertise, doctor formulation, or Ayurveda credibility."},
        {"id": "story", "direction": "Lead with a real-life routine or user-situation narrative."},
        {"id": "curiosity", "direction": "Lead with a question or mechanism gap that makes the reader want the explanation."},
        {"id": "comparison", "direction": "Lead by contrasting this system with stricter, messier, or harder alternatives."},
        {"id": "offer", "direction": "Lead with practical reason to act, result window, guarantee, or kit completeness."},
    ],
    "message_structure": [
        {"id": "pas", "direction": "Problem, then sharpen the consequence, then present the product-led solution."},
        {"id": "bab", "direction": "Before state, after/progress state, then the bridge that gets them there."},
        {"id": "fab", "direction": "Feature, advantage, benefit; keep the feature concrete and the benefit weight-loss-linked."},
        {"id": "four_us", "direction": "Make it useful, urgent where honest, unique, and ultra-specific."},
    ],
}

HOOK_STRUCTURE_GUIDANCE: dict[str, str] = {
    "question_lead": "Open with a plain question the buyer would actually ask. Keep it specific, not clever.",
    "proof_lead": "Open with proof, authority, or a concrete result window before explaining the product reason elsewhere.",
    "contrast_loop": "Open with a natural spoken contrast using but, yet, still, without, before/after, or even with. Show the old friction and the improved weight-loss path in one readable line. Avoid stiff grammar like a slogan template.",
    "confession_lead": "Open like a believable first-person admission, not a polished testimonial headline.",
    "command_lead": "Open with a direct, simple instruction only when it sounds like ad copy, not a how-to manual.",
}

CONCEPT_ANGLE_GUIDANCE: dict[str, str] = {
    "pain_point": "Lead from one real buyer frustration. Keep it concrete and specific, not dramatic or shame-based.",
    "desired_outcome": "Lead with the practical weight-loss outcome or felt relief. Keep it believable, not transformational hype.",
    "social_proof": "Lead with trust, usage, testimonials, or crowd proof. Use proof as credibility, not empty popularity.",
    "authority": "Lead with doctor-formulated, Ayurveda, or expert credibility. Keep it simple and ad-readable.",
    "curiosity": "Lead with a specific mechanism gap or question that makes the reader want the explanation. Avoid clickbait.",
    "comparison": "Lead by contrasting the kit with strict diets, random attempts, or high-friction routines. Avoid competitor bashing.",
    "offer": "Lead with a clear reason to act: 15-day result window, kit completeness, or guarantee logic. Do not mention price.",
}

AWARENESS_STAGE_GUIDANCE: dict[str, str] = {
    "unaware": "Name a hidden daily friction before talking like the reader already wants this kit.",
    "problem_aware": "Start from a problem the reader already recognizes, then make the next step feel clear.",
    "solution_aware": "Assume the reader has tried fixes. Show why this system is easier, safer, or more guided.",
    "product_aware": "Assume the reader knows the kit. Give a proof, urgency, trust, or simplicity push to act.",
}

PROOF_STYLE_GUIDANCE: dict[str, str] = {
    "authority_anchor": "Use doctor-formulated or Ayurvedic credibility as the trust lane. Avoid vague 'expert-backed' filler.",
    "social_proof": "Use user count, testimonials, reviews, or served-users proof where safe. Make it specific.",
    "mechanism_explainer": "Explain the product mechanism simply: hunger/cravings, routine, fullness, digestion, or adherence.",
    "routine_clarity": "Make the proof feel easy to follow: clear steps, low guesswork, simple daily routine.",
    "objection_flip": "Address a real doubt directly, then resolve it with proof or mechanism. Avoid sounding defensive.",
}

CTA_VOICE_GUIDANCE: dict[str, str] = {
    "urgent_start": "Ask for action now/today without sounding pushy or using sale pressure.",
    "guided_next_step": "Ask the user to see, check, or view the plan/protocol/steps.",
    "reassurance_start": "Make the next step feel safe or low-risk: check fit, see if it suits, try safely.",
    "challenge_action": "Frame the action as a 15-day test or challenge. Keep it compliant and simple.",
    "discovery_action": "Invite learning: see how it works, learn the steps, discover the routine.",
}

CONCEPT_STRUCTURE_GUIDANCE: dict[str, str] = {
    "pas": "Shape copy as problem first, consequence next, then product-led resolution.",
    "bab": "Use before-to-after bridge flow: current struggle, better state, then the bridge routine.",
    "fab": "Lead with concrete feature, explain practical advantage, then connect to weight-loss benefit.",
    "four_us": "Keep wording useful, honestly urgent, unique enough to stand out, and ultra-specific.",
}


def classify_hook_structure(headline: str) -> str:
    """Classify a headline opening pattern for hypothesis sanity checks.

    The classifier only verifies whether a pattern is present.
    It does not prescribe which pattern should be used — that's the LLM's job.
    A headline is a question_lead if it opens as a question or contains an
    early question mark. Everything else is classified by visible pattern cues.
    """
    text = (headline or "").strip().lower().replace("’", "'")
    if not text:
        return "proof_lead"
    if text.startswith(("why ", "what ", "how ", "when ", "can ", "could ", "will ", "want ", "need ", "tired ")) or "?" in text[:50]:
        return "question_lead"
    if text.startswith(("stop", "start", "try", "see", "check", "take")):
        return "command_lead"
    contrast_terms = ["before", "after", "without", "instead", " but ", " yet ", " still ", "doesn't have to", "even with"]
    if any(term in f" {text} " for term in contrast_terms):
        return "contrast_loop"
    if text.startswith(("i ", "my ")) or "felt" in text or "struggled" in text:
        return "confession_lead"
    if text.startswith(("finally", "trusted", "proven")) or "70,000" in text or "doctor" in text:
        return "proof_lead"
    return "proof_lead"


def headline_for_candidate(candidate: dict[str, Any], lang: str = "EN") -> str:
    copy = candidate.get("copy") if isinstance(candidate.get("copy"), dict) else {}
    block = copy.get(lang) if isinstance(copy.get(lang), dict) else {}
    return str(block.get("headline") or "").strip()


def copy_text_for_candidate(candidate: dict[str, Any], lang: str = "EN") -> str:
    copy = candidate.get("copy") if isinstance(candidate.get("copy"), dict) else {}
    block = copy.get(lang) if isinstance(copy.get(lang), dict) else {}
    parts: list[str] = []
    for key in ["headline", "support_line", "trust_line", "attribution", "cta"]:
        value = block.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    bullets = block.get("bullets")
    if isinstance(bullets, list):
        parts.extend(str(item).strip() for item in bullets if str(item).strip())
    return " ".join(parts)


def cta_for_candidate(candidate: dict[str, Any], lang: str = "EN") -> str:
    copy = candidate.get("copy") if isinstance(candidate.get("copy"), dict) else {}
    block = copy.get(lang) if isinstance(copy.get(lang), dict) else {}
    return str(block.get("cta") or "").strip()


def classify_proof_style_text(text: str) -> str:
    lower = (text or "").lower()
    if "70,000" in lower or "user" in lower or "people" in lower or "review" in lower or "testimonial" in lower or "trusted" in lower:
        return "social_proof"
    if "doctor" in lower or "ayurvedic" in lower or "dr." in lower or "formulated" in lower:
        return "authority_anchor"
    if "but" in lower or "skeptical" in lower or "doubt" in lower or "worried" in lower or "tried" in lower:
        return "objection_flip"
    if "simple" in lower or "clear" in lower or "5-minute" in lower or "easy" in lower or "low guesswork" in lower:
        return "routine_clarity"
    if "step" in lower or "routine" in lower or "morning" in lower or "night" in lower or "ok liquid" in lower or "craving" in lower or "fullness" in lower:
        return "mechanism_explainer"
    return "mechanism_explainer"


def classify_cta_voice_text(cta: str) -> str:
    text = (cta or "").strip().lower()
    if "test" in text or "challenge" in text or "15-day" in text or "15 day" in text:
        return "challenge_action"
    if "fit" in text or "risk" in text or "safe" in text or "suit" in text:
        return "reassurance_start"
    if "today" in text or "now" in text or "start" in text or "act" in text:
        return "urgent_start"
    if "learn" in text or "how" in text or "works" in text or "discover" in text:
        return "discovery_action"
    if "see" in text or "view" in text or "check" in text or "steps" in text or "details" in text or "plan" in text or "protocol" in text:
        return "guided_next_step"
    return "guided_next_step"


def proof_style_matches(expected: str, text: str) -> bool:
    lower = (text or "").lower()
    checks = {
        "authority_anchor": ["doctor", "ayurvedic", "dr.", "formulated"],
        "social_proof": ["70,000", "user", "people", "review", "testimonial", "trusted"],
        "mechanism_explainer": ["step", "routine", "morning", "night", "ok liquid", "craving", "fullness", "works"],
        "routine_clarity": ["simple", "clear", "5-minute", "easy", "low guesswork", "step", "routine"],
        "objection_flip": ["but", "skeptical", "doubt", "worried", "tried", "without"],
    }
    return any(term in lower for term in checks.get(expected, []))


def cta_voice_matches(expected: str, cta: str) -> bool:
    text = (cta or "").strip().lower()
    checks = {
        "urgent_start": ["today", "now", "start", "act"],
        "guided_next_step": ["see", "view", "check", "steps", "details", "plan", "protocol"],
        "reassurance_start": ["fit", "risk", "safe", "suit"],
        "challenge_action": ["test", "challenge", "15-day", "15 day"],
        "discovery_action": ["learn", "how", "works", "discover"],
    }
    return any(term in text for term in checks.get(expected, []))


def hook_structure_mismatch(candidate: dict[str, Any], planned_ad: dict[str, Any]) -> str | None:
    hypothesis = planned_ad.get("hypothesis") if isinstance(planned_ad.get("hypothesis"), dict) else {}
    if hypothesis.get("type") != "hook_structure":
        return None
    expected = str(hypothesis.get("variant") or "").strip()
    if not expected:
        return None
    headline = headline_for_candidate(candidate, "EN")
    actual = classify_hook_structure(headline)
    if actual != expected:
        return f"Expected hook_structure {expected}, but EN headline classified as {actual}: {headline!r}"
    return None


def hypothesis_mismatch(candidate: dict[str, Any], planned_ad: dict[str, Any]) -> str | None:
    hypothesis = planned_ad.get("hypothesis") if isinstance(planned_ad.get("hypothesis"), dict) else {}
    hyp_type = hypothesis.get("type")
    expected = str(hypothesis.get("variant") or "").strip()
    if not hyp_type or hyp_type == "none" or not expected:
        return None
    if hyp_type == "hook_structure":
        return hook_structure_mismatch(candidate, planned_ad)
    if hyp_type == "concept_angle":
        actual = str(candidate.get("concept_angle") or "").strip()
        if actual != expected:
            return f"Expected concept_angle {expected}, but candidate returned {actual or 'blank'}"
    if hyp_type == "awareness_stage":
        actual = str(candidate.get("awareness_stage") or "").strip()
        if actual != expected:
            return f"Expected awareness_stage {expected}, but candidate returned {actual or 'blank'}"
    if hyp_type == "concept_structure":
        actual = str(candidate.get("concept_structure") or "").strip()
        if actual != expected:
            return f"Expected concept_structure {expected}, but candidate returned {actual or 'blank'}"
    if hyp_type == "proof_style":
        copy_text = copy_text_for_candidate(candidate, "EN")
        if proof_style_matches(expected, copy_text):
            return None
        actual = classify_proof_style_text(copy_text)
        if actual != expected:
            return f"Expected proof_style {expected}, but EN copy classified as {actual}: {copy_text!r}"
    if hyp_type == "cta_voice":
        cta = cta_for_candidate(candidate, "EN")
        if cta_voice_matches(expected, cta):
            return None
        actual = classify_cta_voice_text(cta)
        if actual != expected:
            return f"Expected cta_voice {expected}, but EN CTA classified as {actual}: {cta!r}"
    return None


HYPOTHESIS_VARIABLES: dict[str, dict[str, Any]] = {
    "none": {
        "label": "No hypothesis test",
        "description": "Generate ads normally without controlled A/B testing.",
        "options": [],
    },
    "hook_structure": {
        "label": "Hook Structure (H1)",
        "description": "Test which headline opening pattern performs best: question vs. proof vs. contrast vs. confession vs. command.",
        "options": [
            {"id": "question_lead", "label": "Question Lead", "hint": "Headline opens with a question"},
            {"id": "proof_lead", "label": "Proof Lead", "hint": "Headline opens with credibility or numbers"},
            {"id": "contrast_loop", "label": "Contrast Loop", "hint": "Headline uses before/after tension"},
            {"id": "confession_lead", "label": "Confession Lead", "hint": "Headline uses first-person admission"},
            {"id": "command_lead", "label": "Command Lead", "hint": "Headline uses direct instruction"},
        ],
    },
    "concept_angle": {
        "label": "Concept Angle (H2)",
        "description": "Test which messaging angle drives better results: pain vs. outcome vs. proof vs. authority vs. curiosity.",
        "options": [
            {"id": "pain_point", "label": "Pain Point", "hint": "Lead with the specific problem"},
            {"id": "desired_outcome", "label": "Desired Outcome", "hint": "Lead with the result or felt outcome"},
            {"id": "social_proof", "label": "Social Proof", "hint": "Lead with others' trust or usage"},
            {"id": "authority", "label": "Authority", "hint": "Lead with expertise or doctor credibility"},
            {"id": "curiosity", "label": "Curiosity", "hint": "Lead with a question or mechanism gap"},
            {"id": "comparison", "label": "Comparison", "hint": "Lead by contrasting with harder alternatives"},
            {"id": "offer", "label": "Offer", "hint": "Lead with practical reason to act"},
        ],
    },
    "awareness_stage": {
        "label": "Awareness Stage (H3)",
        "description": "Test whether matching the ad to the audience's funnel stage improves performance.",
        "options": [
            {"id": "unaware", "label": "Unaware", "hint": "Reader does not yet realize the hidden friction"},
            {"id": "problem_aware", "label": "Problem Aware", "hint": "Reader knows the problem but not the fix"},
            {"id": "solution_aware", "label": "Solution Aware", "hint": "Reader knows fixes exist but not why this kit is different"},
            {"id": "product_aware", "label": "Product Aware", "hint": "Reader already knows the kit; give the final push"},
        ],
    },
    "proof_style": {
        "label": "Proof Style (H4)",
        "description": "Test which trust framing works best for this persona: authority vs. social proof vs. mechanism explainer.",
        "options": [
            {"id": "authority_anchor", "label": "Authority Anchor", "hint": "Doctor credibility and Ayurveda trust"},
            {"id": "social_proof", "label": "Social Proof", "hint": "70,000+ users and testimonials"},
            {"id": "mechanism_explainer", "label": "Mechanism Explainer", "hint": "How the protocol works step-by-step"},
            {"id": "routine_clarity", "label": "Routine Clarity", "hint": "Simple, clear daily steps"},
            {"id": "objection_flip", "label": "Objection Flip", "hint": "Address skepticism directly"},
        ],
    },
    "cta_voice": {
        "label": "CTA Voice (H5)",
        "description": "Test which call-to-action tone converts better: urgent vs. guided vs. reassuring vs. discovery.",
        "options": [
            {"id": "urgent_start", "label": "Urgent Start", "hint": "Start Today / Act Now"},
            {"id": "guided_next_step", "label": "Guided Next Step", "hint": "See The Steps / View Details"},
            {"id": "reassurance_start", "label": "Reassurance Start", "hint": "Check If It Fits / Try Risk-Free"},
            {"id": "challenge_action", "label": "Challenge Action", "hint": "Take The 15-Day Test"},
            {"id": "discovery_action", "label": "Discovery Action", "hint": "See How It Works / Learn More"},
        ],
    },
    "concept_structure": {
        "label": "Concept Structure (H6)",
        "description": "Test copy flow structure: PAS vs BAB vs FAB vs Four Us.",
        "options": [
            {"id": "pas", "label": "PAS", "hint": "Problem → Agitation → Solution"},
            {"id": "bab", "label": "BAB", "hint": "Before → After → Bridge"},
            {"id": "fab", "label": "FAB", "hint": "Feature → Advantage → Benefit"},
            {"id": "four_us", "label": "Four Us", "hint": "Useful, urgent, unique, ultra-specific"},
        ],
    },
}




def resolve_language_mode(config: dict[str, Any]) -> str:
    mode = str(config.get("language_mode") or "ALL").strip().upper()
    if mode in {"EN", "HI", "HINGLISH", "ALL"}:
        return mode
    return "ALL"


def assembler_language_mode(config: dict[str, Any]) -> str:
    mode = resolve_language_mode(config)
    if mode == "EN":
        return "EN"
    if mode == "HI":
        return "HI"
    return "BOTH"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id() -> str:
    return f"run_{int(time.time())}_{random.randint(1000, 9999)}"


def ensure_dirs() -> None:
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    INPUT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def load_env_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_persona_library(playbook_path: Path) -> list[dict[str, Any]]:
    text = playbook_path.read_text(encoding="utf-8")
    start = text.find("Persona library (select by number):")
    if start < 0:
        return []
    end = text.find("For each persona", start)
    block = text[start:end if end > start else len(text)]
    out: list[dict[str, Any]] = []
    pattern = re.compile(r"^\s*(\d+)\.\s+(.+)$", re.MULTILINE)
    for m in pattern.finditer(block):
        out.append({"number": int(m.group(1)), "name": m.group(2).strip()})
    return out


PERSONA_SEED_INPUTS: dict[int, dict[str, str]] = {
    1: {"pain": "Daily cravings break every weight plan.", "desire": "Steady appetite control without feeling deprived.", "friction": "Willpower-only plans collapse by evening.", "proof": "Needs visible early control over snack urges.", "tone": "practical and reassuring"},
    2: {"pain": "Work schedule leaves no room for complex routines.", "desire": "Simple weight routine that fits packed days.", "friction": "Meal prep and long workouts are not sustainable.", "proof": "Needs a low-effort protocol that still shows progress.", "tone": "efficient and confidence-building"},
    3: {"pain": "Stress triggers emotional snacking at random times.", "desire": "Calmer eating with fewer stress-led cravings.", "friction": "Plans fail during stressful moments.", "proof": "Needs believable support during emotional triggers.", "tone": "empathetic and non-judgmental"},
    4: {"pain": "Weight loss plateaus despite repeated effort.", "desire": "Break stagnation with a clear daily system.", "friction": "Repeated plateaus kill motivation.", "proof": "Needs a trackable, structured restart path.", "tone": "direct and motivating"},
    5: {"pain": "PCOD-related weight gain feels harder to reverse.", "desire": "Steadier weight progress with manageable routine.", "friction": "Fear of harsh or unsafe methods.", "proof": "Needs non-cure, compliant weight-support framing.", "tone": "careful and trust-led"},
    6: {"pain": "Thyroid-linked weight gain feels stubborn and slow.", "desire": "Consistent progress without extreme restrictions.", "friction": "Low confidence after slow previous results.", "proof": "Needs realistic, compliant support expectations.", "tone": "measured and credible"},
    7: {"pain": "Multiple failed diets created low confidence.", "desire": "A restart that actually feels doable.", "friction": "Past strict plans felt impossible to continue.", "proof": "Needs simple steps and visible early wins.", "tone": "encouraging and reset-focused"},
    8: {"pain": "Wants weight loss but fears weakness and fatigue.", "desire": "Lighter body with stable daily energy.", "friction": "Skeptical of plans that feel draining.", "proof": "Needs assurance of practical energy support.", "tone": "calm and evidence-led"},
    9: {"pain": "Parent schedule causes rushed meals and random snacking.", "desire": "A routine that works even on chaotic days.", "friction": "No time for rigid diets or long workouts.", "proof": "Needs a simple protocol that fits family life.", "tone": "real-life and practical"},
    10: {"pain": "Self-care is postponed while handling household priorities.", "desire": "A manageable routine that can be sustained at home.", "friction": "Complex plans don't fit daily responsibilities.", "proof": "Needs a low-friction system for homemaker schedules.", "tone": "supportive and respectful"},
    11: {"pain": "Tea-time office snacking derails daily intake control.", "desire": "Fewer impulse snacks during work breaks.", "friction": "Social snack cues are hard to resist.", "proof": "Needs practical control over recurring snack windows.", "tone": "conversational and specific"},
    12: {"pain": "Late-night hunger leads to repeated overeating.", "desire": "Calmer nights with better eating control.", "friction": "Evening cravings undo daytime discipline.", "proof": "Needs night-routine support that feels realistic.", "tone": "steady and habit-focused"},
    13: {"pain": "Weight rebounds after festivals and travel periods.", "desire": "Quick reset back to steady routine.", "friction": "Irregular days break consistency easily.", "proof": "Needs a restart protocol that works after disruptions.", "tone": "reset-oriented and practical"},
    14: {"pain": "Worry that metabolism has slowed permanently.", "desire": "Believable progress through structured daily consistency.", "friction": "Confusion from too many conflicting theories.", "proof": "Needs clear mechanism logic without hype claims.", "tone": "clear and science-grounded"},
    15: {"pain": "Digestive discomfort and weight concerns occur together.", "desire": "Lighter digestion with better intake control.", "friction": "Discomfort makes routines hard to follow.", "proof": "Needs digestion-support plus weight-management framing.", "tone": "gentle and practical"},
    16: {"pain": "Budget concerns reduce trust in expensive plans.", "desire": "Reliable progress from a practical system.", "friction": "Fear of paying without results.", "proof": "Needs strong value and risk-reduction cues.", "tone": "transparent and outcome-focused"},
    17: {"pain": "Event deadline creates pressure and urgency.", "desire": "Visible progress in a short, realistic window.", "friction": "Panic-driven plans often backfire.", "proof": "Needs structured short-term milestone framing.", "tone": "urgent but controlled"},
    18: {"pain": "Low confidence from body discomfort and low energy.", "desire": "Feel lighter, sharper, and more confident daily.", "friction": "Inconsistent routines reduce momentum.", "proof": "Needs confidence-building early progress signals.", "tone": "uplifting and grounded"},
    19: {"pain": "Only trusts doctor-backed, evidence-grounded solutions.", "desire": "Safe-feeling system with clear proof signals.", "friction": "Distrust of generic internet claims.", "proof": "Needs founder credibility and structured protocol proof.", "tone": "authoritative and factual"},
    20: {"pain": "Struggles to stay consistent without accountability.", "desire": "Daily support that keeps follow-through high.", "friction": "Drops routines when guidance is missing.", "proof": "Needs tracker-led support and coach cues.", "tone": "coach-like and motivating"},
    21: {"pain": "Hates complicated plans and too many rules.", "desire": "Simple steps with almost no guesswork.", "friction": "Complexity causes early drop-off.", "proof": "Needs a very clear, easy-to-follow structure.", "tone": "simple and direct"},
    22: {"pain": "Progress feels slower after 35 despite effort.", "desire": "Steady sustainable progress without extreme routines.", "friction": "Frustration from slow visible change.", "proof": "Needs realistic milestones and consistency proof.", "tone": "reassuring and practical"},
    23: {"pain": "Routine changed after childbirth and time is limited.", "desire": "A gentle return to steady progress that fits daily life.", "friction": "Harsh or complex plans feel unrealistic right now.", "proof": "Needs practical, supportive steps for a changed routine.", "tone": "gentle and encouraging"},
    24: {"pain": "Weight feels harder to manage during menopause.", "desire": "Visible progress with a manageable, sustainable routine.", "friction": "Usual methods feel harsher and harder to continue.", "proof": "Needs doctor-led credibility and real-life usability.", "tone": "respectful and practical"},
    25: {"pain": "Wants a natural path and avoids harsh methods.", "desire": "Natural weight-loss support that still feels effective.", "friction": "Worries natural options may be vague or weak.", "proof": "Needs clear Ayurvedic, no-synthetic trust cues.", "tone": "clear and trust-led"},
    26: {"pain": "Past quick losses came back too fast.", "desire": "A more sustainable path without bounce-back anxiety.", "friction": "Short-term fixes feel temporary and hard to maintain.", "proof": "Needs non-dependency and maintainability framing.", "tone": "steady and realistic"},
}


# Feature lanes removed: headline/support must be derived freely by the LLM from `product master doc.txt`.


# Format feature rotation removed with feature lanes.


def _framework_item(group: str, item_id: str) -> dict[str, str]:
    for item in HEADLINE_CONCEPT_FRAMEWORK[group]:
        if item["id"] == item_id:
            return item
    return HEADLINE_CONCEPT_FRAMEWORK[group][0]


# Feature-lane-driven headline concept selection removed.


def build_copy_requirements(persona_number: int, fmt: str, format_sequence_index: int, variation_seed: str = "") -> dict[str, Any]:
    # Lanes removed: copy requirements should only enforce goal/structure constraints and let the LLM choose the product facts.
    persona_seed = PERSONA_SEED_INPUTS.get(persona_number, {})
    persona_text = " ".join(str(v).lower() for v in persona_seed.values())
    if any(term in persona_text for term in ["doctor", "trust", "proof", "safe", "natural"]):
        audience_id = "product_aware"
    elif any(term in persona_text for term in ["past", "failed", "plateau", "rebound", "stubborn"]):
        audience_id = "solution_aware"
    elif any(term in persona_text for term in ["cravings", "hunger", "snacking", "stress", "busy", "complicated", "schedule", "packed", "strict", "time"]):
        audience_id = "problem_aware"
    else:
        audience_id = "unaware"

    # Choose a lightweight structure direction only; headline/support must still be selected freely by the LLM.
    # Keep format-appropriate default structure.
    structure_by_fmt = {
        "HERO": "four_us",
        "BA": "bab",
        "TEST": "pas",
        "FEAT": "fab",
        "UGC": "pas",
    }
    concept_structure = structure_by_fmt.get(fmt, "four_us")

    # Lead angle: derived from persona seed only (no feature-lanes).
    if "cravings" in persona_text or "hunger" in persona_text or "snack" in persona_text:
        lead_angle = "pain_point"
    elif "work" in persona_text or "schedule" in persona_text or "simple" in persona_text or "routine" in persona_text:
        lead_angle = "desired_outcome"
    elif "failed" in persona_text or "doubt" in persona_text or "fear" in persona_text or "plateau" in persona_text:
        lead_angle = "comparison"
    elif "doctor" in persona_text or "trust" in persona_text or "proof" in persona_text:
        lead_angle = "authority"
    else:
        lead_angle = "desired_outcome"

    return {
        "must_mention": "Headline or paired support copy must explicitly mention weight loss, obesity reduction, excess-weight reduction, or a 15-day weight outcome.",
        "variation_rule": "Do not reuse the same headline skeleton, support-line skeleton, or persuasion angle as other ads in the same format for this batch.",
        "concept_variation": {
            "audience_stage": _framework_item("audience_stage", audience_id),
            "lead_angle": _framework_item("lead_angle", lead_angle),
            "message_structure": _framework_item("message_structure", concept_structure),
        },
        "hierarchy_rule": "Use concept_variation to set awareness stage / hook direction / flow structure. Do not output labels. Derive actual headline/support from product master doc content.",
        "format_specific_rule": {
            "HERO": "Keep headline as one clean idea. Support line must add believable reason-to-believe and practical ease.",
            "UGC": "Creator-like tone is allowed, but keep headline/support grounded in master-doc facts and compliance.",
            "BA": "Split copy: left bullets are struggle state; right bullets are progress/routine shift.",
            "TEST": "Quote-like headline; attribution + trust line must be role/source-based and non-personal.",
            "FEAT": "Bullets must be distinct product features (LLM decides which features from master doc).",
        }.get(fmt, "Respect format-specific structure; no lane enforcement."),
    }


FORMAT_COPY_RULE_KEYWORDS: dict[str, list[str]] = {
    "HERO": ["copy", "headline", "support", "cta", "text budget", "minimum", "persona"],
    "BA": ["copy", "headline", "bullet", "cta", "text budget", "minimum", "persona", "before", "after", "outcome"],
    "TEST": ["copy", "headline", "quote", "attribution", "trust", "cta", "text budget", "minimum", "persona"],
    "FEAT": ["copy", "headline", "bullet", "feature", "cta", "text budget", "minimum", "persona"],
    "UGC": ["copy", "headline", "support", "cta", "creator", "text budget", "minimum", "persona"],
}

FORMAT_VISUAL_RULE_KEYWORDS = [
    "split-screen",
    "side:",
    "tone",
    "energy",
    "product fidelity",
    "redraw",
    "packaging",
    "visual",
    "background",
    "environment",
    "context-shift",
    "time-of-day",
    "choice-architecture",
    "posture",
    "frame",
    "divider",
    "image",
]

def compact_format_rules_for_copy(fmt: str, format_rules: dict[str, Any]) -> dict[str, Any]:
    fmt = fmt.strip().upper()
    wanted = FORMAT_COPY_RULE_KEYWORDS.get(fmt, [])
    out: list[str] = []
    for raw_rule in format_rules.get("rules") or []:
        rule = str(raw_rule).strip()
        if not rule:
            continue
        lower = rule.lower()
        if any(blocked in lower for blocked in FORMAT_VISUAL_RULE_KEYWORDS):
            continue
        if wanted and not any(keyword in lower for keyword in wanted):
            continue
        out.append(rule)
        if len(out) >= 8:
            break
    return {"format": fmt or format_rules.get("format"), "rules": out}

def build_ad_copy_system_prompt(fmt: str) -> str:
    fmt = fmt.strip().upper()
    base_rules = [
        "You generate ad copy JSON only. Return valid JSON with keys default_aspect_ratio and ads.",
        "Each ads item must include format, headline_angle, awareness_stage, concept_angle, concept_structure, persona, and copy.EN/copy.HI fields compatible with assembler.",
        "Use the attached/read product master doc as the single source of product truth; the JSON payload is only request metadata, format/persona guidance, concept selection, and schema control.",
        "Derive benefits, proof, mechanisms, differentiators, exclusions, and priority hierarchy from the product master doc, not from memory or invented claims.",
        "Make obesity and weight-loss intent obvious to a first-time viewer; headline or paired copy must mention weight loss, obesity reduction, excess-weight reduction, or a direct 15-day result framing.",
        "Never include price in on-image copy fields. Do not use currency symbols or words like INR, price, only, discount, off, or MRP.",
        "Use copy_requirements.concept_variation as the selected execution path; copy its selected ids into awareness_stage, concept_angle, and concept_structure.",
        "If copy_requirements.hypothesis exists and type is not none, obey it as the controlled test.",
        "Use any provided hook/proof/CTA guidance only when present in concept_variation.",
        "Write one clean, short, concrete headline. Do not lead headlines with Start, Begin, Kickstart, or Follow.",
        "Keep AM/PM timing, protocol mechanics, and product component names out of the headline; put them in support lines or bullets when needed.",
        "Avoid AI-ad words such as unlock, transform your journey, revolutionary, holistic wellness, game-changing, effortlessly, and tailored solution.",
        "Do a final editor pass: shorten the headline, remove generic phrasing, and ensure supporting copy adds proof, mechanism, or ease instead of repeating the headline.",
        "Prioritize fast visible weight loss, safer natural-feeling differentiation, real proof, and practical ease; do not let digestion or emotional benefits overshadow weight loss.",
    ]
    format_rules = {
        "BA": [
            "For BA format only: never prefix copy with BEFORE:/AFTER: labels or Hindi equivalents.",
            "For BA format only: write explicit split contrast copy. Use 2 or 4 bullets total; bullet 1/2 are left-side struggle state and bullet 3/4 are right-side fix or progress state. If using 2 bullets, bullet 1 is struggle and bullet 2 is fix.",
        ],
        "TEST": [
            "For TEST format only: headline must read like a first-person review line suitable for a quote card, not generic highly-rated phrasing.",
            "For TEST format only: attribution must be role/source-based without personal names. If no real quote is provided, create one believable representative review grounded in persona pain/desire and safe claims.",
        ],
        "FEAT": ["For FEAT format only: make each bullet a different product feature."],
        "HERO": ["For HERO format only: support line must add a second feature or proof lane instead of restating the headline."],
        "UGC": ["For UGC format only: use creator-like clarity, and make support line add a second feature or proof lane instead of restating the headline."],
    }
    return " ".join(base_rules + format_rules.get(fmt, []))


def build_strict_schema_note(fmt: str) -> str:
    fmt = fmt.strip().upper()
    field_map = {
        "HERO": "headline, support_line, cta",
        "UGC": "headline, support_line, cta",
        "BA": "headline, bullets (list), cta",
        "FEAT": "headline, bullets (list), cta",
        "TEST": "headline, attribution, trust_line, cta",
    }
    copy_fields = field_map.get(fmt, "headline, cta")
    return (
        "STRICT_SCHEMA: Return JSON only. Do not include copy_requirements, disclaimers, or extra keys. "
        "persona must be an object with number, name, pain_en, desire_en, friction_en, proof_needed_en, tone_cue_en, "
        "pain_hi, desire_hi, friction_hi, proof_needed_hi, tone_cue_hi. "
        f"For {fmt or 'this'} format, copy.EN and copy.HI must contain only: {copy_fields}."
    )


def build_ad_prompt_tail(fmt: str) -> str:
    fmt = fmt.strip().upper()
    support_target = {
        "BA": "right-side shift",
        "FEAT": "feature stack",
        "TEST": "trust line",
    }.get(fmt, "support line")
    return (
        "Return only valid JSON. No markdown. No extra text.\n"
        "Return one ad only. You may return either a single ad object or an object with default_aspect_ratio and a one-item ads array.\n"
        "Before writing, rely on the product master doc already attached/read in this OpenCode session. Do not ask for the doc again and do not ignore it.\n"
        f"The current {fmt or 'ad'} ad must use a new persuasion angle in both the headline and the {support_target} compared with generated_same_format_so_far.\n"
        "Do not reuse the same angle family or sentence pattern from generated_same_format_so_far.\n"
        "Before writing, read copy_requirements.concept_variation and make the headline/support hierarchy match that chosen concept path.\n"
        "If hook_structure_override is present, the EN headline must visibly match it. For contrast_loop, use a clear but natural contrast word such as but, yet, still, without, before/after, or even with.\n"
        "Final editor pass before JSON: rewrite the headline into a finished human ad line, usually 5-12 words, one central idea only. Move mechanism/proof/timing details into support line or bullets.\n"
        "Use supporting copy to explain why the headline is believable: simple routine, 5-minute ease, doctor-formulated proof, 70,000+ users, 15-day progress, cravings/fullness, digestion support, or less sacrifice.\n"
        "Reject your own first draft if the headline reads like a generic AI slogan, a keyword list, or a paraphrase of supporting copy.\n"
        "Do not return framework labels, rationale, or explanations."
    )


def build_generation_payload_for_llm(context: dict[str, Any]) -> dict[str, Any]:
    compact_ads: list[dict[str, Any]] = []
    for item in context.get("ads") or []:
        if not isinstance(item, dict):
            continue
        fmt = str(item.get("format") or "").strip().upper()
        persona = item.get("persona") if isinstance(item.get("persona"), dict) else {}
        format_rules = item.get("format_rules") if isinstance(item.get("format_rules"), dict) else {}
        copy_requirements = item.get("copy_requirements") if isinstance(item.get("copy_requirements"), dict) else {}
        compact_ads.append(
            {
                "format": fmt,
                "persona": {
                    "persona_number": persona.get("persona_number"),
                    "persona_name": persona.get("persona_name"),
                    "pain_points": persona.get("pain_points") or [],
                    "objections": persona.get("objections") or [],
                    "core_message": persona.get("core_message") or [],
                    "trust_anchors": persona.get("trust_anchors") or [],
                    "english_ready": persona.get("english_ready") or [],
                    "hindi_ready": persona.get("hindi_ready") or [],
                },
                "format_rules": compact_format_rules_for_copy(fmt, format_rules),
                "copy_requirements": copy_requirements,
            }
        )

    requested_plan = []
    for item in compact_ads:
        persona = item.get("persona") if isinstance(item.get("persona"), dict) else {}
        requested_plan.append(
            {
                "format": item.get("format"),
                "persona_number": persona.get("persona_number"),
                "persona_name": persona.get("persona_name"),
            }
        )

    return {
        "generated_at": context.get("generated_at"),
        "run_id": context.get("run_id"),
        "language_mode": context.get("language_mode"),
        "context_source": context.get("context_source"),
        "requested_ad_count": len(compact_ads),
        "requested_plan": requested_plan,
        "product_doc": {
            "attached_in_session": True,
            "source_file": context.get("product_file_path"),
            "instruction": "Read and use the attached product master doc as source of truth for all product claims.",
        },
        "ads": compact_ads,
    }


def validate_generated_copy_payload(copy_json: dict[str, Any], planned_ads: list[dict[str, Any]]) -> str | None:
    ads = copy_json.get("ads") if isinstance(copy_json, dict) else None
    if not isinstance(ads, list):
        return "Generated payload did not include an ads array"
    if len(ads) < len(planned_ads):
        return f"Generated ads count {len(ads)} is lower than planned count {len(planned_ads)}"

    planned_keys = {
        (str(item.get("format") or "").strip().upper(), int((item.get("persona") or {}).get("persona_number") or 0))
        for item in planned_ads
        if isinstance(item, dict) and isinstance(item.get("persona"), dict)
    }
    seen_keys: set[tuple[str, int]] = set()
    for ad in ads:
        if not isinstance(ad, dict):
            return "Generated ads payload contains a non-object item"
        fmt = str(ad.get("format") or "").strip().upper()
        persona = ad.get("persona") if isinstance(ad.get("persona"), dict) else {}
        persona_number = persona.get("number")
        if not isinstance(persona_number, int):
            persona_number = persona.get("persona_number")
        if not isinstance(persona_number, int):
            return f"Generated ad for format {fmt or '?'} is missing persona number"
        seen_keys.add((fmt, persona_number))
        copy = ad.get("copy") if isinstance(ad.get("copy"), dict) else {}
        for lang in ["EN", "HI"]:
            block = copy.get(lang) if isinstance(copy.get(lang), dict) else {}
            if not str(block.get("headline") or "").strip():
                return f"Generated ad {fmt}/P{persona_number} is missing {lang} headline"
            if fmt in {"HERO", "UGC"} and not str(block.get("support_line") or "").strip():
                return f"Generated ad {fmt}/P{persona_number} is missing {lang} support line"
            if fmt in {"BA", "FEAT"}:
                bullets = block.get("bullets") if isinstance(block.get("bullets"), list) else []
                if len([item for item in bullets if isinstance(item, str) and item.strip()]) < 2:
                    return f"Generated ad {fmt}/P{persona_number} has insufficient {lang} bullets"
            if fmt == "TEST" and not str(block.get("attribution") or "").strip():
                return f"Generated ad {fmt}/P{persona_number} is missing {lang} attribution"

    missing = sorted(planned_keys - seen_keys)
    if missing:
        return "Generated payload is missing planned ads: " + ", ".join(f"{fmt}/P{persona}" for fmt, persona in missing)
    return None


def extract_generated_ad_candidate(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    def normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
        cloned = json.loads(json.dumps(candidate, ensure_ascii=False))
        persona = cloned.get("persona") if isinstance(cloned.get("persona"), dict) else {}
        if not isinstance(persona, dict):
            persona = {}
        if not isinstance(persona.get("persona_number"), int) and isinstance(cloned.get("persona_number"), int):
            persona["persona_number"] = cloned.get("persona_number")
        if not isinstance(persona.get("number"), int) and isinstance(cloned.get("persona_number"), int):
            persona["number"] = cloned.get("persona_number")
        if not isinstance(persona.get("persona_name"), str) and isinstance(cloned.get("persona_name"), str):
            persona["persona_name"] = cloned.get("persona_name")
        if not isinstance(persona.get("name"), str) and isinstance(cloned.get("persona_name"), str):
            persona["name"] = cloned.get("persona_name")
        if persona:
            cloned["persona"] = persona
        return cloned

    ads = payload.get("ads")
    if isinstance(ads, list):
        for item in ads:
            if isinstance(item, dict) and item.get("copy"):
                return normalize_candidate(item)
    if payload.get("format") and payload.get("copy"):
        return normalize_candidate(payload)
    return None


def hydrate_generated_ad_candidate(candidate: dict[str, Any], planned_ad: dict[str, Any]) -> dict[str, Any]:
    hydrated = json.loads(json.dumps(candidate, ensure_ascii=False))

    planned_format = str(planned_ad.get("format") or "").strip().upper()
    candidate_format = str(hydrated.get("format") or "").strip().upper()
    hydrated["format"] = candidate_format or planned_format

    planned_persona = planned_ad.get("persona") if isinstance(planned_ad.get("persona"), dict) else {}
    candidate_persona = hydrated.get("persona") if isinstance(hydrated.get("persona"), dict) else {}

    persona_number = candidate_persona.get("number")
    if not isinstance(persona_number, int):
        persona_number = candidate_persona.get("persona_number")
    if not isinstance(persona_number, int):
        planned_number = planned_persona.get("persona_number")
        if isinstance(planned_number, int):
            persona_number = planned_number

    persona_name = candidate_persona.get("name")
    if not isinstance(persona_name, str) or not persona_name.strip():
        persona_name = candidate_persona.get("persona_name")
    if not isinstance(persona_name, str) or not persona_name.strip():
        planned_name = planned_persona.get("persona_name")
        if isinstance(planned_name, str):
            persona_name = planned_name

    merged_persona = dict(candidate_persona)
    if isinstance(persona_number, int):
        merged_persona["number"] = persona_number
        merged_persona["persona_number"] = persona_number
    if isinstance(persona_name, str) and persona_name.strip():
        clean_name = persona_name.strip()
        merged_persona["name"] = clean_name
        merged_persona["persona_name"] = clean_name
    if merged_persona:
        hydrated["persona"] = merged_persona

    copy_payload = hydrated.get("copy") if isinstance(hydrated.get("copy"), dict) else {}
    normalized_copy: dict[str, Any] = {}
    for lang in ["EN", "HI"]:
        lang_block = copy_payload.get(lang)
        normalized_copy[lang] = lang_block if isinstance(lang_block, dict) else {}
    hydrated["copy"] = normalized_copy

    return hydrated


def build_persona_payload(persona_number: int, personas: list[dict[str, Any]]) -> dict[str, Any]:
    persona_name = f"Persona {persona_number}"
    for item in personas:
        if int(item.get("number") or 0) == persona_number:
            name = str(item.get("name") or "").strip()
            if name:
                persona_name = name
            break
    seed = PERSONA_SEED_INPUTS.get(persona_number, {})
    pain = seed.get("pain", "Daily routine feels heavy and hard to sustain.")
    desire = seed.get("desire", "A practical routine that feels easy to follow.")
    friction = seed.get("friction", "Past plans felt too strict and difficult to maintain.")
    proof = seed.get("proof", "Needs clear structure and believable support.")
    tone = seed.get("tone", "practical and confidence-building")

    return {
        "persona_number": persona_number,
        "persona_name": persona_name,
        "pain_points": [pain],
        "trigger_scenarios": [],
        "objections": [friction],
        "language_bank": [],
        "core_message": [desire],
        "grounded_mechanism_map": [],
        "how_kit_solves": [],
        "trust_anchors": [proof],
        "english_ready": [f"Tone cue: {tone}"],
        "hindi_ready": ["टोन संकेत: सरल, भरोसेमंद, व्यावहारिक"],
    }


def read_active_images(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def default_image_sources_file() -> Path:
    if DEFAULT_IMAGE_SOURCES_FILE.exists():
        return DEFAULT_IMAGE_SOURCES_FILE
    return LEGACY_ACTIVE_IMAGES_FILE


def list_input_images() -> list[str]:
    if not INPUT_IMAGES_DIR.exists():
        return []
    allowed = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
    items = [
        p for p in sorted(INPUT_IMAGES_DIR.iterdir())
        if p.is_file() and p.suffix.lower() in allowed
    ]
    return [str(p.relative_to(ROOT)).replace("\\", "/") for p in items]


def store_uploaded_input_images(files: list[UploadFile], clear_existing: bool) -> list[str]:
    ensure_dirs()
    if clear_existing and INPUT_IMAGES_DIR.exists():
        for existing in INPUT_IMAGES_DIR.iterdir():
            if existing.is_file():
                existing.unlink(missing_ok=True)

    allowed = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
    saved: list[str] = []
    for upload in files:
        filename = Path(upload.filename or "").name
        if not filename:
            continue
        ext = Path(filename).suffix.lower()
        if ext not in allowed:
            continue
        target = INPUT_IMAGES_DIR / filename
        counter = 1
        while target.exists():
            target = INPUT_IMAGES_DIR / f"{Path(filename).stem}_{counter}{ext}"
            counter += 1
        data = upload.file.read()
        target.write_bytes(data)
        saved.append(str(target.relative_to(ROOT)).replace("\\", "/"))
    return saved


def _is_opencode_run_cmd(cmd: list[str]) -> bool:
    return bool(cmd) and Path(cmd[0]).name == "opencode" and len(cmd) > 1 and cmd[1] == "run"


def _append_opencode_queue_log(message: str) -> None:
    try:
        OPENCODE_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        with OPENCODE_QUEUE_LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"{now_iso()} {message}\n")
    except OSError:
        pass


def dashboard_subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    playwright_path = "/home/mylappy/.local/lib/python3.12/site-packages"
    if playwright_path not in env.get("PYTHONPATH", ""):
        env["PYTHONPATH"] = playwright_path + ((":" + env["PYTHONPATH"]) if env.get("PYTHONPATH") else "")
    return env


@contextmanager
def _opencode_queue_slot(label: str) -> Iterator[None]:
    OPENCODE_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    queued_at = time.time()
    logged_wait = False
    while True:
        for slot in range(OPENCODE_MAX_CONCURRENT):
            lock_path = OPENCODE_QUEUE_DIR / f"slot_{slot}.lock"
            lock_handle = lock_path.open("a+")
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                lock_handle.close()
                continue
            wait_seconds = time.time() - queued_at
            if wait_seconds >= 0.25:
                _append_opencode_queue_log(f"{label} started slot={slot} wait_seconds={wait_seconds:.1f}")
            try:
                yield
                return
            finally:
                try:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
                finally:
                    lock_handle.close()
        if not logged_wait:
            _append_opencode_queue_log(f"{label} queued max_concurrent={OPENCODE_MAX_CONCURRENT}")
            logged_wait = True
        time.sleep(0.25)


def _run_opencode_queued(cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    with _opencode_queue_slot("command"):
        return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False, env=env)


def run_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dashboard_subprocess_env()
    if _is_opencode_run_cmd(cmd):
        return _run_opencode_queued(cmd, cwd, env)
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False, env=env)


def generated_image_roots() -> list[Path]:
    return [GENERATED_IMAGES_ROOT]


def image_static_route_for_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("generated_images/"):
        return f"/generated_images/{normalized.removeprefix('generated_images/')}"
    return f"/generated_images/{normalized}"


def gemini_debugger_args() -> list[str]:
    address = resolve_gemini_debugger_address()
    return ["--attach-debugger-address", address]


def debugger_endpoint_reachable(address: str) -> bool:
    if not address:
        return False
    url = f"http://{address}/json/version"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def resolve_gemini_debugger_address() -> str:
    configured = str(os.getenv("GEMINI_DEBUGGER_ADDRESS") or "").strip()
    candidates = [configured] if configured else []
    candidates.extend(["127.0.0.1:9222", "localhost:9222", "127.0.0.1:9223", "localhost:9223"])
    for candidate in candidates:
        if candidate and debugger_endpoint_reachable(candidate):
            return candidate
    # No reachable endpoint now: return preferred default so automation script
    # can auto-launch a debuggable Chrome session and continue.
    return configured or "127.0.0.1:9222"


def run_gemini_generation(
    *,
    batch: str,
    prompt_files: list[str],
    aspect_ratio: str,
    image_sources_file: str | None,
    prompt_reference_map: Path | None = None,
    headless: bool = False,
    run_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    aspect_folder = "9_16" if aspect_ratio == "9:16" else "4_5"
    prompt_work_dir = RUNTIME_ROOT / "gemini_selected_prompts" / f"{batch}_{aspect_folder}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    prompt_work_dir.mkdir(parents=True, exist_ok=True)

    starting_prompt_path = ROOT / "input" / "startingprompt.txt"
    starting_prompt = starting_prompt_path.read_text(encoding="utf-8").strip() if starting_prompt_path.exists() else ""
    for prompt_file in prompt_files:
        source = Path(prompt_file)
        if not source.is_absolute():
            source = ROOT / source
        source = source.resolve()
        if not source.exists():
            raise RuntimeError(f"Prompt file not found: {source}")
        prompt_text = source.read_text(encoding="utf-8")
        combined = f"{starting_prompt}\n\n{prompt_text.strip()}\n" if starting_prompt else prompt_text
        (prompt_work_dir / source.name).write_text(combined, encoding="utf-8")

    out_dir = GENERATED_IMAGES_ROOT / batch / f"GEMINI_{aspect_folder}"
    image_source_arg = image_sources_file
    if prompt_reference_map is not None:
        try:
            reference_payload = json.loads(prompt_reference_map.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Could not read prompt reference map: {exc}") from exc
        flattened_sources: list[str] = []
        if isinstance(reference_payload, dict):
            for value in reference_payload.values():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and item.strip() and item.strip() not in flattened_sources:
                            flattened_sources.append(item.strip())
        if flattened_sources:
            source_file = prompt_work_dir / "image_sources.txt"
            source_file.write_text("\n".join(flattened_sources) + "\n", encoding="utf-8")
            image_source_arg = str(source_file)

    cmd = [
        sys.executable,
        "scripts/gemini_web_automation.py",
        "--prompt-dir",
        str(prompt_work_dir),
        "--prompt-glob",
        "*.txt",
        "--out-dir",
        str(out_dir),
        "--timeout",
        str(int(os.getenv("GEMINI_GENERATION_TIMEOUT_SECONDS") or "420")),
        "--manual-login-timeout",
        str(int(os.getenv("GEMINI_MANUAL_LOGIN_TIMEOUT_SECONDS") or "180")),
        "--upload-dir",
        str(INPUT_IMAGES_DIR),
    ]
    if headless:
        cmd.append("--headless")
    if image_source_arg:
        cmd.extend(["--image-source-file", image_source_arg])
    if run_dir is not None:
        hyp_path = run_dir / "context" / "hypothesis_config.json"
        if hyp_path.exists():
            cmd.extend(["--hypothesis-config", str(hyp_path)])

    log_dir = RUNTIME_ROOT / "generation_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"gen_{batch}_{aspect_folder}.log"

    env = dict(os.environ)
    playwright_path = "/home/mylappy/.local/lib/python3.12/site-packages"
    if playwright_path not in env.get("PYTHONPATH", ""):
        env["PYTHONPATH"] = playwright_path + ((":" + env["PYTHONPATH"]) if env.get("PYTHONPATH") else "")

    with open(log_path, "w") as log_file:
        result = subprocess.run(cmd, cwd=str(ROOT), text=True, stdout=log_file, stderr=subprocess.STDOUT, check=False, env=env)

    full_output = log_path.read_text() if log_path.exists() else ""
    result.stdout = full_output
    result.stderr = ""
    return result


def build_multipart_form(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----dashboard{uuid.uuid4().hex}"
    lines: list[bytes] = []

    for key, value in fields.items():
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        lines.append(f"{value}\r\n".encode("utf-8"))

    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    lines.append(f"--{boundary}\r\n".encode("utf-8"))
    lines.append(
        (
            f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8")
    )
    lines.append(file_path.read_bytes())
    lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode("utf-8"))

    body = b"".join(lines)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


def upload_image_to_cloudinary(image_path: Path, cloud_name: str, api_key: str, api_secret: str) -> str:
    if not image_path.exists() or not image_path.is_file():
        raise RuntimeError(f"Image not found for upload: {image_path}")

    timestamp = str(int(time.time()))
    signature_base = f"timestamp={timestamp}{api_secret}"
    signature = hashlib.sha1(signature_base.encode("utf-8")).hexdigest()

    fields = {
        "api_key": api_key,
        "timestamp": timestamp,
        "signature": signature,
    }
    body, content_type = build_multipart_form(fields, "file", image_path)
    upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    req = urllib.request.Request(
        url=upload_url,
        data=body,
        method="POST",
        headers={"Content-Type": content_type},
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        raw = response.read().decode("utf-8")
    payload = json.loads(raw)
    secure_url = str(payload.get("secure_url") or "").strip()
    if not secure_url:
        raise RuntimeError(f"Cloudinary upload did not return secure_url: {payload}")
    return secure_url


def load_batch_image_summary(batch: str) -> list[dict[str, Any]]:
    summary_path = GENERATED_IMAGES_ROOT / batch / "batch_run_summary.json"
    if not summary_path.exists():
        jobs_by_prompt: dict[str, dict[str, Any]] = {}
        for generated_root in generated_image_roots():
            generated_batch_dir = generated_root / batch
            if not generated_batch_dir.exists():
                continue
            for meta_file in sorted(generated_batch_dir.glob("**/*.json")):
                try:
                    payload = json.loads(meta_file.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(payload, dict):
                    continue
                if str(payload.get("record_type") or "").strip() != "generated_image":
                    continue

                prompt_file = str(payload.get("prompt_file_relative") or payload.get("prompt_file") or "").strip().replace("\\", "/")
                saved_file = str(payload.get("saved_file") or "").strip().replace("\\", "/")
                if not prompt_file or not saved_file:
                    continue

                existing = jobs_by_prompt.get(prompt_file)
                if not existing:
                    existing = {
                        "prompt_file": prompt_file,
                        "saved_files": [],
                        "format": payload.get("format"),
                        "language": payload.get("language"),
                        "variation": payload.get("variation"),
                        "task_id": payload.get("task_id"),
                        "prompt_metadata": payload.get("prompt_metadata") or {},
                    }
                    jobs_by_prompt[prompt_file] = existing
                saved_files = existing.get("saved_files")
                if not isinstance(saved_files, list):
                    saved_files = []
                    existing["saved_files"] = saved_files
                if saved_file not in saved_files:
                    saved_files.append(saved_file)

        return list(jobs_by_prompt.values())
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    jobs = summary.get("jobs")
    if isinstance(jobs, list):
        return [job for job in jobs if isinstance(job, dict)]
    return []


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text)


def opencode_discovery_env() -> dict[str, str]:
    env = os.environ.copy()
    default_xdg = Path.home() / ".local" / "share"
    default_auth = default_xdg / "opencode" / "auth.json"

    raw_xdg = env.get("XDG_DATA_HOME", "").strip()
    current_xdg = Path(raw_xdg).expanduser() if raw_xdg else default_xdg
    current_auth = current_xdg / "opencode" / "auth.json"

    if default_auth.exists() and not current_auth.exists():
        env["XDG_DATA_HOME"] = str(default_xdg)
    return env


def run_opencode_discovery_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, check=False, env=opencode_discovery_env())


def list_opencode_models() -> list[str]:
    result = run_opencode_discovery_cmd(["opencode", "models"])
    if result.returncode != 0:
        return []
    lines = [line.strip() for line in strip_ansi(result.stdout).splitlines()]
    return [line for line in lines if line and "/" in line]


def list_opencode_provider_labels() -> list[str]:
    result = run_opencode_discovery_cmd(["opencode", "providers", "list"])
    if result.returncode != 0:
        return []
    lines = [line.strip() for line in strip_ansi(result.stdout).splitlines()]
    labels: list[str] = []
    for line in lines:
        match = re.search(r"[●•]\s+(.+?)\s+(oauth|api|token|key)\b", line, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip()
        else:
            fallback = re.search(r"^[│\s]*[●•]\s+(.+)$", line)
            if not fallback:
                continue
            value = re.sub(r"\s+(oauth|api|token|key)\b.*$", "", fallback.group(1), flags=re.IGNORECASE).strip()
        if value:
            labels.append(value)
    return labels


def provider_id_from_label(label: str) -> str:
    known = {
        "github copilot": "github-copilot",
        "github-copilot": "github-copilot",
        "opencode": "opencode",
    }
    key = label.strip().lower()
    if key in known:
        return known[key]
    return re.sub(r"[^a-z0-9]+", "-", key).strip("-")


def list_models_for_provider(provider: str) -> list[str]:
    result = run_opencode_discovery_cmd(["opencode", "models", provider])
    if result.returncode != 0:
        return []
    lines = [line.strip() for line in strip_ansi(result.stdout).splitlines()]
    return [line for line in lines if line and line.startswith(provider + "/")]


def choose_openai_gpt52(models: list[str]) -> str:
    if not models:
        return ""
    preferred = "openai/gpt-5.2"
    if preferred in models:
        return preferred
    for model in models:
        lower = model.lower()
        if lower.startswith("openai/") and "gpt-5.2" in lower:
            return model
    for model in models:
        if model.lower().startswith("openai/"):
            return model
    non_copilot = [m for m in models if not m.lower().startswith("github-copilot/")]
    if non_copilot:
        return non_copilot[0]
    return models[0]


def sanitize_dashboard_model(selected: str, models: list[str]) -> str:
    chosen = (selected or "").strip()
    if chosen and (not models or chosen in models):
        return chosen
    return choose_openai_gpt52(models)


def build_opencode_catalog() -> dict[str, Any]:
    models = list_opencode_models()
    provider_labels = list_opencode_provider_labels()
    provider_ids = {line.split("/", 1)[0] for line in models}

    known_providers = ["opencode", "openai"]
    for provider in known_providers:
        provider_ids.add(provider)
    for label in provider_labels:
        pid = provider_id_from_label(label)
        if pid:
            provider_ids.add(pid)

    for provider in sorted(provider_ids):
        if any(model.startswith(provider + "/") for model in models):
            continue
        models.extend(list_models_for_provider(provider))

    providers = sorted(provider for provider in provider_ids if provider.lower() != "github-copilot")
    grouped: dict[str, list[str]] = {provider: [] for provider in providers}
    for model in models:
        provider = model.split("/", 1)[0]
        if provider.lower() == "github-copilot":
            continue
        grouped.setdefault(provider, []).append(model)
    for provider in grouped:
        grouped[provider] = sorted(grouped[provider])
    providers_with_models = [provider for provider, values in grouped.items() if values]
    copilot_models = [model for model in models if model.lower().startswith("github-copilot/")]
    if providers_with_models:
        providers = sorted(providers_with_models)
    elif copilot_models:
        providers = ["github-copilot"]
        grouped = {"github-copilot": sorted(copilot_models)}
    default_model = ""
    if models:
        default_model = choose_openai_gpt52(models)
    return {
        "api_url": DEFAULT_OPENCODE_API_URL,
        "providers": providers,
        "provider_labels": provider_labels,
        "models_by_provider": grouped,
        "default_model": default_model,
    }


def parse_json_stdout(result: subprocess.CompletedProcess[str], context: str) -> Any:
    if result.returncode != 0:
        raise RuntimeError(f"{context} failed: {result.stderr.strip() or result.stdout.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{context} returned invalid JSON") from exc


def save_upload(target: Path, upload: UploadFile | None) -> Path | None:
    if upload is None or not upload.filename:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    data = upload.file.read()
    target.write_bytes(data)
    return target


def coalesce_path(uploaded: Path | None, default_path: Path) -> Path:
    return uploaded if uploaded and uploaded.exists() else default_path


def resolve_safe_path(relative_path: str) -> Path:
    candidate = (ROOT / relative_path).resolve()
    if str(candidate).startswith(str(ROOT.resolve())):
        return candidate
    raise HTTPException(status_code=400, detail="Invalid path")


def choose_text(items: list[str], fallback: str) -> str:
    for item in items:
        clean = item.strip()
        if clean:
            return clean
    return fallback


def shorten_copy_line(text: str) -> str:
    return " ".join((text or "").split()).strip()


def strip_internal_marker(text: str) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = re.sub(r"\s*\b\d{4}-\d{2}-(hero|ba|test|feat|ugc)\.?\b", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\(\s*\d+[_-]\d+\s*\)", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def strip_price_tokens(text: str) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = text
    cleaned = re.sub(r"\bINR\b\s*\d+[\d,]*(?:\.\d+)?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[₹$]\s*\d+[\d,]*(?:\.\d+)?", "", cleaned)
    cleaned = re.sub(r"\b\d+[\d,]*(?:\.\d+)?\s*(?:INR|Rs\.?|rupees?)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:price|only|discount|off|mrp)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;:-")
    return cleaned


def strip_ba_panel_label(text: str) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = text.strip()
    cleaned = re.sub(r"^\s*(?:before|after)\s*[:\-]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*(?:पहले|बाद|पहले\s*में|बाद\s*में)\s*[:\-]\s*", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def strip_internal_markers_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    ads = payload.get("ads")
    if not isinstance(ads, list):
        return payload

    for ad in ads:
        if not isinstance(ad, dict):
            continue
        copy = ad.get("copy")
        if not isinstance(copy, dict):
            continue
        for lang in ["EN", "HI"]:
            block = copy.get(lang)
            if not isinstance(block, dict):
                continue
            for key in ["headline", "support_line", "cta", "trust_line", "attribution"]:
                if key in block and isinstance(block.get(key), str):
                    value = strip_internal_marker(block[key])
                    block[key] = strip_price_tokens(value)
            if isinstance(block.get("context_line"), str):
                context_line = strip_price_tokens(strip_internal_marker(block["context_line"]))
                if re.search(r"\bneeds\b|proof needed|tone cue|persona", context_line, flags=re.IGNORECASE):
                    block["context_line"] = ""
                else:
                    block["context_line"] = context_line
            if isinstance(block.get("bullets"), list):
                cleaned_bullets = []
                for item in block["bullets"]:
                    if not isinstance(item, str):
                        continue
                    value = strip_price_tokens(strip_internal_marker(item))
                    if value:
                        cleaned_bullets.append(value)
                block["bullets"] = cleaned_bullets
    return payload


CTA_VARIANTS: dict[str, dict[str, list[str]]] = {
    "EN": {
        "HERO": ["Start Today", "See The 15-Day Plan", "Begin The Kit"],
        "BA": ["See The Shift", "Start The Reset", "View The Change"],
        "TEST": ["See The Proof", "Read The Routine", "Start With Proof"],
        "FEAT": ["View Kit Steps", "See The Protocol", "Check The Steps"],
        "UGC": ["See My Routine", "Watch The Routine", "Try The Steps"],
    },
    "HI": {
        "HERO": ["आज शुरू करें", "15 दिन का प्लान देखें", "किट शुरू करें"],
        "BA": ["बदलाव देखें", "रीसेट शुरू करें", "फर्क देखें"],
        "TEST": ["प्रमाण देखें", "दिनचर्या पढ़ें", "भरोसे से शुरू करें"],
        "FEAT": ["किट कदम देखें", "प्रोटोकॉल देखें", "कदम देखें"],
        "UGC": ["मेरी दिनचर्या देखें", "दिनचर्या देखें", "कदम अपनाएं"],
    },
}


def registry_banlist_values(context: dict[str, Any]) -> set[str]:
    banlist = context.get("banlist") if isinstance(context.get("banlist"), dict) else {}
    buckets = banlist.get("buckets") if isinstance(banlist.get("buckets"), dict) else {}
    values: set[str] = set()
    for arr in buckets.values():
        if not isinstance(arr, list):
            continue
        for item in arr:
            if isinstance(item, str) and item.strip():
                values.add(item.strip())
    registry_path = ROOT / "AD_GENERATION_REGISTRY.JSON"
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception:
            registry = {}
        used_text = ((registry.get("indexes") or {}).get("used_text") or {}) if isinstance(registry, dict) else {}
        if isinstance(used_text, dict):
            for arr in used_text.values():
                if not isinstance(arr, list):
                    continue
                for item in arr:
                    if isinstance(item, str) and item.strip():
                        values.add(item.strip())
    return values


def enforce_unique_ctas(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    ads = payload.get("ads") if isinstance(payload.get("ads"), list) else []
    blocked = registry_banlist_values(context)
    seen: set[str] = set()
    for ad in ads:
        if not isinstance(ad, dict):
            continue
        fmt = _clean_str(ad.get("format")).upper()
        copy = ad.get("copy") if isinstance(ad.get("copy"), dict) else {}
        for lang in ["EN", "HI"]:
            block = copy.get(lang) if isinstance(copy.get(lang), dict) else None
            if not block:
                continue
            current = _clean_str(block.get("cta"))
            if current and current not in seen and current not in blocked:
                seen.add(current)
                continue
            variants = CTA_VARIANTS.get(lang, {}).get(fmt, [])
            chosen = ""
            for candidate in variants:
                if candidate not in seen and candidate not in blocked:
                    chosen = candidate
                    break
            if not chosen:
                # Keep CTA natural if uniqueness pool is exhausted.
                chosen = current or (variants[0] if variants else "See Details")
            block["cta"] = chosen
            seen.add(chosen)
    return payload


PROOF_NOTE_MARKERS = [
    "needs",
    "proof needed",
    "tone cue",
    "persona",
    "non-cure",
    "compliant",
    "weight-support framing",
]


def scrub_on_image_copy(payload: dict[str, Any]) -> dict[str, Any]:
    ads = payload.get("ads") if isinstance(payload.get("ads"), list) else []
    for ad in ads:
        if not isinstance(ad, dict):
            continue
        copy = ad.get("copy") if isinstance(ad.get("copy"), dict) else {}
        for lang in ["EN", "HI"]:
            block = copy.get(lang)
            if not isinstance(block, dict):
                continue
            ctx = block.get("context_line")
            if isinstance(ctx, str) and ctx.strip():
                lowered = ctx.lower()
                if any(marker in lowered for marker in PROOF_NOTE_MARKERS):
                    block.pop("context_line", None)
    return payload


def parse_uniqueness_collisions(error_text: str) -> list[dict[str, Any]]:
    collisions: list[dict[str, Any]] = []
    for raw_line in error_text.splitlines():
        line = raw_line.strip()
        match = re.search(r"ads\[(\d+)\]\.copy\.(EN|HI)\.([a-z_]+)", line)
        if not match:
            continue
        collisions.append(
            {
                "ad_index": int(match.group(1)),
                "language": match.group(2),
                "field": match.group(3),
                "line": line,
            }
        )
    return collisions


def parse_json_object_from_text(content: str) -> dict[str, Any] | None:
    text = (content or "").strip()
    if not text:
        return None

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        try:
            parsed = json.loads(fence.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    decoder = json.JSONDecoder()
    best: dict[str, Any] | None = None
    best_span = -1
    for match in re.finditer(r"\{", text):
        start = match.start()
        try:
            parsed, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        span = end
        if span > best_span:
            best = parsed
            best_span = span
    return best


def parse_opencode_json_output(stdout: str) -> dict[str, Any] | None:
    text_chunks: list[str] = []
    for raw_line in (stdout or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "text":
            continue
        part = event.get("part") or {}
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            text_chunks.append(text.strip())

    if text_chunks:
        parsed = parse_json_object_from_text("\n".join(text_chunks).strip())
        if parsed is not None:
            return parsed

    return parse_json_object_from_text((stdout or "").strip())


def _find_session_id(value: Any, session_scoped: bool = False) -> str | None:
    if isinstance(value, dict):
        event_type = str(value.get("type") or "").lower()
        scoped = session_scoped or "session" in event_type
        for key in ("sessionID", "sessionId", "session_id"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        if scoped:
            candidate = value.get("id")
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for key, nested in value.items():
            nested_scoped = scoped or "session" in str(key).lower()
            found = _find_session_id(nested, nested_scoped)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_session_id(item, session_scoped)
            if found:
                return found
    return None


def parse_opencode_session_id(stdout: str) -> str | None:
    for raw_line in (stdout or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        found = _find_session_id(event)
        if found:
            return found

    match = re.search(r'"session(?:ID|Id|_id)"\s*:\s*"([^"]+)"', stdout or "")
    if match:
        return match.group(1).strip()
    return None


def build_product_doc_bootstrap_prompt() -> str:
    return (
        "Read the attached product master doc completely. For every following ad-copy request in this same OpenCode session, "
        "use that doc as the single source of product truth for benefits, proof, mechanism, differentiators, exclusions, and priority hierarchy. "
        "Do not rewrite, summarize, modify, or ignore the doc. The following messages will provide only ad format/persona/concept/schema instructions. "
        "Return only valid JSON: {\"status\":\"product_doc_loaded\"}."
    )


def append_run_log(run_dir: Path, filename: str, message: str) -> None:
    log_path = run_dir / "logs" / filename
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def call_opencode_repair_copy(
    config: dict[str, Any],
    context: dict[str, Any],
    current_copy: dict[str, Any],
    collisions: list[dict[str, Any]],
    run_dir: Path,
) -> dict[str, Any] | None:
    api_url = (config.get("opencode_api_url") or "").strip()
    model = sanitize_dashboard_model((config.get("opencode_model") or "").strip(), list_opencode_models())
    if not api_url:
        return None

    payload = {
        "task": "Repair uniqueness collisions only",
        "rules": [
            "Return valid JSON only",
            "Keep existing structure and fields",
            "Only change collided fields",
            "Do not use generic repeated support lines",
            "Do not add internal tags or IDs",
        ],
        "collisions": collisions,
        "current_copy": current_copy,
        "context": build_generation_payload_for_llm(context),
    }
    prompt = (
        "You are fixing ad copy JSON after uniqueness collisions. "
        "Return only corrected JSON object with keys default_aspect_ratio and ads.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    password = (config.get("opencode_api_key") or "").strip() or os.getenv("OPENCODE_SERVER_PASSWORD", "").strip()
    cmd = [
        "opencode",
        "run",
        "--pure",
        "--attach",
        api_url,
        "--model",
        model,
        "--format",
        "json",
        prompt,
    ]
    if password:
        cmd.extend(["--password", password])
    try:
        result = run_cmd(cmd, cwd=ROOT)
    except OSError as exc:
        (run_dir / "logs" / "opencode_repair_error.txt").write_text(
            f"Repair command launch failed: {exc}", encoding="utf-8"
        )
        return None
    if result.returncode != 0:
        (run_dir / "logs" / "opencode_repair_error.txt").write_text(
            f"Repair command failed\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}", encoding="utf-8"
        )
        return None

    return parse_opencode_json_output(result.stdout)


def _clean_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _clean_bullets(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def concept_ids_from_requirements(copy_req: dict[str, Any]) -> dict[str, str]:
    concept = copy_req.get("concept_variation") if isinstance(copy_req.get("concept_variation"), dict) else {}

    def nested_id(key: str, fallback: str) -> str:
        item = concept.get(key) if isinstance(concept.get(key), dict) else {}
        value = item.get("id") if isinstance(item, dict) else ""
        return _clean_str(value) or fallback

    return {
        "awareness_stage": nested_id("audience_stage", "problem_aware"),
        "concept_angle": nested_id("lead_angle", "desired_outcome"),
        "concept_structure": nested_id("message_structure", "four_us"),
    }


# Feature template copy removed. Deterministic fallback should not hardcode headline/support “lanes”.


# Deterministic template helpers removed with feature template copy.


def ensure_testimonial_headline(headline: str, lang: str, persona: dict[str, Any]) -> str:
    clean = shorten_copy_line(headline)
    if lang == "EN":
        if re.search(r"\b(i|i'm|i’ve|i'd|my|me)\b", clean, flags=re.IGNORECASE):
            if re.search(r"\b(weight|obesity|excess\s*weight|kg|kilo)\b", clean, flags=re.IGNORECASE):
                return clean
            return shorten_copy_line(f'{clean.rstrip(".")}. It finally fit my weight-loss routine.')
        desire = _clean_str(persona.get("desire_en")).rstrip(".")
        if desire:
            desire_phrase = desire[:1].lower() + desire[1:] if len(desire) > 1 else desire.lower()
            return shorten_copy_line(f'"I finally found {desire_phrase} for my weight-loss goal."')
        return '"I finally found a routine I can follow for weight loss every day."'

    if re.search(r"(मैं|मेरी|मेरा|मुझे|मैंने)", clean):
        if re.search(r"(वजन|मोटापा|किलो|kg)", clean):
            return clean
        return shorten_copy_line(f'{clean.rstrip("।")}। यह मेरे वजन घटाने के लिए काम आया।')
    desire_hi = _clean_str(persona.get("desire_hi")).rstrip("।")
    if desire_hi:
        return shorten_copy_line(f'"मुझे आखिर {desire_hi} वाला रूटीन मिला जो वजन घटाने में मदद करता है।"')
    return '"मुझे आखिर ऐसा रूटीन मिला जिसे मैं रोज निभा सकूं और वजन घटा सकूं।"'


def ensure_testimonial_attribution(attribution: str, lang: str, persona: dict[str, Any], headline: str, trust_line: str) -> str:
    if lang == "EN":
        variants = [
            "Verified routine user feedback",
            "15-day adherence feedback snapshot",
            "Community obesity-care review",
            "Early weight-loss routine review",
            "Structured-plan user feedback",
            "Repeat-user experience note",
        ]
    else:
        variants = [
            "रूटीन-फॉलो यूजर फीडबैक",
            "15-दिन adherence फीडबैक स्नैपशॉट",
            "कम्युनिटी obesity-care रिव्यू",
            "शुरुआती वजन-घटाने रूटीन रिव्यू",
            "स्ट्रक्चर्ड-प्लान यूजर फीडबैक",
            "रीपीट-यूजर अनुभव नोट",
        ]

    current = _clean_str(attribution)
    seed_input = (
        f"{persona.get('number', '')}|{persona.get('name', '')}|{headline}|{trust_line}|{persona.get('pain_en', '')}|{persona.get('pain_hi', '')}"
    )
    digest = hashlib.sha1(seed_input.encode("utf-8", errors="ignore")).hexdigest()
    idx = int(digest[:8], 16) % len(variants)
    chosen = variants[idx]

    if not current:
        return chosen

    # For TEST attribution we avoid personal names and generic repeated labels.
    if re.search(r"\brepresentative\s+user\s+review\b", current, flags=re.IGNORECASE):
        return chosen
    if re.search(r"\b(user|customer)\s+review\b", current, flags=re.IGNORECASE):
        return chosen
    if re.search(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", current):
        return chosen
    if re.search(r"[\u0900-\u097F]{2,}\s+[\u0900-\u097F]{2,}", current):
        return chosen
    return shorten_copy_line(current)


def _persona_number_from_candidate(candidate: dict[str, Any]) -> int | None:
    persona = candidate.get("persona") if isinstance(candidate, dict) else None
    if not isinstance(persona, dict):
        return None
    val = persona.get("number")
    if isinstance(val, int):
        return val
    val = persona.get("persona_number")
    if isinstance(val, int):
        return val
    if isinstance(val, str) and val.strip().isdigit():
        return int(val.strip())
    return None


def _persona_name_from_candidate(candidate: dict[str, Any]) -> str:
    persona = candidate.get("persona") if isinstance(candidate, dict) else None
    if not isinstance(persona, dict):
        return ""
    return _clean_str(persona.get("name") or persona.get("persona_name") or "")


def normalize_generated_copy(
    generated: dict[str, Any] | None,
    context: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    base = build_template_copy(context, run_id)
    ads_generated = generated.get("ads") if isinstance(generated, dict) else None
    candidates = ads_generated if isinstance(ads_generated, list) else []
    used_indices: set[int] = set()

    def pick_candidate(fmt: str, persona_num: int, persona_name: str) -> dict[str, Any] | None:
        for idx, cand in enumerate(candidates):
            if idx in used_indices or not isinstance(cand, dict):
                continue
            cand_fmt = _clean_str(cand.get("format")).upper()
            if cand_fmt != fmt:
                continue
            cand_num = _persona_number_from_candidate(cand)
            cand_name = _persona_name_from_candidate(cand)
            if cand_num == persona_num or (cand_name and cand_name.lower() == persona_name.lower()):
                used_indices.add(idx)
                return cand

        for idx, cand in enumerate(candidates):
            if idx in used_indices or not isinstance(cand, dict):
                continue
            cand_fmt = _clean_str(cand.get("format")).upper()
            if cand_fmt == fmt:
                used_indices.add(idx)
                return cand
        return None

    for ad in base.get("ads", []):
        fmt = _clean_str(ad.get("format")).upper()
        persona = ad.get("persona") or {}
        persona_num = int(persona.get("number"))
        persona_name = _clean_str(persona.get("name"))
        candidate = pick_candidate(fmt, persona_num, persona_name)
        if not candidate:
            continue

        hypothesis = candidate.get("hypothesis") if isinstance(candidate.get("hypothesis"), dict) else None
        if hypothesis:
            ad["hypothesis"] = hypothesis

        angle = _clean_str(candidate.get("headline_angle"))
        if angle:
            ad["headline_angle"] = angle

        for key in ["awareness_stage", "concept_angle", "concept_structure"]:
            value = _clean_str(candidate.get(key))
            if value:
                ad[key] = value

        cand_copy = candidate.get("copy") if isinstance(candidate.get("copy"), dict) else {}
        for lang in ["EN", "HI"]:
            base_lang = ad["copy"][lang]
            src_lang = cand_copy.get(lang) if isinstance(cand_copy.get(lang), dict) else {}

            headline = _clean_str(src_lang.get("headline"))
            cta = _clean_str(src_lang.get("cta"))
            if headline:
                base_lang["headline"] = shorten_copy_line(headline)
            if cta:
                base_lang["cta"] = cta

            if fmt == "TEST":
                base_lang["headline"] = ensure_testimonial_headline(base_lang.get("headline", ""), lang, persona)
                base_lang["attribution"] = ensure_testimonial_attribution(
                    _clean_str(src_lang.get("attribution")),
                    lang,
                    persona,
                    base_lang.get("headline", ""),
                    _clean_str(src_lang.get("trust_line")) or base_lang.get("trust_line", ""),
                )

            if fmt in {"HERO", "UGC"}:
                support = _clean_str(src_lang.get("support_line"))
                if support:
                    base_lang["support_line"] = shorten_copy_line(support)
            elif fmt in {"BA", "FEAT"}:
                bullets = _clean_bullets(src_lang.get("bullets"))
                if len(bullets) >= 2:
                    if fmt == "BA":
                        bullets = [strip_ba_panel_label(b) for b in bullets]
                    base_lang["bullets"] = [shorten_copy_line(b) for b in bullets]
            else:
                trust = _clean_str(src_lang.get("trust_line"))
                if trust:
                    base_lang["trust_line"] = shorten_copy_line(trust)

    return base


def _template_copy(primary_key: str, secondary_key: str, concept_angle: str, pain: str, lang: str) -> str:
    if lang == "HI":
        return f"{primary_key} का {secondary_key} सिस्टम जो {pain} को संभालने में मदद करता है।"
    return f"A clear {primary_key} system for {secondary_key} that helps manage {pain}."


def template_headline(primary_key: str, concept_angle: str, pain: str, lang: str) -> str:
    return _template_copy(primary_key, concept_angle, concept_angle, pain, lang)


def template_support(primary_key: str, secondary_key: str, lang: str) -> str:
    if lang == "HI":
        return f"सरल कदम, जो {primary_key} और {secondary_key} पर आधारित हैं।"
    return f"Simple steps rooted in {primary_key} and {secondary_key}."


def feature_template(key: str) -> dict[str, str]:
    FEATURES = {
        "structured_system": {"support_en": "Structured system for consistent weight-loss progress.", "support_hi": "लगातार वजन-सपोर्ट के लिए व्यवस्थित सिस्टम।"},
        "cravings_down": {"support_en": "Helps reduce cravings for better daily weight management.", "support_hi": "बेहतर दैनिक वजन-प्रबंधन के लिए लालसा कम करने में सहायक।"},
        "guided_weight_loss": {"support_en": "Guided morning and night steps for visible results.", "support_hi": "दिखने वाले परिणामों के लिए निर्देशित सुबह-रात के कदम।"},
        "natural_ingredients": {"support_en": "Natural Ayurvedic formulation without side effects.", "support_hi": "बिना दुष्प्रभाव के प्राकृतिक आयुर्वेदिक फॉर्मूलेशन।"},
        "easy_routine": {"support_en": "Simple routine that fits into daily life easily.", "support_hi": "रोज़मर्रा की ज़िंदगी में आसानी से फिट होने वाली सरल दिनचर्या।"},
    }
    return FEATURES.get(key, {"support_en": "Structured system for consistent progress.", "support_hi": "लगातार प्रगति के लिए व्यवस्थित सिस्टम।"})


def build_template_copy(context: dict[str, Any], run_id: str) -> dict[str, Any]:
    ads: list[dict[str, Any]] = []
    token = run_id[-4:]
    for idx, item in enumerate(context["ads"], start=1):
        persona = item["persona"]
        fmt = item["format"]
        persona_num = int(persona["persona_number"])
        persona_name = persona["persona_name"]
        unique = f"{token}-{idx:02d}-{fmt.lower()}"
        copy_req = item.get("copy_requirements") if isinstance(item.get("copy_requirements"), dict) else {}
        concept_ids = concept_ids_from_requirements(copy_req)
        primary_key = _clean_str(copy_req.get("primary_feature_key")) or "structured_system"
        secondary_key = _clean_str(copy_req.get("secondary_feature_key")) or "cravings_down"

        pain_en = choose_text(persona.get("pain_points", []), f"Daily routine feels heavy and hard to sustain for persona {persona_num}.")
        desire_en = choose_text(persona.get("core_message", []), "A practical routine that feels easy to follow.")
        friction_en = choose_text(persona.get("objections", []), "Past plans felt too strict and difficult to maintain.")
        proof_en = choose_text(persona.get("trust_anchors", []), "Needs proof through clear structure and believable support.")
        tone_en = "Practical, empathetic, and confidence-building"

        pain_hi = "रोज की वजन-घटाने की दिनचर्या टूटना आसान है।"
        desire_hi = "ऐसा आसान सिस्टम चाहिए जो रोज निभ सके।"
        friction_hi = "पहले के प्लान बहुत सख्त और मुश्किल थे।"
        proof_hi = "साफ कदम, भरोसेमंद सपोर्ट और व्यावहारिक प्रमाण चाहिए।"
        tone_hi = "सरल, भरोसेमंद, और व्यावहारिक"

        concept_angle = concept_ids["concept_angle"]
        headline_en = template_headline(primary_key, concept_angle, pain_en, "EN")
        headline_hi = template_headline(primary_key, concept_angle, pain_en, "HI")
        if fmt == "BA":
            headline_en = "A clear kit routine beats random dieting."
            headline_hi = "साफ किट दिनचर्या अनियमित डाइटिंग से बेहतर है।"
        elif fmt == "FEAT":
            headline_en = "Three kit steps support 15-day weight loss."
            headline_hi = "तीन किट कदम 15 दिन के वजन-सपोर्ट में मदद करते हैं।"
        elif fmt == "UGC":
            headline_en = "Late-night cravings can feel easier to control."
            headline_hi = "रात की लालसा नियंत्रित करना आसान लग सकता है।"
        cta_by_format = {
            "HERO": ("Start Today", "आज शुरू करें"),
            "BA": ("See The Shift", "बदलाव देखें"),
            "TEST": ("See The Proof", "प्रमाण देखें"),
            "FEAT": ("View Kit Steps", "किट कदम देखें"),
            "UGC": ("See My Routine", "मेरी दिनचर्या देखें"),
        }
        cta_en, cta_hi = cta_by_format.get(fmt, ("Start Today", "आज शुरू करें"))
        if fmt == "TEST":
            headline_en = shorten_copy_line(f"I trusted the 15-day kit because the steps felt clear for weight loss.")
            headline_hi = "मैंने 15 दिन की किट पर भरोसा किया क्योंकि वजन-घटाने के कदम साफ लगे।"

        copy_en: dict[str, Any]
        copy_hi: dict[str, Any]
        if fmt in {"HERO", "UGC"}:
            support_en = template_support(primary_key, secondary_key, "EN")
            support_hi = template_support(primary_key, secondary_key, "HI")
            if fmt == "UGC":
                support_en = "A simple first step helps keep late-night weight-loss control practical."
                support_hi = "एक सरल पहला कदम रात के वजन-नियंत्रण को व्यावहारिक रखता है।"
            copy_en = {"headline": headline_en, "support_line": support_en, "cta": cta_en}
            copy_hi = {"headline": headline_hi, "support_line": support_hi, "cta": cta_hi}
        elif fmt == "BA":
            bullets_en = [
                pain_en.rstrip("."),
                friction_en.rstrip("."),
                feature_template(primary_key)["support_en"].rstrip("."),
                feature_template(secondary_key)["support_en"].rstrip("."),
            ]
            bullets_hi = [
                pain_hi.rstrip("।"),
                friction_hi.rstrip("।"),
                feature_template(primary_key)["support_hi"].rstrip("।"),
                feature_template(secondary_key)["support_hi"].rstrip("।"),
            ]
            copy_en = {"headline": headline_en, "bullets": bullets_en, "cta": cta_en}
            copy_hi = {"headline": headline_hi, "bullets": bullets_hi, "cta": cta_hi}
        elif fmt == "FEAT":
            bullets_en = [
                "Morning OK Liquid helps reduce hunger and random snacking for weight loss.",
                "Night Tablet + Powder support digestion and lighter mornings in obesity routine.",
                "Built for visible 15-day weight-loss support without crash-diet pressure.",
            ]
            bullets_hi = [
                "सुबह का OK Liquid वजन घटाने के लिए भूख और अचानक खाने की आदत कम करने में सहायक है।",
                "रात का Tablet + Powder मोटापा-नियंत्रण दिनचर्या में पाचन-सपोर्ट देता है।",
                "कठोर डाइट दबाव के बिना 15 दिन के वजन-सपोर्ट के लिए बनाया गया।",
            ]
            copy_en = {"headline": headline_en, "bullets": bullets_en, "cta": cta_en}
            copy_hi = {"headline": headline_hi, "bullets": bullets_hi, "cta": cta_hi}
        else:
            copy_en = {
                "headline": headline_en,
                "attribution": "Doctor-formulated Ayurvedic obesity and weight-loss protocol",
                "trust_line": "Structured morning-night steps for visible weight-loss progress and obesity control.",
                "cta": cta_en,
            }
            copy_hi = {
                "headline": headline_hi,
                "attribution": "डॉक्टर-फॉर्मुलेटेड आयुर्वेदिक मोटापा और वजन-घटाने का प्रोटोकॉल",
                "trust_line": "सुबह-रात के स्पष्ट कदमों से वजन घटाने और मोटापा नियंत्रण का भरोसेमंद सपोर्ट।",
                "cta": cta_hi,
            }

        ad_payload = {
            "format": fmt,
            "headline_angle": "mechanism",
            "awareness_stage": concept_ids["awareness_stage"],
            "concept_angle": concept_ids["concept_angle"],
            "concept_structure": concept_ids["concept_structure"],
            "persona": {
                "number": persona_num,
                "name": persona_name,
                "pain_en": pain_en,
                "desire_en": desire_en,
                "friction_en": friction_en,
                "proof_needed_en": proof_en,
                "tone_cue_en": tone_en,
                "pain_hi": pain_hi,
                "desire_hi": desire_hi,
                "friction_hi": friction_hi,
                "proof_needed_hi": proof_hi,
                "tone_cue_hi": tone_hi,
            },
            "copy": {"EN": copy_en, "HI": copy_hi},
        }
        hypothesis = item.get("hypothesis") if isinstance(item.get("hypothesis"), dict) else None
        if hypothesis:
            ad_payload["hypothesis"] = hypothesis
        ads.append(ad_payload)

    return {"default_aspect_ratio": "4:5", "ads": ads}


def call_opencode_compatible(config: dict[str, Any], context: dict[str, Any], run_dir: Path) -> dict[str, Any] | None:
    api_url = (config.get("opencode_api_url") or "").strip()
    api_key = (config.get("opencode_api_key") or "").strip() or os.getenv("OPENCODE_SERVER_PASSWORD", "").strip()
    model = sanitize_dashboard_model((config.get("opencode_model") or "").strip(), list_opencode_models())
    if not api_url:
        return None

    print(f"[call_opencode_compatible] api_url={api_url}, model={model}", file=sys.stderr)

    language_mode = resolve_language_mode(config)
    cli_password = api_key or os.getenv("OPENCODE_SERVER_PASSWORD", "").strip()
    product_file = Path(str(context.get("product_file_path") or DEFAULT_PRODUCT_MASTER))
    generated_ads: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    session_id: str | None = None
    session_fallback_used = False

    if not product_file.exists() or not product_file.is_file():
        errors.append(f"Product master doc missing: {product_file}")
        (run_dir / "logs" / "opencode_error.txt").write_text("\n\n---\n\n".join(errors), encoding="utf-8")
        return None

    env = dashboard_subprocess_env()

    def build_cmd(prompt: str, *, use_session: bool, attach_product_doc: bool) -> list[str]:
        cmd = [
            "opencode",
            "run",
            "--pure",
            "--attach",
            api_url,
            "--model",
            model,
            "--format",
            "json",
        ]
        if use_session and session_id:
            cmd.extend(["--session", session_id])
        if attach_product_doc:
            cmd.extend(["--file", str(product_file)])
        if cli_password:
            cmd.extend(["--password", cli_password])
        cmd.extend(["--", prompt])
        return cmd

    def run_opencode(prompt: str, *, force_file: bool = False) -> tuple[dict[str, Any] | None, str, str, int]:
        use_session = bool(session_id) and not force_file
        cmd = build_cmd(prompt, use_session=use_session, attach_product_doc=force_file or not use_session)
        result = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, check=False, env=env)
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        if result.returncode != 0:
            return None, stdout, stderr, result.returncode
        parsed = parse_opencode_json_output(stdout)
        return (extract_generated_ad_candidate(parsed) if parsed else None), stdout, stderr, result.returncode

    with _opencode_queue_slot(f"copy_session {run_dir.name}"):
        append_run_log(
            run_dir,
            "opencode_session.log",
            f"{now_iso()} Starting OpenCode product-doc session with file: {product_file}",
        )
        bootstrap_cmd = build_cmd(build_product_doc_bootstrap_prompt(), use_session=False, attach_product_doc=True)
        bootstrap = subprocess.run(bootstrap_cmd, cwd=str(ROOT), text=True, capture_output=True, check=False, env=env)
        append_run_log(
            run_dir,
            "opencode_session.log",
            (
                f"{now_iso()} Bootstrap return_code={bootstrap.returncode}\n"
                f"STDOUT:\n{bootstrap.stdout or ''}\nSTDERR:\n{bootstrap.stderr or ''}"
            ),
        )
        if bootstrap.returncode == 0:
            session_id = parse_opencode_session_id(bootstrap.stdout or "")
            if session_id:
                append_run_log(run_dir, "opencode_session.log", f"{now_iso()} Reusing OpenCode session: {session_id}")
            else:
                session_fallback_used = True
                warning = "OpenCode did not expose a session id; falling back to attaching product master doc on every ad request."
                warnings.append(warning)
                append_run_log(run_dir, "opencode_session.log", f"{now_iso()} FALLBACK: {warning}")
        else:
            session_fallback_used = True
            warning = "OpenCode product-doc session bootstrap failed; falling back to attaching product master doc on every ad request."
            warnings.append(warning)
            append_run_log(run_dir, "opencode_session.log", f"{now_iso()} FALLBACK: {warning}")

        for index, ad_item in enumerate(context.get("ads") or [], start=1):
            previous_same_format: list[dict[str, Any]] = []
            target_format = str(ad_item.get("format") or "").strip().upper()
            for prev in generated_ads:
                if not isinstance(prev, dict):
                    continue
                if str(prev.get("format") or "").strip().upper() != target_format:
                    continue
                prev_copy = prev.get("copy") if isinstance(prev.get("copy"), dict) else {}
                prev_en = prev_copy.get("EN") if isinstance(prev_copy.get("EN"), dict) else {}
                previous_same_format.append(
                    {
                        "persona": (prev.get("persona") or {}).get("name") if isinstance(prev.get("persona"), dict) else "",
                        "headline_angle": prev.get("headline_angle"),
                        "headline": prev_en.get("headline"),
                        "support_line": prev_en.get("support_line"),
                        "bullets": prev_en.get("bullets") if isinstance(prev_en.get("bullets"), list) else [],
                    }
                )
            single_context = {
                **context,
                "ads": [ad_item],
            }
            user_payload = {
                "task": "Generate fresh ad copy JSON for provided context.",
                "context": build_generation_payload_for_llm(single_context),
                "generated_same_format_so_far": previous_same_format,
                "constraints": {
                    "language": ["EN", "HI"],
                    "language_mode": language_mode,
                    "format": target_format,
                    "return_json_only": True,
                },
            }
            cli_prompt = (
                "SYSTEM:\n"
                f"{build_ad_copy_system_prompt(target_format)}\n\n"
                "USER_PAYLOAD_JSON:\n"
                f"{json.dumps(user_payload, ensure_ascii=False)}\n\n"
                f"{build_ad_prompt_tail(target_format)}"
            )

            try:
                candidate, last_stdout, last_stderr, last_code = run_opencode(cli_prompt)
            except OSError as exc:
                errors.append(f"Ad {index}: launch failed: {exc}")
                continue

            if last_code != 0 and session_id:
                session_id = None
                session_fallback_used = True
                warning = f"OpenCode reusable session failed on ad {index}; falling back to product-doc file attachment for remaining requests."
                warnings.append(f"{warning}\nSTDOUT:\n{last_stdout}\nSTDERR:\n{last_stderr}")
                append_run_log(run_dir, "opencode_session.log", f"{now_iso()} FALLBACK: {warning}")
                candidate, last_stdout, last_stderr, last_code = run_opencode(cli_prompt, force_file=True)

            if not candidate:
                retry_prompt = f"{cli_prompt}\n\n{build_strict_schema_note(target_format)}\n"
                candidate, last_stdout, last_stderr, last_code = run_opencode(retry_prompt, force_file=session_fallback_used and not session_id)

            mismatch = hypothesis_mismatch(candidate, ad_item) if candidate else None
            if mismatch:
                retry_prompt = (
                    f"{cli_prompt}\n\n"
                    f"REVISION_REQUIRED: {mismatch}\n"
                    "Rewrite only this ad so it satisfies the requested hypothesis while keeping schema valid.\n"
                )
                candidate, last_stdout, last_stderr, last_code = run_opencode(retry_prompt, force_file=session_fallback_used and not session_id)
                mismatch_after = hypothesis_mismatch(candidate, ad_item) if candidate else None
                if mismatch_after:
                    warnings.append(f"Ad {index}: hypothesis retry mismatch persisted; accepting generated copy: {mismatch_after}\nSTDOUT:\n{last_stdout}\nSTDERR:\n{last_stderr}")

            if not candidate:
                errors.append(f"Ad {index}: returned no usable ad JSON; return code {last_code}\nSTDOUT:\n{last_stdout}\nSTDERR:\n{last_stderr}")
                continue
            generated_ads.append(hydrate_generated_ad_candidate(candidate, ad_item))

    if errors or warnings:
        (run_dir / "logs" / "opencode_error.txt").write_text("\n\n---\n\n".join(errors + warnings), encoding="utf-8")

    if not generated_ads:
        return None

    result_payload: dict[str, Any] = {"default_aspect_ratio": "4:5", "ads": generated_ads}
    if errors:
        result_payload["_opencode_failures"] = errors
    if warnings:
        result_payload["_opencode_warnings"] = warnings
    if session_fallback_used:
        result_payload["_opencode_session_fallback"] = True
    return result_payload


def collect_run_result(run_dir: Path, batch_name: str, image_generated: bool) -> dict[str, Any]:
    output_dir = ROOT / "output" / batch_name
    prompt_files = []
    if output_dir.exists():
        for file in sorted(output_dir.glob("**/OUTPUT_*.txt")):
            prompt_files.append(str(file.relative_to(ROOT)))

    image_files: list[str] = []
    if image_generated:
        for generated_root in generated_image_roots():
            image_dir = generated_root / batch_name
            if not image_dir.exists():
                continue
            for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                for file in sorted(image_dir.glob(f"**/{ext}")):
                    image_files.append(str(file.relative_to(ROOT)))

    result = {
        "run_id": run_dir.name,
        "batch": batch_name,
        "prompt_files": prompt_files,
        "image_files": image_files,
        "image_generated": image_generated,
        "updated_at": now_iso(),
    }
    (run_dir / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _collect_aspect_ratio_images(batch_name: str, aspect_ratio: str) -> list[str]:
    """Collect generated image paths for a specific aspect ratio.

    Searches both legacy and new unified output roots, looking under
    generated_images/{batch}/GEMINI_{aspect}/ for image files recursively.
    """
    aspect_folder = "GEMINI_4_5" if aspect_ratio == "4:5" else "GEMINI_9_16"
    image_files: list[str] = []
    for generated_root in generated_image_roots():
        image_dir = generated_root / batch_name / aspect_folder
        if not image_dir.exists():
            continue
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            for file in sorted(image_dir.glob(f"**/{ext}")):
                image_files.append(str(file.relative_to(ROOT)))
    return image_files


def _write_generation_metadata(run_dir: Path, batch: str, aspect_ratio: str,
                                manifest: dict[str, Any]) -> None:
    """Write generation_metadata.json alongside generated images with persona,
    format, hypothesis and run-level context."""
    aspect_folder = "GEMINI_4_5" if aspect_ratio == "4:5" else "GEMINI_9_16"
    meta_dir = GENERATED_IMAGES_ROOT / batch / aspect_folder / "generated images"
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta_path = meta_dir / "generation_metadata.json"

    # Load hypothesis config if it exists
    hypothesis_cfg: dict[str, Any] = {}
    hyp_path = run_dir / "context" / "hypothesis_config.json"
    if hyp_path.exists():
        try:
            hypothesis_cfg = json.loads(hyp_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    metadata = {
        "batch": batch,
        "aspect_ratio": aspect_ratio,
        "run_id": run_dir.name,
        "personas": manifest.get("prompt_files", []),
        "hypothesis": hypothesis_cfg,
        "image_files": sorted(
            p for p in manifest.get("image_files", [])
            if f"/{aspect_folder}/" in p
        ),
        "generated_at": now_iso(),
    }
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def scan_prompt_files_for_batch(batch_name: str) -> list[str]:
    output_dir = ROOT / "output" / batch_name
    prompt_files: list[str] = []
    if not output_dir.exists():
        return prompt_files
    for file in sorted(output_dir.glob("**/OUTPUT_*.txt")):
        prompt_files.append(str(file.relative_to(ROOT)))
    return prompt_files


def scan_image_files_for_batch(batch_name: str) -> list[str]:
    image_files: list[str] = []
    seen: set[str] = set()
    for generated_root in generated_image_roots():
        image_dir = generated_root / batch_name
        if not image_dir.exists():
            continue
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            for file in sorted(image_dir.glob(f"**/{ext}")):
                rel = str(file.relative_to(ROOT)).replace("\\", "/")
                if "/.browser_downloads/" in rel:
                    continue
                if rel in seen:
                    continue
                seen.add(rel)
                image_files.append(rel)
    return image_files


def refresh_manifest_file_state(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    batch_name = str(manifest.get("batch") or "").strip()
    if not batch_name:
        return manifest

    prompt_files = scan_prompt_files_for_batch(batch_name)
    image_files = scan_image_files_for_batch(batch_name)
    refreshed = {
        "run_id": run_dir.name,
        "batch": batch_name,
        "prompt_files": prompt_files,
        "image_files": image_files,
        "image_generated": bool(image_files) or bool(manifest.get("image_generated", False)),
        "updated_at": now_iso(),
    }
    merged = {**manifest, **refreshed}
    (run_dir / "manifest.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return merged


def force_aspect_ratio(copy_json: dict[str, Any], aspect_ratio: str) -> dict[str, Any]:
    cloned = json.loads(json.dumps(copy_json, ensure_ascii=False))
    cloned["default_aspect_ratio"] = aspect_ratio
    ads = cloned.get("ads")
    if isinstance(ads, list):
        for ad in ads:
            if isinstance(ad, dict):
                ad["aspect_ratio"] = aspect_ratio
    return cloned


def _parse_prompt_field(prompt_text: str, label: str) -> str:
    match = re.search(rf"^\s*-\s*{re.escape(label)}:\s*(.+)$", prompt_text, flags=re.MULTILINE)
    return (match.group(1).strip() if match else "")


def parse_background_lock_from_prompt(prompt_text: str) -> tuple[str, int] | None:
    slot_match = re.search(r"^\s*-\s*Background\s+slot:\s*(BG-\d{3})\b", prompt_text, flags=re.MULTILINE | re.IGNORECASE)
    seed_match = re.search(r"^\s*-\s*Background\s+seed:\s*(\d+)\s*$", prompt_text, flags=re.MULTILINE | re.IGNORECASE)
    if not slot_match or not seed_match:
        return None
    return (slot_match.group(1).upper(), int(seed_match.group(1)))


def parse_prompt_filename(prompt_path: str) -> tuple[str, str, int | None] | None:
    name = Path(prompt_path).name
    match = re.match(r"^OUTPUT_([A-Z]+)(?:_P(\d+))?_(EN|HI)(?:_V\d+)?\.txt$", name)
    if not match:
        return None
    persona_raw = match.group(2)
    persona_number = int(persona_raw) if persona_raw else None
    return (match.group(1), match.group(3), persona_number)


def parse_persona_number_from_prompt(prompt_text: str) -> int | None:
    match = re.search(r"\(\s*Persona\s*(\d+)\s*\)", prompt_text, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def extract_on_image_copy_lines(prompt_text: str) -> list[dict[str, str]]:
    """
    Legacy-ish extractor used by the dashboard editor.

    It DOES NOT preserve exact spacing/linebreaks; it trims lines into {label,value}.
    Keep this for backward compatibility.
    """
    block = re.search(
        r"EXACT ON-IMAGE COPY - DO NOT ALTER ANYTHING\s*\n(.+?)\n\s*Render every character exactly as written",
        prompt_text,
        flags=re.DOTALL,
    )
    if not block:
        return []

    out: list[dict[str, str]] = []
    for line in block.group(1).splitlines():
        raw = line.strip()
        if not raw:
            continue
        parsed = re.match(r"^-\s*([^:]+):\s*(.*)$", raw)
        if not parsed:
            continue
        out.append({"label": parsed.group(1).strip(), "value": parsed.group(2).strip()})
    return out


def extract_exact_on_image_copy_block(prompt_text: str, *, warn_log_path: Path | None = None) -> str | None:
    """
    Task 5: Extract ONLY the content inside:
      EXACT ON-IMAGE COPY - DO NOT ALTER ANYTHING
      ...
      Render every character exactly as written

    Rules:
    - preserve exact text including punctuation/case/spacing/line breaks
    - no normalization (no strip, no join)
    - if block missing: optionally log warning; return None
    """
    pattern = (
        r"EXACT ON-IMAGE COPY - DO NOT ALTER ANYTHING\s*\n"
        r"(?P<block>.+?)\n\s*Render every character exactly as written"
    )
    m = re.search(pattern, prompt_text, flags=re.DOTALL)
    if not m:
        if warn_log_path is not None:
            warn_log_path.parent.mkdir(parents=True, exist_ok=True)
            warn_log_path.write_text(
                "WARNING: EXACT ON-IMAGE COPY block missing; skipping this prompt.\n",
                encoding="utf-8",
            )
        return None

    # Return exactly what was captured: no strip().
    return m.group("block")


def load_run_language_mode(run_dir: Path) -> str:
    run_context_path = run_dir / "context" / "run_context.json"
    assembler_mode = "BOTH"
    if not run_context_path.exists():
        return assembler_mode
    try:
        run_context = json.loads(run_context_path.read_text(encoding="utf-8"))
        lang_mode = str(run_context.get("language_mode") or "ALL").upper()
        if lang_mode == "EN":
            return "EN"
        if lang_mode == "HI":
            return "HI"
    except Exception:
        return assembler_mode
    return assembler_mode


def rerender_prompts_for_run(run_dir: Path, batch: str, copy_file: Path, language_mode: str) -> None:
    result = run_cmd(
        [
            "python3",
            "scripts/generate_ads.py",
            "--copy-file",
            str(copy_file),
            "--batch",
            batch,
            "--language-mode",
            language_mode,
            "--no-registry-write",
            "--skip-uniqueness-check",
        ],
        cwd=ROOT,
    )
    if result.returncode != 0:
        error_text = result.stderr or result.stdout
        (run_dir / "logs" / "assembler_edit_error.txt").write_text(error_text, encoding="utf-8")
        short_error = "\n".join([line for line in error_text.splitlines() if line.strip()][-12:])
        raise HTTPException(status_code=500, detail=f"Prompt regeneration failed: {short_error}")


def merge_manifest(run_dir: Path, previous_manifest: dict[str, Any], refreshed: dict[str, Any]) -> dict[str, Any]:
    merged = {**previous_manifest, **refreshed}
    (run_dir / "manifest.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return merged


def generate_916_for_run(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    copy_path = run_dir / "context" / "copy_batch.json"
    if not copy_path.exists():
        raise HTTPException(status_code=404, detail="copy_batch.json not found for run")

    batch = (manifest.get("batch") or "").strip()
    if not batch:
        raise HTTPException(status_code=400, detail="Run has no batch folder")

    copy_json = json.loads(copy_path.read_text(encoding="utf-8"))
    copy_916 = force_aspect_ratio(copy_json, "9:16")
    visual_locks = collect_45_visual_locks(batch)
    if visual_locks:
        copy_916 = apply_visual_locks(copy_916, visual_locks)
    copy_916_path = run_dir / "context" / "copy_batch_916.json"
    copy_916_path.write_text(json.dumps(copy_916, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    assembler_mode = load_run_language_mode(run_dir)
    result = run_cmd(
        [
            "python3",
            "scripts/generate_ads.py",
            "--copy-file",
            str(copy_916_path),
            "--batch",
            batch,
            "--language-mode",
            assembler_mode,
            "--no-registry-write",
            "--skip-uniqueness-check",
        ],
        cwd=ROOT,
    )

    if result.returncode != 0:
        error_text = result.stderr or result.stdout
        (run_dir / "logs" / "assembler_916_error.txt").write_text(error_text, encoding="utf-8")
        short_error = "\n".join([line for line in error_text.splitlines() if line.strip()][-12:])
        raise HTTPException(status_code=500, detail=f"9:16 generation failed: {short_error}")

    refreshed = collect_run_result(run_dir, batch, bool(manifest.get("image_generated", False)))
    refreshed["generated_variant"] = "9:16"
    return merge_manifest(run_dir, manifest, refreshed)


def collect_45_visual_locks(batch: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    ratio_dir = ROOT / "output" / batch / "45"
    if not ratio_dir.exists():
        return out
    for prompt_file in sorted(ratio_dir.glob("OUTPUT_*_EN.txt")) + sorted(ratio_dir.glob("OUTPUT_*_HI.txt")):
        parsed = parse_prompt_filename(prompt_file.name)
        if not parsed:
            continue
        fmt, _lang, persona_number = parsed
        key = f"{fmt}::P{persona_number}" if isinstance(persona_number, int) else fmt
        current = out.get(key, {})
        text = prompt_file.read_text(encoding="utf-8", errors="ignore")
        if persona_number is None:
            inferred = parse_persona_number_from_prompt(text)
            if isinstance(inferred, int):
                persona_number = inferred
                key = f"{fmt}::P{persona_number}"
                current = out.get(key, current)
        lock = parse_background_lock_from_prompt(text)
        if lock:
            current["background_slot"] = lock[0]
            current["background_seed"] = lock[1]

        visual_lock = {
            "seeded_background_direction": _parse_prompt_field(text, "Seeded background direction (single sentence, exact)"),
            "subject": _parse_prompt_field(text, "Subject"),
            "action": _parse_prompt_field(text, "Action"),
            "camera": _parse_prompt_field(text, "Camera"),
            "lighting": _parse_prompt_field(text, "Lighting"),
            "props": _parse_prompt_field(text, "Props"),
            "surfaces": _parse_prompt_field(text, "Surfaces"),
            "mood": _parse_prompt_field(text, "Mood"),
            "realism": _parse_prompt_field(text, "Realism"),
        }
        visual_lock = {k: v for k, v in visual_lock.items() if v}
        if visual_lock:
            current["visual_lock"] = visual_lock

        if current:
            out[key] = current
    return out


def apply_visual_locks(copy_json: dict[str, Any], locks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cloned = json.loads(json.dumps(copy_json, ensure_ascii=False))
    ads = cloned.get("ads")
    if not isinstance(ads, list):
        return cloned
    for ad in ads:
        if not isinstance(ad, dict):
            continue
        fmt = str(ad.get("format") or "").strip().upper()
        persona_no = None
        persona = ad.get("persona")
        if isinstance(persona, dict):
            raw_no = persona.get("number")
            if isinstance(raw_no, int):
                persona_no = raw_no
        lock_key = f"{fmt}::P{persona_no}" if isinstance(persona_no, int) else ""
        lock = (locks.get(lock_key) if lock_key else None) or locks.get(fmt) or {}
        if not lock:
            continue
        if isinstance(lock.get("background_slot"), str):
            ad["background_slot"] = lock["background_slot"]
        if isinstance(lock.get("background_seed"), int):
            ad["background_seed"] = lock["background_seed"]
        if isinstance(lock.get("visual_lock"), dict):
            ad["visual_lock"] = lock["visual_lock"]
    return cloned


def resolve_format_plan(config: dict[str, Any]) -> list[dict[str, Any]]:
    personas = config.get("selected_personas") or []
    if not personas:
        raise RuntimeError("selected_personas is required")

    all_formats = [fmt for fmt in (config.get("global_formats") or []) if fmt in FORMATS]
    format_map = config.get("formats_by_persona") or {}

    out: list[dict[str, Any]] = []
    for raw_persona in personas:
        persona_num = int(raw_persona)
        per_formats = [fmt for fmt in (format_map.get(str(persona_num)) or format_map.get(persona_num) or []) if fmt in FORMATS]
        formats = per_formats if per_formats else all_formats
        if not formats:
            formats = ["HERO"]
        for fmt in formats:
            out.append({"persona": persona_num, "format": fmt})
    return out


def expand_plan_with_hypothesis(plan: list[dict[str, Any]], hypothesis_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand ad plan to include hypothesis style.

    When a hypothesis is active, generates ads using that specific style/variant.
    """
    hyp_type = str(hypothesis_cfg.get("type") or "none").strip().lower()
    if hyp_type == "none" or hyp_type not in HYPOTHESIS_VARIABLES:
        return plan

    variable_def = HYPOTHESIS_VARIABLES[hyp_type]
    selected_variant = str(hypothesis_cfg.get("variant") or "").strip()
    available_options = [opt["id"] for opt in variable_def.get("options", [])]

    if not available_options:
        return plan

    # Use the selected variant if valid, otherwise use first available
    variant_to_use = selected_variant if selected_variant in available_options else available_options[0]

    out: list[dict[str, Any]] = []
    for item in plan:
        entry = dict(item)
        entry["hypothesis"] = {
            "type": hyp_type,
            "variable_label": variable_def["label"],
            "variant": variant_to_use,
            "hypothesis_id": f"{hyp_type}-{variant_to_use}",
        }
        out.append(entry)
    return out


app = FastAPI(title="Ad Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    load_env_file(ENV_PATH)
    ensure_dirs()


def api_defaults() -> dict[str, Any]:
    personas = parse_persona_library(DEFAULT_PLAYBOOK)
    opencode = build_opencode_catalog()
    return {
        "personas": personas,
        "formats": FORMATS,
        "image_sources": read_active_images(default_image_sources_file()),
        "input_images": list_input_images(),
        "default_files": {
            "product_info": str(DEFAULT_PRODUCT_MASTER.relative_to(ROOT)),
            "playbook": str(DEFAULT_PLAYBOOK.relative_to(ROOT)),
        },
        "opencode": opencode,
        "hypothesis": {
            "variables": HYPOTHESIS_VARIABLES,
            "default": {"type": "none", "variant": ""},
        },
    }


def api_progress(batch_key: str) -> dict[str, Any]:
    batch_key_clean = str(batch_key).strip()
    for root in generated_image_roots():
        log_path = root / batch_key_clean / "_headless_progress.json"
        if not log_path.exists():
            continue
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        entries = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        if not entries:
            continue
        latest = entries[-1]
        return {
            "batch_key": batch_key_clean,
            "step": latest.get("step", ""),
            "message": latest.get("message", ""),
            "time": latest.get("time", 0),
            "entries": entries,
        }
    raise HTTPException(status_code=404, detail=f"No progress found for batch: {batch_key_clean}")


def api_opencode_catalog() -> dict[str, Any]:
    return build_opencode_catalog()


def api_runs() -> dict[str, Any]:
    ensure_dirs()
    runs: list[dict[str, Any]] = []
    seen_run_ids: set[str] = set()
    seen_batches: set[str] = set()
    for run_dir in sorted(RUNS_ROOT.glob("run_*"), reverse=True):
        manifest = run_dir / "manifest.json"
        if manifest.exists():
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            refreshed = refresh_manifest_file_state(run_dir, payload)
            run_id = str(refreshed.get("run_id") or run_dir.name)
            batch = str(refreshed.get("batch") or "").strip()
            if run_id in seen_run_ids:
                continue
            seen_run_ids.add(run_id)
            if batch:
                seen_batches.add(batch)
            runs.append(refreshed)

    # Backfill batches that exist on disk but have no run manifest
    # (e.g., older/generated output imported from another machine).
    output_root = ROOT / "output"
    if output_root.exists():
        for batch_dir in sorted(output_root.glob("v*"), reverse=True):
            if not batch_dir.is_dir():
                continue
            batch_name = batch_dir.name
            if batch_name in seen_batches:
                continue
            prompt_files = scan_prompt_files_for_batch(batch_name)
            if not prompt_files:
                continue
            image_files = scan_image_files_for_batch(batch_name)
            updated_at = datetime.fromtimestamp(batch_dir.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            runs.append(
                {
                    "run_id": f"batch_{batch_name}",
                    "batch": batch_name,
                    "prompt_files": prompt_files,
                    "image_files": image_files,
                    "image_generated": bool(image_files),
                    "updated_at": updated_at,
                    "source": "output_backfill",
                }
            )

    def batch_sort_key(run: dict[str, Any]) -> tuple[int, float]:
        batch = str(run.get("batch") or "").strip().lower()
        match = re.match(r"^v(\d+)$", batch)
        batch_num = int(match.group(1)) if match else -1
        updated = str(run.get("updated_at") or "")
        ts = 0.0
        if updated:
            try:
                ts = datetime.fromisoformat(updated.replace("Z", "+00:00")).timestamp()
            except Exception:
                ts = 0.0
        return (batch_num, ts)

    runs.sort(key=batch_sort_key, reverse=True)
    return {"runs": runs}


def api_run(run_id: str) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest = run_dir / "manifest.json"
    if not manifest.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return refresh_manifest_file_state(run_dir, payload)


def api_run_prompt_copies(run_id: str) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prompt_files_all = manifest.get("prompt_files") or []
    prompt_files = [path for path in prompt_files_all if "/45/" in str(path)] or prompt_files_all
    records: list[dict[str, Any]] = []
    for rel_path in prompt_files:
        prompt_path = ROOT / rel_path
        if not prompt_path.exists() or not prompt_path.is_file():
            continue
        text = prompt_path.read_text(encoding="utf-8", errors="ignore")
        parsed_name = parse_prompt_filename(rel_path)
        persona_number = parsed_name[2] if parsed_name else None
        if persona_number is None:
            persona_number = parse_persona_number_from_prompt(text)
        records.append(
            {
                "prompt_file": rel_path,
                "format": parsed_name[0] if parsed_name else "",
                "language": parsed_name[1] if parsed_name else "",
                "persona_number": persona_number,
                "review_url": "/output/" + rel_path.replace("output/", ""),
                "copy_lines": extract_on_image_copy_lines(text),
            }
        )

    return {"run_id": run_id, "batch": manifest.get("batch"), "prompts": records}


def api_run_update_prompt_copies(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    copy_path = run_dir / "context" / "copy_batch.json"

    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    if not copy_path.exists():
        raise HTTPException(status_code=404, detail="copy_batch.json not found for run")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    batch = (manifest.get("batch") or "").strip()
    if not batch:
        raise HTTPException(status_code=400, detail="Run has no batch folder")

    edits = payload.get("edits")
    if not isinstance(edits, list) or not edits:
        raise HTTPException(status_code=400, detail="edits must be a non-empty array")

    copy_json = json.loads(copy_path.read_text(encoding="utf-8"))
    ads = copy_json.get("ads")
    if not isinstance(ads, list) or not ads:
        raise HTTPException(status_code=400, detail="Invalid copy batch payload")

    updated_count = 0
    for entry in edits:
        if not isinstance(entry, dict):
            continue
        prompt_file = str(entry.get("prompt_file") or "").strip()
        if not prompt_file:
            continue
        parsed_name = parse_prompt_filename(prompt_file)
        if not parsed_name:
            continue
        fmt, lang, parsed_persona = parsed_name
        persona_number = entry.get("persona_number")
        if not isinstance(persona_number, int):
            persona_number = parsed_persona
        line_items = entry.get("copy_lines")
        if not isinstance(line_items, list) or not line_items:
            continue

        target_ad = None
        for ad in ads:
            if not isinstance(ad, dict):
                continue
            if str(ad.get("format") or "").strip().upper() != fmt:
                continue
            if isinstance(persona_number, int):
                persona = ad.get("persona")
                ad_persona_no = None
                if isinstance(persona, dict) and isinstance(persona.get("number"), int):
                    ad_persona_no = int(persona.get("number"))
                if ad_persona_no != persona_number:
                    continue
            target_ad = ad
            break
        if not isinstance(target_ad, dict):
            continue

        ad_copy = target_ad.setdefault("copy", {})
        if not isinstance(ad_copy, dict):
            continue
        lang_copy = ad_copy.setdefault(lang, {})
        if not isinstance(lang_copy, dict):
            continue

        for line_item in line_items:
            if not isinstance(line_item, dict):
                continue
            label = str(line_item.get("label") or "").strip()
            value = str(line_item.get("value") or "").strip()
            if not label:
                continue
            key = label.lower()

            if key == "headline":
                lang_copy["headline"] = value
            elif key == "support line":
                lang_copy["support_line"] = value
            elif key == "context line":
                lang_copy["context_line"] = value
            elif key == "cta":
                lang_copy["cta"] = value
            elif key == "attribution":
                lang_copy["attribution"] = value
            elif key == "trust line":
                lang_copy["trust_line"] = value
            elif key.startswith("bullet "):
                match = re.match(r"^bullet\s+(\d+)$", key)
                if not match:
                    continue
                index = int(match.group(1)) - 1
                if index < 0:
                    continue
                bullets = lang_copy.get("bullets")
                if not isinstance(bullets, list):
                    bullets = []
                while len(bullets) <= index:
                    bullets.append("")
                bullets[index] = value
                lang_copy["bullets"] = bullets
            elif key.startswith("left situation ") or key.startswith("right shift "):
                match = re.match(r"^(left situation|right shift)\s+(\d+)$", key)
                if not match:
                    continue
                side = match.group(1)
                ordinal = int(match.group(2))
                if ordinal <= 0:
                    continue
                if side == "left situation":
                    index = ordinal - 1
                else:
                    index = ordinal + 1
                bullets = lang_copy.get("bullets")
                if not isinstance(bullets, list):
                    bullets = []
                while len(bullets) <= index:
                    bullets.append("")
                bullets[index] = value
                lang_copy["bullets"] = bullets

        updated_count += 1

    if updated_count == 0:
        raise HTTPException(status_code=400, detail="No valid prompt edits were provided")

    copy_path.write_text(json.dumps(copy_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rerender_prompts_for_run(run_dir, batch, copy_path, load_run_language_mode(run_dir))

    _append_audit_log(
        run_dir,
        "prompt_updates",
        {
            "run_id": run_id,
            "batch": batch,
            "updated_count": updated_count,
        },
    )

    has_916 = any("/96/" in str(path) for path in (manifest.get("prompt_files") or []))
    if has_916:
        manifest = generate_916_for_run(run_dir, manifest)

    refreshed = collect_run_result(run_dir, batch, bool(manifest.get("image_generated", False)))
    refreshed["copy_edits_applied"] = updated_count
    merged = merge_manifest(run_dir, manifest, refreshed)
    return merged


# ──────────────────────────────────────────────────────────────────────────────
# Task 6/7/8: Export/Import on-image copy (EXACT ON-IMAGE COPY block)
# ──────────────────────────────────────────────────────────────────────────────

EXACT_COPY_SHEET_COLUMNS = [
    "prompt_id",
    "vn",
    "hypothesis_id",
    "hypothesis_name",
    "persona",
    "angle",
    "headline_copy",
    "exact_on_image_copy_block",
    "created_at",
]

EXACT_COPY_BLOCK_FULL_RE = re.compile(
    r"EXACT ON-IMAGE COPY - DO NOT ALTER ANYTHING\s*\n(?P<block>.+?)\n\s*Render every character exactly as written",
    flags=re.DOTALL,
)


def _extract_vn_from_prompt_rel_path(prompt_rel_path: str) -> str:
    # Expected pattern: output/v{N}/...
    # Keep backward compatible: if not found, return empty string.
    m = re.search(r"/output/(v\d+)(/|$)", prompt_rel_path.replace("\\", "/"))
    return m.group(1) if m else ""


def _extract_created_at_iso_from_file(file_path: Path) -> str:
    try:
        ts = file_path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def _parse_exact_block_headline_value(block_text: str) -> str | None:
    """
    Preserve EXACT headline value text as written in the exact block.

    We intentionally do NOT trim/normalize:
    - keep any spaces immediately after the colon
    - keep punctuation/case/capitalization
    """
    for raw_line in (block_text or "").splitlines():
        # Allow optional whitespace before "-" and around "-", but preserve everything after "Headline:"
        m = re.match(r"^\s*-\s*Headline:(.*)$", raw_line)
        if not m:
            continue
        return m.group(1)
    return None


def _replace_exact_copy_block(prompt_text: str, new_block_text: str) -> str | None:
    m = EXACT_COPY_BLOCK_FULL_RE.search(prompt_text or "")
    if not m:
        return None
    start_idx = m.start("block")
    end_idx = m.end("block")
    return (prompt_text[:start_idx] + new_block_text + prompt_text[end_idx:])


def _load_run_prompt_files(run_id: str, aspect_ratios: list[str] | None = None) -> list[str]:
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prompt_files_all = manifest.get("prompt_files") or []
    if not aspect_ratios:
        return prompt_files_all
    result: list[str] = []
    for p in prompt_files_all:
        for ar in aspect_ratios:
            if f"/{ar}/" in str(p):
                result.append(p)
                break
    return result or prompt_files_all


def _extract_prompt_row_metadata(run_id: str, copy_batch: dict[str, Any], prompt_rel_path: str, batch_vn: str = "") -> dict[str, Any]:
    prompt_path = ROOT / prompt_rel_path
    text = prompt_path.read_text(encoding="utf-8", errors="ignore")

    block = extract_exact_on_image_copy_block(text)
    headline_copy = None
    exact_block = ""
    if block is not None:
        headline_copy = _parse_exact_block_headline_value(block)
        exact_block = block.strip()
    if headline_copy is None:
        headline_copy = ""

    vn = _extract_vn_from_prompt_rel_path(prompt_rel_path)
    if not vn and batch_vn:
        vn = batch_vn
    created_at = _extract_created_at_iso_from_file(prompt_path)

    parsed = parse_prompt_filename(prompt_rel_path)
    fmt = parsed[0] if parsed else ""
    persona_number = parsed[2] if parsed else None
    if persona_number is None:
        persona_number = parse_persona_number_from_prompt(text)

    persona = ""
    angle = ""
    hypothesis_id = ""
    hypothesis_name = ""

    if isinstance(persona_number, int):
        for ad in copy_batch.get("ads") or []:
            if not isinstance(ad, dict):
                continue
            if str(ad.get("format") or "").strip().upper() != fmt:
                continue
            persona = ""
            persona_obj = ad.get("persona")
            if isinstance(persona_obj, dict):
                if isinstance(persona_obj.get("number"), int) and int(persona_obj.get("number")) == persona_number:
                    persona = str(persona_obj.get("persona_name") or persona_obj.get("name") or f"Persona {persona_number}")
            if persona:
                angle = str(ad.get("headline_angle") or ad.get("concept_angle") or "")
                hyp = ad.get("hypothesis") if isinstance(ad.get("hypothesis"), dict) else {}
                if hyp:
                    hypothesis_id = str(hyp.get("hypothesis_id") or "")
                    hypothesis_name = str(hyp.get("variant") or hyp.get("variable_label") or "")
                break

    return {
        "prompt_id": prompt_rel_path,
        "vn": vn,
        "hypothesis_id": hypothesis_id,
        "hypothesis_name": hypothesis_name,
        "persona": persona,
        "angle": angle,
        "headline_copy": headline_copy,
        "exact_on_image_copy_block": exact_block,
        "created_at": created_at,
    }


def _append_audit_log(run_dir: Path, event_type: str, payload: dict[str, Any]) -> None:
    audit_dir = run_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / "audit_log.jsonl"
    entry = {"ts": now_iso(), "event_type": event_type, "payload": payload}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def api_export_on_image_copy(run_id: str) -> StreamingResponse:
    from openpyxl import Workbook
    import io

    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    copy_path = run_dir / "context" / "copy_batch.json"
    if not copy_path.exists():
        raise HTTPException(status_code=404, detail="copy_batch.json not found for run")

    copy_batch = json.loads(copy_path.read_text(encoding="utf-8"))

    prompt_files = _load_run_prompt_files(run_id)

    unique_vns = set()
    for rel in prompt_files:
        prompt_rel_path = str(rel).replace("\\", "/")
        vn = _extract_vn_from_prompt_rel_path(prompt_rel_path)
        if vn:
            unique_vns.add(vn)

    batch = manifest.get("batch", "")

    if not unique_vns:
        if batch and batch.startswith("v"):
            unique_vns.add(batch)

    if unique_vns:
        vn_suffix = "-".join(sorted(unique_vns))
    else:
        vn_suffix = None

    wb = Workbook()
    ws = wb.active
    ws.title = "on-image-copy"

    ws.append(EXACT_COPY_SHEET_COLUMNS)
    for rel in prompt_files:
        prompt_rel_path = str(rel).replace("\\", "/")
        if not (ROOT / prompt_rel_path).exists():
            continue
        row = _extract_prompt_row_metadata(run_id, copy_batch, prompt_rel_path, batch)
        ws.append([row.get(col, "") for col in EXACT_COPY_SHEET_COLUMNS])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    _append_audit_log(run_dir, "export_on_image_copy", {"run_id": run_id, "prompt_rows": len(prompt_files)})

    if vn_suffix:
        filename = f"on-image-copy-{vn_suffix}.xlsx"
    else:
        filename = f"on-image-copy-{run_id}.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def api_import_on_image_copy(
    run_id: str,
    file: UploadFile = File(...),
    confirm: bool = Form(False),
) -> dict[str, Any]:
    from openpyxl import load_workbook

    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    copy_path = run_dir / "context" / "copy_batch.json"
    if not copy_path.exists():
        raise HTTPException(status_code=404, detail="copy_batch.json not found for run")

    # Parse xlsx (no prompt regeneration; only exact-block replacement)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing upload filename")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty upload")

    tmp_path = run_dir / "imports" / f"upload-{int(time.time())}-{file.filename}"
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_bytes(content)

    wb = load_workbook(tmp_path)
    ws = wb.active

    # Build column index
    header = [str(cell.value or "").strip() for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    col_idx = {name: i for i, name in enumerate(header) if name}
    missing_cols = [c for c in EXACT_COPY_SHEET_COLUMNS if c not in col_idx]
    if missing_cols:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {missing_cols}")

    seen_prompt_ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for excel_row in ws.iter_rows(min_row=2):
        values = [cell.value for cell in excel_row]
        prompt_id = str(values[col_idx["prompt_id"]] or "").replace("\\", "/").strip()
        if not prompt_id:
            continue
        if prompt_id in seen_prompt_ids:
            errors.append({"prompt_id": prompt_id, "error": "duplicate_prompt_id"})
            continue
        seen_prompt_ids.add(prompt_id)

        headline_copy = str(values[col_idx["headline_copy"]] or "").strip()
        full_block = str(values[col_idx.get("exact_on_image_copy_block", -1)] or "").strip() if "exact_on_image_copy_block" in col_idx else ""

        if not headline_copy.strip() and not full_block:
            errors.append({"prompt_id": prompt_id, "error": "empty_headline_copy_and_block"})
            continue

        rows.append(
            {
                "prompt_id": prompt_id,
                "headline_copy": headline_copy,
                "full_block": full_block,
            }
        )

    # Validate prompt_id exists
    for r in rows:
        p = ROOT / r["prompt_id"]
        if not p.exists() or not p.is_file():
            errors.append({"prompt_id": r["prompt_id"], "error": "prompt_id_not_found"})
    if errors:
        _append_audit_log(run_dir, "import_on_image_copy_validation_failed", {"run_id": run_id, "errors": errors, "confirm": confirm})
        raise HTTPException(status_code=400, detail={"validation_errors": errors})

    # Preview diffs
    preview_items: list[dict[str, Any]] = []
    applied_count = 0
    skipped_count = 0

    for r in rows:
        prompt_rel_path = r["prompt_id"]
        prompt_path = ROOT / prompt_rel_path
        old_text = prompt_path.read_text(encoding="utf-8", errors="ignore")

        old_block = extract_exact_on_image_copy_block(old_text, warn_log_path=None)
        if old_block is None:
            skipped_count += 1
            preview_items.append({"prompt_id": prompt_rel_path, "status": "skipped_missing_exact_block"})
            continue

        full_block = r.get("full_block", "")
        new_block = None

        if full_block:
            new_block = full_block
            old_copy = old_block.strip()
            new_copy = new_block.strip()
        else:
            headline_copy = r.get("headline_copy", "")
            new_lines: list[str] = []
            headline_replaced = False
            for line in old_block.splitlines():
                m = re.match(r"^(\s*-\s*Headline:)(.*)$", line)
                if m:
                    new_lines.append(m.group(1) + headline_copy)
                    headline_replaced = True
                else:
                    new_lines.append(line)

            if not headline_replaced:
                skipped_count += 1
                preview_items.append({"prompt_id": prompt_rel_path, "status": "skipped_headline_line_not_found"})
                continue

            new_block = "\n".join(new_lines)
            old_copy = _parse_exact_block_headline_value(old_block) or ""
            new_copy = _parse_exact_block_headline_value(new_block) or ""

        preview_items.append(
            {
                "prompt_id": prompt_rel_path,
                "status": "ready_to_apply" if confirm else "preview",
                "old_copy": old_copy[:100] + "..." if len(old_copy) > 100 else old_copy,
                "new_copy": new_copy[:100] + "..." if len(new_copy) > 100 else new_copy,
            }
        )

        if confirm:
            updated_text = _replace_exact_copy_block(old_text, new_block)
            if updated_text is None:
                skipped_count += 1
                preview_items[-1]["status"] = "skipped_replace_failed"
                continue
            prompt_path.write_text(updated_text, encoding="utf-8")
            applied_count += 1

    _append_audit_log(
        run_dir,
        "import_on_image_copy",
        {"run_id": run_id, "confirm": confirm, "rows": len(rows), "applied": applied_count, "skipped": skipped_count},
    )

    if not confirm:
        return {
            "run_id": run_id,
            "preview": True,
            "changed_rows_count": applied_count,
            "skipped_rows": skipped_count,
            "failed_rows": len(errors),
            "items": preview_items,
        }

    # Re-assemble prompts side-effects: since we directly edited prompt text,
    # we do not mutate copy_batch.json metadata (per requirements).
    # However, manifest/prompt_files state should be refreshed.
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    batch = (manifest.get("batch") or "").strip()
    refreshed = collect_run_result(run_dir, batch, bool(manifest.get("image_generated", False)))
    refreshed["on_image_copy_import_applied"] = applied_count
    merged = merge_manifest(run_dir, manifest, refreshed)

    return {
        "run_id": run_id,
        "preview": False,
        "changed_rows_count": applied_count,
        "skipped_rows": skipped_count,
        "failed_rows": len(errors),
        "items": preview_items,
        "manifest": merged,
    }


def api_run_generate_916(run_id: str) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"

    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return generate_916_for_run(run_dir, manifest)


def api_run_generate_916_selected(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    copy_path = run_dir / "context" / "copy_batch.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    if not copy_path.exists():
        raise HTTPException(status_code=404, detail="copy_batch.json not found for run")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    batch = str(manifest.get("batch") or "").strip()
    if not batch:
        raise HTTPException(status_code=400, detail="Run has no batch folder")

    prompt_files = payload.get("prompt_files")
    if not isinstance(prompt_files, list) or not prompt_files:
        raise HTTPException(status_code=400, detail="prompt_files must be a non-empty array")

    selected_45 = validate_selected_45_prompts(batch, prompt_files)
    if not selected_45:
        raise HTTPException(status_code=400, detail="No valid 4:5 prompt files selected")

    selected_keys = extract_selected_ad_keys_from_45_prompts(selected_45)
    if not selected_keys:
        raise HTTPException(status_code=400, detail="Could not resolve selected persona/format keys")

    copy_json = json.loads(copy_path.read_text(encoding="utf-8"))
    selected_copy = filter_copy_json_for_selected_ads(copy_json, selected_keys)
    ads = selected_copy.get("ads")
    if not isinstance(ads, list) or not ads:
        raise HTTPException(status_code=400, detail="No ads matched selected prompts")

    copy_916 = force_aspect_ratio(selected_copy, "9:16")
    visual_locks = collect_45_visual_locks(batch)
    if visual_locks:
        copy_916 = apply_visual_locks(copy_916, visual_locks)
    copy_916_path = run_dir / "context" / "copy_batch_916_selected.json"
    copy_916_path.write_text(json.dumps(copy_916, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = run_cmd(
        [
            "python3",
            "scripts/generate_ads.py",
            "--copy-file",
            str(copy_916_path),
            "--batch",
            batch,
            "--language-mode",
            load_run_language_mode(run_dir),
            "--no-registry-write",
            "--skip-uniqueness-check",
        ],
        cwd=ROOT,
    )
    if result.returncode != 0:
        error_text = result.stderr or result.stdout
        (run_dir / "logs" / "assembler_916_selected_error.txt").write_text(error_text, encoding="utf-8")
        short_error = "\n".join([line for line in error_text.splitlines() if line.strip()][-12:])
        raise HTTPException(status_code=500, detail=f"Selective 9:16 generation failed: {short_error}")

    refreshed = collect_run_result(run_dir, batch, bool(manifest.get("image_generated", False)))
    refreshed["generated_variant"] = "9:16"
    refreshed["generated_916_for_prompts"] = selected_45
    return merge_manifest(run_dir, manifest, refreshed)


def validate_selected_45_prompts(batch: str, prompt_files: list[Any]) -> list[str]:
    valid_prompt_files: list[str] = []
    for prompt_file in prompt_files:
        rel = str(prompt_file or "").strip().replace("\\", "/")
        if not rel or not rel.startswith("output/"):
            continue
        if "/45/" not in rel:
            continue
        candidate = ROOT / rel
        if not candidate.exists() or not candidate.is_file():
            continue
        if f"output/{batch}/" not in rel:
            continue
        valid_prompt_files.append(rel)
    return valid_prompt_files


def map_45_to_96_prompts(selected_45: list[str]) -> list[str]:
    out: list[str] = []
    for rel in selected_45:
        rel_96 = rel.replace("/45/", "/96/")
        file_96 = ROOT / rel_96
        if file_96.exists() and file_96.is_file():
            out.append(rel_96)
    return out


def extract_selected_ad_keys_from_45_prompts(selected_45: list[str]) -> set[tuple[str, int | None]]:
    keys: set[tuple[str, int | None]] = set()
    for rel in selected_45:
        parsed = parse_prompt_filename(rel)
        if not parsed:
            continue
        fmt, _lang, persona_number = parsed
        keys.add((fmt, persona_number))
    return keys


def filter_copy_json_for_selected_ads(copy_json: dict[str, Any], selected_keys: set[tuple[str, int | None]]) -> dict[str, Any]:
    ads = copy_json.get("ads")
    if not isinstance(ads, list):
        return copy_json
    selected_ads: list[dict[str, Any]] = []
    for ad in ads:
        if not isinstance(ad, dict):
            continue
        fmt = str(ad.get("format") or "").strip().upper()
        persona_number = None
        persona = ad.get("persona")
        if isinstance(persona, dict) and isinstance(persona.get("number"), int):
            persona_number = int(persona.get("number"))
        if (fmt, persona_number) in selected_keys or (fmt, None) in selected_keys:
            selected_ads.append(ad)
    cloned = json.loads(json.dumps(copy_json, ensure_ascii=False))
    cloned["ads"] = selected_ads
    return cloned


def api_run_generate_images_45(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    batch = str(manifest.get("batch") or "").strip()
    if not batch:
        raise HTTPException(status_code=400, detail="Run has no batch folder")

    prompt_files = payload.get("prompt_files")
    if not isinstance(prompt_files, list) or not prompt_files:
        raise HTTPException(status_code=400, detail="prompt_files must be a non-empty array")

    selected_45 = validate_selected_45_prompts(batch, prompt_files)
    if not selected_45:
        raise HTTPException(status_code=400, detail="No valid 4:5 prompt files selected")

    headless = bool(payload.get("headless", False))
    try:
        result = run_gemini_generation(
            batch=batch,
            prompt_files=selected_45,
            aspect_ratio="4:5",
            image_sources_file=None,
            headless=headless,
            run_dir=run_dir,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result.returncode != 0:
        error_text = result.stderr or result.stdout
        log_path = RUNTIME_ROOT / "generation_logs" / f"gen_{batch}_4_5.log"
        (run_dir / "logs" / "image_generation_45_error.txt").write_text(error_text, encoding="utf-8")
        short_error = "\n".join([line for line in error_text.splitlines() if line.strip()][-6:])
        raise HTTPException(status_code=500, detail=f"Gemini image generation failed (4:5). Log: {log_path}\n{short_error}")

    refreshed = collect_run_result(run_dir, batch, True)
    refreshed["generated_images_for_prompts_45"] = selected_45
    merged = merge_manifest(run_dir, manifest, refreshed)
    # Write generation metadata for 4:5 images
    try:
        _write_generation_metadata(run_dir, batch, "4:5", merged)
    except Exception:
        pass
    return merged


def api_run_generate_images_916_from_45(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    batch = str(manifest.get("batch") or "").strip()
    if not batch:
        raise HTTPException(status_code=400, detail="Run has no batch folder")

    prompt_files = payload.get("prompt_files")
    if not isinstance(prompt_files, list) or not prompt_files:
        raise HTTPException(status_code=400, detail="prompt_files must be a non-empty array")

    selected_45 = validate_selected_45_prompts(batch, prompt_files)
    if not selected_45:
        raise HTTPException(status_code=400, detail="No valid 4:5 prompt files for 9:16 generation")

    # Use image summary to map 4:5 prompt files to their generated image paths
    image_summary = load_batch_image_summary(batch)
    prompt_to_images: dict[str, list[str]] = {}
    for entry in image_summary:
        pf = entry.get("prompt_file") or ""
        saved = entry.get("saved_files") or []
        if pf and saved:
            prompt_to_images[pf] = saved

    # Build mapping: 9:16 prompt path -> [reference image paths]
    prompt_reference_map: dict[str, list[str]] = {}
    for pf in selected_45:
        rel_45 = str(pf).replace("\\", "/")

        # Parse format and persona number from the 4:5 prompt filename
        parsed = parse_prompt_filename(rel_45)
        if not parsed:
            continue
        fmt, lang, persona_num = parsed

        # Find existing 9:16 prompt file created by generate_ads.py (via generate-916 endpoint).
        # It lives at output/{batch}/96/OUTPUT_{FMT}_P{persona}_{lang}.txt
        pf_filename = f"OUTPUT_{fmt}_P{persona_num:02d}_{lang}.txt"
        prompt_96 = f"output/{batch}/96/{pf_filename}"
        prompt_96_path = ROOT / prompt_96
        if not prompt_96_path.exists():
            continue

        # Find the 4:5 generated image(s) for this prompt via image summary
        image_sources = prompt_to_images.get(rel_45, [])
        if not image_sources:
            # Fallback: search recursively in both image roots under GEMINI_4_5
            gemini_name = f"gemini-{fmt.lower()}-p{persona_num:02d}"
            for img_root in generated_image_roots():
                gemini_dir = img_root / batch / "GEMINI_4_5"
                if not gemini_dir.exists():
                    continue
                for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                    for f in sorted(gemini_dir.glob(f"**/{gemini_name}*.{ext.lstrip('*')}")):
                        rel = str(f.relative_to(ROOT))
                        if rel not in image_sources:
                            image_sources.append(rel)
                        break
                    if image_sources:
                        break
                if image_sources:
                    break

        if not image_sources:
            continue

        # Resolve to absolute paths for the reference map
        prompt_reference_map[prompt_96] = [str(ROOT / img) for img in image_sources]

    if not prompt_reference_map:
        raise HTTPException(status_code=400, detail="Could not build 9:16 reference images from selected 4:5 outputs")

    map_path = run_dir / "context" / "prompt_reference_map_916.json"
    map_path.write_text(json.dumps(prompt_reference_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    headless = bool(payload.get("headless", False))
    try:
        result = run_gemini_generation(
            batch=batch,
            prompt_files=sorted(prompt_reference_map.keys()),
            aspect_ratio="9:16",
            image_sources_file=None,
            prompt_reference_map=map_path,
            headless=headless,
            run_dir=run_dir,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result.returncode != 0:
        error_text = result.stderr or result.stdout
        log_path = RUNTIME_ROOT / "generation_logs" / f"gen_{batch}_9_16.log"
        (run_dir / "logs" / "image_generation_916_from_45_error.txt").write_text(error_text, encoding="utf-8")
        short_error = "\n".join([line for line in error_text.splitlines() if line.strip()][-6:])
        raise HTTPException(status_code=500, detail=f"Gemini image generation failed (9:16 from 4:5 refs). Log: {log_path}\n{short_error}")

    refreshed = collect_run_result(run_dir, batch, True)
    refreshed["generated_images_for_prompts_916"] = sorted(prompt_reference_map.keys())
    refreshed["reference_images_916"] = prompt_reference_map
    merged = merge_manifest(run_dir, manifest, refreshed)
    # Write generation metadata for 9:16 images
    try:
        _write_generation_metadata(run_dir, batch, "9:16", merged)
    except Exception:
        pass
    return merged


def api_batch_generate_images_45(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    run_ids = payload.get("run_ids")
    if not isinstance(run_ids, list) or not run_ids:
        raise HTTPException(status_code=400, detail="run_ids must be a non-empty array")

    all_prompt_files: list[str] = []
    run_info: list[dict[str, Any]] = []

    for run_id in run_ids:
        run_dir = RUNS_ROOT / run_id
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        batch = str(manifest.get("batch") or "").strip()
        if not batch:
            continue
        prompt_files_all = manifest.get("prompt_files") or []
        prompt_files_45 = [path for path in prompt_files_all if "/45/" in str(path)]
        if not prompt_files_45:
            continue
        all_prompt_files.extend(prompt_files_45)
        run_info.append({
            "run_id": run_id,
            "batch": batch,
            "prompt_count": len(prompt_files_45),
        })

    if not all_prompt_files:
        raise HTTPException(status_code=400, detail="No 4:5 prompt files found for any run")

    batch_names = sorted({r["batch"] for r in run_info})
    batch_name = batch_names[0] if len(batch_names) == 1 else "_".join(batch_names)
    work_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    prompt_work_dir = RUNTIME_ROOT / "gemini_selected_prompts" / f"{batch_name}_{work_id}"
    prompt_work_dir.mkdir(parents=True, exist_ok=True)
    starting_prompt = ""
    starting_prompt_path = ROOT / "input" / "startingprompt.txt"
    if starting_prompt_path.exists():
        starting_prompt = starting_prompt_path.read_text(encoding="utf-8").strip()
    prompt_files_created: list[str] = []
    for src_pf in all_prompt_files:
        src = Path(src_pf)
        if not src.is_absolute():
            src = ROOT / src
        src = src.resolve()
        if not src.exists():
            continue
        prompt_text = src.read_text(encoding="utf-8")
        combined = f"{starting_prompt}\n\n{prompt_text.strip()}\n" if starting_prompt else prompt_text
        dest = prompt_work_dir / src.name
        dest.write_text(combined, encoding="utf-8")
        prompt_files_created.append(str(dest))
    headless = bool(payload.get("headless", False))
    out_dir = GENERATED_IMAGES_ROOT / batch_name / "GEMINI_4_5"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "scripts/gemini_web_automation.py",
        "--prompt-dir",
        str(prompt_work_dir),
        "--prompt-glob",
        "*.txt",
        "--out-dir",
        str(out_dir),
        "--timeout",
        str(int(os.getenv("GEMINI_GENERATION_TIMEOUT_SECONDS") or "420")),
        "--manual-login-timeout",
        str(int(os.getenv("GEMINI_MANUAL_LOGIN_TIMEOUT_SECONDS") or "180")),
        "--upload-dir",
        str(INPUT_IMAGES_DIR),
    ]
    if headless:
        cmd.append("--headless")

    result = run_cmd(cmd, cwd=ROOT)
    if result.returncode != 0:
        error_text = result.stderr or result.stdout
        raise HTTPException(status_code=500, detail=f"Batch 4:5 generation failed: {error_text[:500]}")

    try:
        _write_generation_metadata(
            RUNS_ROOT / run_ids[0] if run_ids else RUNTIME_ROOT,
            batch_name, "4:5", {"batch": batch_name, "prompt_count": len(prompt_files_created)}
        )
    except Exception:
        pass

    return {
        "status": "completed",
        "batch_key": batch_name,
        "total_prompts": len(prompt_files_created),
        "run_count": len(run_ids),
    }


def _resolve_916_generation_for_run(run_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """For a single run, build the list of {prompt_96, image_sources} entries for 9:16 generation.

    Checks manifest for existing 9:16 prompt files, falls back to deriving from 4:5 prompts.
    Uses load_batch_image_summary to find existing 4:5 images as references.
    """
    batch = (manifest.get("batch") or "").strip()
    if not batch:
        return []

    prompt_files_all = manifest.get("prompt_files") or []

    # First try to use existing 9:16 prompt files from the manifest
    prompt_files_96 = [p for p in prompt_files_all if "/96/" in str(p)]

    if prompt_files_96:
        # We have 9:16 prompts already; find their corresponding 4:5 images
        image_summary = load_batch_image_summary(batch)
        prompt_to_images: dict[str, list[str]] = {}
        for entry in image_summary:
            pf = entry.get("prompt_file") or ""
            saved = entry.get("saved_files") or []
            if pf and saved:
                prompt_to_images[pf] = saved

        entries: list[dict[str, Any]] = []
        for pf96 in prompt_files_96:
            rel_96 = str(pf96).replace("\\", "/")
            parsed = parse_prompt_filename(rel_96)
            if not parsed:
                continue
            fmt, lang, persona_num = parsed

            # Look for 4:5 image by matching format+persona
            gemini_name = f"gemini-{fmt.lower()}-p{persona_num:02d}"
            image_sources: list[str] = []
            for pf45, imgs in prompt_to_images.items():
                if f"OUTPUT_{fmt}_P{persona_num:02d}" in str(pf45).upper():
                    image_sources = list(imgs)
                    break

            # Fallback: search image roots directly for the 4:5 image
            if not image_sources:
                for img_root in generated_image_roots():
                    gemini_dir = img_root / batch / "GEMINI_4_5"
                    if not gemini_dir.exists():
                        continue
                    for ext in ("png", "jpg", "jpeg", "webp"):
                        for f in sorted(gemini_dir.glob(f"**/{gemini_name}*.{ext}")):
                            rel = str(f.relative_to(ROOT))
                            if rel not in image_sources:
                                image_sources.append(rel)
                        if image_sources:
                            break
                    if image_sources:
                        break

            if not image_sources:
                continue

            pf96_path = f"output/{batch}/96/{Path(pf96).name}"
            entries.append({
                "prompt_96": pf96_path,
                "image_sources": image_sources,
            })
        return entries

    # Fallback: derive 9:16 prompts from 4:5 prompts (if 96 outputs exist on disk)
    prompt_files_45 = [p for p in prompt_files_all if "/45/" in str(p)]
    image_summary = load_batch_image_summary(batch)
    prompt_to_images: dict[str, list[str]] = {}
    for entry in image_summary:
        pf = entry.get("prompt_file") or ""
        saved = entry.get("saved_files") or []
        if pf and saved:
            prompt_to_images[pf] = saved

    entries = []
    for pf in prompt_files_45:
        rel_45 = str(pf).replace("\\", "/")
        parsed = parse_prompt_filename(rel_45)
        if not parsed:
            continue
        fmt, lang, persona_num = parsed

        # 9:16 prompt expected at output/{batch}/96/
        pf_filename = f"OUTPUT_{fmt}_P{persona_num:02d}_{lang}.txt"
        prompt_96 = f"output/{batch}/96/{pf_filename}"
        prompt_96_path = ROOT / prompt_96
        if not prompt_96_path.exists():
            continue

        image_sources = list(prompt_to_images.get(rel_45, []))

        # Fallback: search image roots directly
        if not image_sources:
            gemini_name = f"gemini-{fmt.lower()}-p{persona_num:02d}"
            for img_root in generated_image_roots():
                gemini_dir = img_root / batch / "GEMINI_4_5"
                if not gemini_dir.exists():
                    continue
                for ext in ("png", "jpg", "jpeg", "webp"):
                    for f in sorted(gemini_dir.glob(f"**/{gemini_name}*.{ext}")):
                        rel = str(f.relative_to(ROOT))
                        if rel not in image_sources:
                            image_sources.append(rel)
                        break
                    if image_sources:
                        break
                if image_sources:
                    break

        if not image_sources:
            continue

        entries.append({
            "prompt_96": prompt_96,
            "image_sources": image_sources,
        })

    return entries


def api_batch_generate_images_916(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    run_ids = payload.get("run_ids")
    if not isinstance(run_ids, list) or not run_ids:
        raise HTTPException(status_code=400, detail="run_ids must be a non-empty array")

    headless = bool(payload.get("headless", False))
    all_entries: list[dict[str, Any]] = []
    run_count = 0

    for run_id in run_ids:
        run_dir = RUNS_ROOT / run_id
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        entries = _resolve_916_generation_for_run(run_dir, manifest)
        if not entries:
            continue

        batch = str(manifest.get("batch") or "").strip()
        prompt_reference_map: dict[str, list[str]] = {}
        for e in entries:
            prompt_reference_map[e["prompt_96"]] = e["image_sources"]

        map_path = run_dir / "context" / "prompt_reference_map_916.json"
        map_path.write_text(json.dumps(prompt_reference_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        try:
            result = run_gemini_generation(
                batch=batch,
                prompt_files=sorted(prompt_reference_map.keys()),
                aspect_ratio="9:16",
                image_sources_file=None,
                prompt_reference_map=map_path,
                headless=headless,
                run_dir=run_dir,
            )
            if result.returncode != 0:
                error_text = result.stderr or result.stdout
                log_path = RUNTIME_ROOT / "generation_logs" / f"gen_{batch}_9_16.log"
                (run_dir / "logs" / "image_generation_916_error.txt").write_text(f"Log: {log_path}\n{error_text}", encoding="utf-8")
                # Continue to next run instead of failing everything
                continue

            refreshed = collect_run_result(run_dir, batch, True)
            refreshed["generated_images_for_prompts_916"] = sorted(prompt_reference_map.keys())
            refreshed["reference_images_916"] = prompt_reference_map
            merge_manifest(run_dir, manifest, refreshed)
            run_count += 1
            # Write generation metadata for this run's 9:16 images
            try:
                _write_generation_metadata(run_dir, batch, "9:16", refreshed)
            except Exception:
                pass
        except Exception:
            continue

        all_entries.extend(entries)

    if not all_entries:
        raise HTTPException(status_code=400, detail="No 9:16 images could be generated for any run")

    return {
        "status": "completed",
        "total_prompts": len(all_entries),
        "run_count": run_count,
    }


def extract_persona_input_block(prompt_text: str) -> str:
    markers = ["EXACT ON-IMAGE COPY", "PERSONA INPUT", "PERSONA:", "INPUT:"]
    for marker in markers:
        if marker in prompt_text.upper():
            start = prompt_text.upper().find(marker)
            if start != -1:
                return prompt_text[start:].strip()
    if len(prompt_text) > 50:
        return prompt_text.strip()
    return ""


def api_file_content(path: str, max_lines: int = 400) -> dict[str, Any]:
    file_path = resolve_safe_path(path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    clipped = lines[:max_lines]
    return {
        "path": str(file_path.relative_to(ROOT)),
        "total_lines": len(lines),
        "shown_lines": len(clipped),
        "content": "\n".join(clipped),
    }


async def api_run_execute(
    config: str = Form(...),
    product_info_file: UploadFile | None = File(None),
    mechanism_file: UploadFile | None = File(None),
    faq_file: UploadFile | None = File(None),
    image_source_file: UploadFile | None = File(None),
    input_image_files: list[UploadFile] | None = File(None),
    clear_input_images: bool = Form(False),
) -> dict[str, Any]:
    ensure_dirs()
    batch = "v0"
    try:
        cfg = json.loads(config)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid config JSON") from exc
    if str((cfg.get("server_type") or "opencode")).strip().lower() != "opencode":
        raise HTTPException(status_code=400, detail="Unsupported server type. Use OpenCode.")

    run_id = make_run_id()
    run_dir = RUNS_ROOT / run_id
    (run_dir / "inputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "context").mkdir(parents=True, exist_ok=True)

    product_path = save_upload(run_dir / "inputs" / "product master doc.txt", product_info_file)
    mechanism_path = None
    faq_path = None
    image_sources_path = save_upload(run_dir / "inputs" / "image_sources.txt", image_source_file)
    saved_input_images = store_uploaded_input_images(input_image_files or [], clear_input_images)

    product_file = coalesce_path(product_path, DEFAULT_PRODUCT_MASTER)
    mechanism_file_path = ROOT / "__empty__.txt"
    faq_file_path = ROOT / "__empty__.txt"

    image_sources_file_path = coalesce_path(image_sources_path, default_image_sources_file())

    try:
        base_plan = resolve_format_plan(cfg)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    hypothesis_cfg = cfg.get("hypothesis") or {}
    plan = expand_plan_with_hypothesis(base_plan, hypothesis_cfg)

    # Save hypothesis config to run dir for reference
    if hypothesis_cfg:
        (run_dir / "context" / "hypothesis_config.json").write_text(
            json.dumps(hypothesis_cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    product_ctx_source = "attached_product_master_doc"
    extractor_model = "none"
    (run_dir / "context" / "product_doc_source.json").write_text(
        json.dumps(
            {
                "source": product_ctx_source,
                "product_file": str(product_file),
                "note": "Canonical extraction is disabled; the full product master doc is attached to the OpenCode copy session unchanged.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    persona_library = parse_persona_library(DEFAULT_PLAYBOOK)
    ads_context: list[dict[str, Any]] = []
    format_seen_counts: dict[str, int] = {}
    for item in plan:
        persona_no = item["persona"]
        fmt = item["format"]
        format_seen_counts[fmt] = format_seen_counts.get(fmt, 0) + 1
        persona_payload = build_persona_payload(persona_no, persona_library)

        format_result = run_cmd(
            [
                "python3",
                "scripts/extract_format_rules.py",
                "--playbook",
                str(DEFAULT_PLAYBOOK),
                "--format",
                fmt,
                "--json",
            ],
            cwd=ROOT,
        )
        format_payload = parse_json_stdout(format_result, f"extract_format_rules({fmt})")
        copy_req = build_copy_requirements(persona_no, fmt, format_seen_counts[fmt], run_id)

        # Inject hypothesis directive if active
        hyp_meta = item.get("hypothesis")
        concept = {}
        if isinstance(hyp_meta, dict) and hyp_meta.get("type") != "none":
            copy_req["hypothesis"] = hyp_meta
            concept = copy_req.get("concept_variation") or {}
            hyp_type = hyp_meta.get("type")
            variant = hyp_meta.get("variant")
            if hyp_type == "awareness_stage" and variant:
                concept["audience_stage"] = _framework_item("audience_stage", variant)
                if variant in AWARENESS_STAGE_GUIDANCE:
                    concept["awareness_stage_guidance"] = AWARENESS_STAGE_GUIDANCE[variant]
            elif hyp_type == "concept_angle" and variant:
                concept["lead_angle"] = _framework_item("lead_angle", variant)
                if variant in CONCEPT_ANGLE_GUIDANCE:
                    concept["concept_angle_guidance"] = CONCEPT_ANGLE_GUIDANCE[variant]
            elif hyp_type == "concept_structure" and variant:
                concept["message_structure"] = _framework_item("message_structure", variant)
                if variant in CONCEPT_STRUCTURE_GUIDANCE:
                    concept["concept_structure_guidance"] = CONCEPT_STRUCTURE_GUIDANCE[variant]
            elif hyp_type == "hook_structure" and variant:
                concept["hook_structure_override"] = variant
                if variant in HOOK_STRUCTURE_GUIDANCE:
                    concept["hook_structure_guidance"] = HOOK_STRUCTURE_GUIDANCE[variant]
            elif hyp_type == "proof_style" and variant:
                concept["proof_style_override"] = variant
                if variant in PROOF_STYLE_GUIDANCE:
                    concept["proof_style_guidance"] = PROOF_STYLE_GUIDANCE[variant]
            elif hyp_type == "cta_voice" and variant:
                concept["cta_voice_override"] = variant
                if variant in CTA_VOICE_GUIDANCE:
                    concept["cta_voice_guidance"] = CTA_VOICE_GUIDANCE[variant]
            copy_req["concept_variation"] = concept

        ads_context.append(
            {
                "persona": persona_payload,
                "format_rules": format_payload,
                "format": fmt,
                "copy_requirements": copy_req,
                "hypothesis": hyp_meta,
            }
        )

    banlist_result = run_cmd(["python3", "scripts/registry_banlist.py", "--last", "150"], cwd=ROOT)
    banlist_payload = parse_json_stdout(banlist_result, "registry_banlist")

    full_context = {
        "generated_at": now_iso(),
        "run_id": run_id,
        "language_mode": resolve_language_mode(cfg),
        "context_source": product_ctx_source,
        "context_extractor_model": extractor_model,
        "product_file_path": str(product_file),
        "ads": ads_context,
        "banlist": banlist_payload,
    }
    (run_dir / "context" / "run_context.json").write_text(
        json.dumps(full_context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    llm_mode = "opencode"
    copy_json = call_opencode_compatible(cfg, full_context, run_dir)
    used_template_fallback = False
    if not copy_json:
        llm_mode = "fallback_template"
        used_template_fallback = True
        (run_dir / "logs" / "opencode_fallback.txt").write_text(
            "OpenCode copy generation unavailable; using deterministic schema-compatible fallback copy.\n",
            encoding="utf-8",
        )
        copy_json = build_template_copy(full_context, run_id)
    opencode_failures = copy_json.pop("_opencode_failures", []) if isinstance(copy_json, dict) else []
    opencode_warnings = copy_json.pop("_opencode_warnings", []) if isinstance(copy_json, dict) else []
    opencode_session_fallback = bool(copy_json.pop("_opencode_session_fallback", False)) if isinstance(copy_json, dict) else False
    if opencode_failures and llm_mode == "opencode":
        llm_mode = "opencode_partial_fallback"
        (run_dir / "logs" / "opencode_fallback.txt").write_text(
            "Some OpenCode ad generations failed; normalize_generated_copy filled those outputs with deterministic template copy.\n\n"
            + "\n\n---\n\n".join(opencode_failures),
            encoding="utf-8",
        )
    copy_json = normalize_generated_copy(copy_json, full_context, run_id)
    copy_json = strip_internal_markers_from_payload(copy_json)
    copy_json = enforce_unique_ctas(copy_json, full_context)
    copy_json = scrub_on_image_copy(copy_json)
    generated_copy_error = validate_generated_copy_payload(copy_json, ads_context)
    if generated_copy_error:
        (run_dir / "logs" / "opencode_error.txt").write_text(
            generated_copy_error + "\n\nGenerated payload:\n" + json.dumps(copy_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raise HTTPException(status_code=502, detail="OpenCode copy generation returned incomplete copy. Prompt production stopped; check run logs.")

    copy_file = run_dir / "context" / "copy_batch.json"
    copy_file.write_text(json.dumps(copy_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    assembler_result = run_cmd(
        [
            "python3",
            "scripts/generate_ads.py",
            "--copy-file",
            str(copy_file),
            "--language-mode",
            assembler_language_mode(cfg),
            "--no-registry-write",
            "--skip-uniqueness-check",
        ],
        cwd=ROOT,
    )
    if assembler_result.returncode != 0:
        assembler_error = assembler_result.stderr or assembler_result.stdout
        (run_dir / "logs" / "assembler_error.txt").write_text(assembler_error, encoding="utf-8")
        raise HTTPException(status_code=500, detail="Prompt assembly failed. Check run logs.")

    batch_match = re.search(r"Batch:\s*(v\d+)", assembler_result.stdout)
    if not batch_match:
        raise HTTPException(status_code=500, detail="Could not parse batch from assembler output")
    batch = batch_match.group(1)

    generate_images = False
    image_generated = False
    if generate_images:
        kie_api_key = (cfg.get("kie_api_key") or "").strip()
        if not kie_api_key:
            (run_dir / "logs" / "image_blocker.txt").write_text(
                "generate_images was true but kie_api_key is missing", encoding="utf-8"
            )
        else:
            image_result = run_cmd(
                [
                    "python3",
                    "scripts/kie_nano_batch.py",
                    "--batch",
                    batch,
                ],
                cwd=ROOT,
            )
            (run_dir / "logs" / "image_generation.log").write_text(
                (image_result.stdout or "") + "\n" + (image_result.stderr or ""), encoding="utf-8"
            )
            image_generated = image_result.returncode == 0

    manifest = collect_run_result(run_dir, batch, image_generated)
    manifest["llm_mode"] = llm_mode
    if llm_mode == "fallback_template":
        manifest["copy_source"] = "deterministic fallback template"
    elif llm_mode == "opencode_partial_fallback":
        manifest["copy_source"] = f"opencode generated copy with template fallback for {len(opencode_failures)} failed ad(s)"
    else:
        manifest["copy_source"] = "opencode generated copy"
    if opencode_failures:
        manifest["copy_generation_failures"] = len(opencode_failures)
        manifest["copy_fallback_log"] = str((run_dir / "logs" / "opencode_fallback.txt").relative_to(ROOT))
    if used_template_fallback:
        manifest["copy_generation_failures"] = max(int(manifest.get("copy_generation_failures") or 0), 1)
        manifest["copy_fallback_log"] = str((run_dir / "logs" / "opencode_fallback.txt").relative_to(ROOT))
        manifest["copy_generation_notes"] = ["OpenCode copy generation unavailable; deterministic fallback copy was used."]
    if opencode_warnings:
        manifest["copy_generation_warnings"] = len(opencode_warnings)
        manifest["copy_warning_log"] = str((run_dir / "logs" / "opencode_error.txt").relative_to(ROOT))
        manifest["copy_generation_notes"] = [str(item).splitlines()[0] for item in opencode_warnings[:3]]
    if opencode_session_fallback:
        manifest["copy_session_fallback"] = True
        manifest["copy_session_log"] = str((run_dir / "logs" / "opencode_session.log").relative_to(ROOT))
    manifest["context_source"] = product_ctx_source
    manifest["context_extractor_model"] = extractor_model
    manifest["image_sources_file"] = str(image_sources_file_path)
    manifest["input_images_dir"] = str(INPUT_IMAGES_DIR.relative_to(ROOT)).replace("\\", "/")
    manifest["input_images_uploaded"] = saved_input_images
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


# Chrome process tracking
_chrome_process: subprocess.Popen | None = None


def api_launch_visible_browser() -> dict[str, Any]:
    """Launch a visible Chrome instance with CDP enabled so the user can log in
    before automation begins."""
    global _chrome_process

    chrome_bin = None
    for candidate in [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]:
        if Path(candidate).exists():
            chrome_bin = candidate
            break

    if not chrome_bin:
        raise HTTPException(status_code=500, detail="Chrome binary not found on system")

    cmd = [
        chrome_bin,
        "--remote-debugging-port=9222",
        f"--user-data-dir={os.path.expandvars('$HOME')}/.config/google-chrome-gemini-cdp",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    _chrome_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

    for attempt in range(10):
        try:
            resp = urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=2)
            if resp.status == 200:
                return {
                    "status": "launched",
                    "cdp_url": "http://127.0.0.1:9222",
                    "message": "Chrome launched. Log in, then trigger generation.",
                }
        except Exception:
            time.sleep(1)

    raise HTTPException(status_code=500, detail="Chrome launched but CDP not responding on port 9222")


def api_kill_chrome() -> dict[str, Any]:
    """Kill the Chrome process started by launch-visible-browser and stop any running automation."""
    global _chrome_process
    killed = False
    if _chrome_process and _chrome_process.poll() is None:
        try:
            _chrome_process.terminate()
            try:
                _chrome_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _chrome_process.kill()
                _chrome_process.wait(timeout=3)
            killed = True
        except Exception:
            pass
        _chrome_process = None

    # Also kill any running gemini automation processes
    gemini_killed = 0
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            if any("gemini_web_automation" in c for c in cmdline):
                proc.kill()
                gemini_killed += 1
        except Exception:
            continue

    return {"status": "killed", "chrome": killed, "gemini_processes": gemini_killed}


def api_edit_prompt(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Edit a prompt file in-place, replacing only the EXACT ON-IMAGE COPY block."""
    run_dir = RUNS_ROOT / run_id
    prompt_path = payload.get("prompt_file", "")
    new_text = payload.get("text", "")
    if not prompt_path or not new_text:
        raise HTTPException(status_code=400, detail="prompt_file and text are required")

    full_path = ROOT / prompt_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Prompt file not found")

    old_text = full_path.read_text(encoding="utf-8")
    updated_text = _replace_exact_copy_block(old_text, new_text)
    if updated_text is None:
        raise HTTPException(status_code=400, detail="No EXACT ON-IMAGE COPY block found in prompt file")
    full_path.write_text(updated_text, encoding="utf-8")
    return {"status": "saved", "prompt_file": prompt_path}


def api_delete_prompt(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Delete a prompt file and remove it from the run manifest."""
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    prompt_path = payload.get("prompt_file", "")
    if not prompt_path:
        raise HTTPException(status_code=400, detail="prompt_file is required")

    full_path = ROOT / prompt_path
    if full_path.exists():
        full_path.unlink()

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["prompt_files"] = [p for p in manifest.get("prompt_files", []) if p != prompt_path]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {"status": "deleted", "prompt_file": prompt_path}


def api_delete_image(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Delete a generated image and its metadata JSON."""
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    image_path = payload.get("image_file", "")
    if not image_path:
        raise HTTPException(status_code=400, detail="image_file is required")

    full_path = ROOT / image_path
    if full_path.exists():
        full_path.unlink()

    # Also delete companion JSON metadata if it exists
    json_path = full_path.with_suffix(".json")
    if json_path.exists():
        json_path.unlink()

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["image_files"] = [p for p in manifest.get("image_files", []) if p != image_path]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {"status": "deleted", "image_file": image_path}


def _parse_image_naming(image_path_str: str, run_dir: Path) -> dict[str, str]:
    """Extract format, persona, language from an image's companion JSON metadata
    and build a human-readable stem for download naming."""
    full_path = ROOT / image_path_str
    meta_path = full_path.with_suffix(".json")
    base = {"format": "UNKNOWN", "persona": "00", "lang": "EN", "stem": "image"}

    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        prompt_file = str(meta.get("prompt_file_relative") or meta.get("prompt_file") or "").strip().replace("\\", "/")
        if not prompt_file:
            prompt_file = str(meta.get("prompt_file_relative") or meta.get("prompt_file") or "").strip().replace("\\", "/")
        parsed = parse_prompt_filename(prompt_file)
        if parsed:
            fmt, lang, persona_num = parsed
            base["format"] = fmt
            base["persona"] = f"P{persona_num:02d}" if persona_num else "P00"
            base["lang"] = lang

    # Try hypothesis
    hyp_label = ""
    hyp_path = run_dir / "context" / "hypothesis_config.json"
    if hyp_path.exists():
        try:
            hyp_cfg = json.loads(hyp_path.read_text(encoding="utf-8"))
            htype = hyp_cfg.get("type", "")
            hvar = hyp_cfg.get("variant", "")
            if htype and htype != "none":
                parts = [htype]
                if hvar:
                    parts.append(hvar)
                hyp_label = "_" + "_".join(parts)
        except Exception:
            pass

    ext = Path(image_path_str).suffix
    stem = f"{base['format']}_{base['persona']}_{base['lang']}{hyp_label}"
    base["stem"] = stem
    base["ext"] = ext
    return base


def api_download_single_image(run_id: str, image_file: str):
    """Return a zip containing the image file and its metadata JSON."""
    run_dir = RUNS_ROOT / run_id
    full_path = ROOT / image_file
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")

    naming = _parse_image_naming(image_file, run_dir)
    meta_path = full_path.with_suffix(".json")

    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(full_path, f"{naming['stem']}{naming['ext']}")
        meta_content = {"source": image_file}
        if meta_path.exists():
            try:
                meta_content = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        meta_content["_download_name"] = naming["stem"]
        zf.writestr(f"{naming['stem']}_metadata.json", json.dumps(meta_content, ensure_ascii=False, indent=2))

    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{naming["stem"]}.zip"'})


def api_download_batch_images(run_id: str):
    """Return a zip containing all images in a run with their metadata."""
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    image_files = manifest.get("image_files", [])
    if not image_files:
        raise HTTPException(status_code=404, detail="No images found for this run")

    batch_label = manifest.get("batch", run_id)
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for img_path in image_files:
            full_path = ROOT / img_path
            if not full_path.exists():
                continue
            naming = _parse_image_naming(img_path, run_dir)
            meta_path = full_path.with_suffix(".json")
            zf.write(full_path, f"{naming['stem']}{naming['ext']}")
            meta_content = {"source": img_path}
            if meta_path.exists():
                try:
                    meta_content = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            meta_content["_download_name"] = naming["stem"]
            zf.writestr(f"{naming['stem']}_metadata.json", json.dumps(meta_content, ensure_ascii=False, indent=2))

    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="batch_{batch_label}.zip"'})


# ── Modular routes ───────────────────────────────────────────────────────────
from dashboard.backend.routes import defaults, progress, runs, generate, batch, export_import, execute, chrome

app.include_router(defaults.router)
app.include_router(progress.router)
app.include_router(runs.router)
app.include_router(generate.router)
app.include_router(batch.router)
app.include_router(export_import.router)
app.include_router(execute.router)
app.include_router(chrome.router)

app.mount("/storage", StaticFiles(directory=str(STORAGE_ROOT)), name="storage")
app.mount("/output", StaticFiles(directory=str(ROOT / "output")), name="output")
GENERATED_IMAGES_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/generated_images", StaticFiles(directory=str(GENERATED_IMAGES_ROOT)), name="generated_images")
app.mount("/", StaticFiles(directory=str(ROOT / "dashboard" / "frontend"), html=True), name="frontend")
