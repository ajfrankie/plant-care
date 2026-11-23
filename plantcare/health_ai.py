"""Find plant health problems in a photo (vision + structured output).

Two providers are supported, chosen by ``provider()``:

- Google Gemini: GEMINI_API_KEY (or GOOGLE_API_KEY). Model from
  GEMINI_HEALTH_MODEL, default gemini-3.5-flash.
- Anthropic (Claude): ANTHROPIC_API_KEY, or an `ant auth login` profile.

Set PLANT_HEALTH_PROVIDER=gemini|anthropic to choose explicitly; otherwise the
provider whose key is set is used. Without credentials, analysis fails with a
readable message and the user can still pick the issue by hand.
"""
import base64
import io
import json
import os

from django.conf import settings
from PIL import Image

from . import health_library

MODEL = getattr(settings, "PLANT_HEALTH_MODEL", "claude-opus-5-5")
GEMINI_MODEL = os.environ.get("GEMINI_HEALTH_MODEL") or getattr(settings, "GEMINI_HEALTH_MODEL", "gemini-3.5-flash")
GEMINI_TIMEOUT_MS = 90_000
PROVIDERS = ("gemini", "anthropic")
MAX_SIDE = 1568  # larger images are downscaled by the API anyway


def issue_keys():
    return list(health_library.ISSUES) + ["other"]


def schema():
    """JSON schema for the analysis, listing the library's current issue keys."""
    return {
        "type": "object",
        "properties": {
            "is_plant": {"type": "boolean"},
            "overall": {"type": "string", "enum": ["healthy", "mild", "moderate", "severe"]},
            "progress": {"type": "string", "enum": ["first", "better", "same", "worse"]},
            "summary": {"type": "string"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "enum": issue_keys()},
                        "name": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                        "evidence": {"type": "string"},
                        "organic_treatments": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "step": {"type": "string"},
                                    "when": {"type": "string"},
                                    "how": {"type": "string"},
                                },
                                "required": ["name", "step", "when", "how"],
                                "additionalProperties": False,
                            },
                        },
                        "prevention": {"type": "string"},
                        "areas": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "ymin": {"type": "integer"},
                                    "xmin": {"type": "integer"},
                                    "ymax": {"type": "integer"},
                                    "xmax": {"type": "integer"},
                                },
                                "required": ["label", "ymin", "xmin", "ymax", "xmax"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["key", "name", "confidence", "evidence", "organic_treatments",
                                 "prevention", "areas"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["is_plant", "overall", "progress", "summary", "issues"],
        "additionalProperties": False,
    }


SYSTEM_RULES = (
    "You are a careful plant doctor for home gardeners. You look at a photo of a whole "
    "plant or a single leaf and identify visible pests, diseases and care problems.\n"
    "- Only report problems you can actually see evidence of; say what you see in "
    "'evidence'. If the plant looks healthy, return overall 'healthy' and no issues.\n"
    "- Use a listed issue key when one fits; use 'other' only when none does.\n"
    "- Recommend organic, home-friendly treatments only: no synthetic pesticides or "
    "fungicides, and no copper or sulfur products. List them in the order to do them.\n"
    "- For each treatment give 'step' (a short action title of 5 words at most, e.g. "
    "'Cut off spotted leaves'), 'when' (e.g. 'Today', 'Every 7 days') and 'how' (one or "
    "two plain sentences with practical amounts).\n"
    "- In 'areas', mark up to 3 places on the latest photo where the problem is visible, "
    "as boxes with coordinates from 0 to 1000 (ymin, xmin, ymax, xmax; 0,0 is the top "
    "left) and a 2–4 word 'label' such as 'Brown spots'. Leave it empty if you can't "
    "point to a spot.\n"
    "- Order issues from most to least likely. Be honest about confidence: a photo "
    "can't confirm everything.\n"
    "- If the image is not a plant, set is_plant false.\n"
    "- When an earlier photo is given, compare the two and set 'progress' to better, "
    "same or worse; otherwise set it to 'first'.\n"
    "Known issue keys: "
)


def system_prompt():
    return SYSTEM_RULES + ", ".join(f"{key} ({issue['name']})" for key, issue in health_library.ISSUES.items())


NO_CREDENTIALS = (
    "Photo analysis isn't set up yet: no Anthropic API key was found on the server. "
    "Add GEMINI_API_KEY or ANTHROPIC_API_KEY to the project's .env file and restart the server."
)
NO_GEMINI_CREDENTIALS = (
    "Photo analysis isn't set up yet: no Gemini API key was found on the server. "
    "Add GEMINI_API_KEY to the project's .env file and restart the server."
)
GEMINI_KEY_IN_ANTHROPIC = (
    "Photo analysis isn't set up: ANTHROPIC_API_KEY holds a Google Gemini key. "
    "Rename it to GEMINI_API_KEY in the .env file and restart the server."
)
OTHER_KEY_IN_ANTHROPIC = (
    "Photo analysis isn't set up: ANTHROPIC_API_KEY doesn't hold an Anthropic key "
    "(those start with sk-ant-). For a Gemini key use GEMINI_API_KEY instead."
)


class AnalysisError(Exception):
    """The photo couldn't be analysed; the message is safe to show the user."""


def _encode(image_file):
    """Downscale and re-encode an uploaded image as base64 JPEG."""
    image_file.seek(0)
    with Image.open(image_file) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
    image_file.seek(0)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def _image_block(image_file):
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": _encode(image_file)},
    }


def _http_exceptions():
    """(timeout errors, other network errors) of whichever HTTP client the Gemini SDK uses."""
    timeouts, failures = [TimeoutError], [OSError]
    for name in ("httpx2", "httpx", "requests"):
        try:
            module = __import__(name)
        except ImportError:
            continue
        if name == "requests":
            timeouts.append(module.exceptions.Timeout)
            failures.append(module.exceptions.RequestException)
        else:
            timeouts.append(module.TimeoutException)
            failures.append(module.HTTPError)
    return tuple(timeouts), tuple(failures)



def _gemini_key():
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""


def provider():
    """'gemini' or 'anthropic'."""
    chosen = (os.environ.get("PLANT_HEALTH_PROVIDER") or getattr(settings, "PLANT_HEALTH_PROVIDER", "")).lower()
    if chosen in PROVIDERS:
        return chosen
    if _gemini_key():
        return "gemini"
    return "anthropic"  # uses ANTHROPIC_API_KEY or an `ant auth login` profile


def _prompt_text(plant, notes, previous_title):
    species = plant.plant_species
    text = f"Plant: {plant.name}"
    if species:
        text += f" — {species.common_name} ({species.scientific_name})"
    text += "."
    if previous_title:
        text += f" It is being treated for: {previous_title}."
    if notes:
        text += f" The owner noticed: {notes}"
    return text + "\nWhat problems can you see?"


def _parse(text):
    try:
        result = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        raise AnalysisError("The analysis came back incomplete. Please try again.")
    if not result.get("is_plant", True):
        raise AnalysisError("That photo doesn't look like a plant. Try a close-up of the leaves.")
    return result


def analyse(image_file, *, plant, notes="", previous_image=None, previous_title=""):
    """Return the analysis dict for a photo, or raise AnalysisError."""
    analyse_with = _analyse_gemini if provider() == "gemini" else _analyse_anthropic
    return analyse_with(image_file, plant=plant, notes=notes,
                        previous_image=previous_image, previous_title=previous_title)


def _analyse_gemini(image_file, *, plant, notes, previous_image, previous_title):
    try:
        from google import genai  # imported lazily so the app runs without the SDK installed
        from google.genai import errors, types
    except ImportError:
        raise AnalysisError("Photo analysis with Gemini needs the 'google-genai' package: pip install google-genai")
    key = _gemini_key()
    if not key:
        raise AnalysisError(NO_GEMINI_CREDENTIALS)
    http_timeouts, http_errors = _http_exceptions()

    def image(file):
        return types.Part.from_bytes(data=base64.b64decode(_encode(file)), mime_type="image/jpeg")

    contents = []
    if previous_image:
        contents += ["Earlier photo:", image(previous_image), "Latest photo:"]
    contents += [image(image_file), _prompt_text(plant, notes, previous_title)]

    try:
        client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS))
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt(),
                max_output_tokens=8000,
                response_mime_type="application/json",
                response_json_schema=schema(),
                # Low reasoning keeps the upload page quick; the photo does most of the work.
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
            ),
        )
    except errors.APIError as error:
        code = getattr(error, "code", None)
        text = str(error)
        if code in (401, 403) or "API_KEY_INVALID" in text or "API key not valid" in text:
            raise AnalysisError("Photo analysis isn't set up: the Gemini API key is missing or invalid.")
        if code == 429:
            raise AnalysisError("Photo analysis has hit the Gemini free-tier limit. Please try again in a minute.")
        raise AnalysisError(f"Photo analysis failed ({code}). Please try again.")
    except http_timeouts:
        raise AnalysisError("Photo analysis took too long. Please try again.")
    except http_errors:
        raise AnalysisError("Couldn't reach the photo analysis service. Check the internet connection.")

    feedback = getattr(response, "prompt_feedback", None)
    if feedback is not None and getattr(feedback, "block_reason", None):
        raise AnalysisError("This photo couldn't be analysed. Try a clearer photo of the plant.")
    candidates = getattr(response, "candidates", None) or []
    reason = getattr(candidates[0], "finish_reason", None) if candidates else None
    reason = getattr(reason, "name", reason)
    if reason == "MAX_TOKENS":
        raise AnalysisError("The analysis was cut short. Please try again.")
    if reason in ("SAFETY", "IMAGE_SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "RECITATION", "SPII"):
        raise AnalysisError("This photo couldn't be analysed. Try a clearer photo of the plant.")
    return _parse(response.text)


def _analyse_anthropic(image_file, *, plant, notes, previous_image, previous_title):
    import anthropic  # imported lazily so the app runs without the SDK installed

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key.startswith(("AIza", "AQ.")):  # Google API key formats
        raise AnalysisError(GEMINI_KEY_IN_ANTHROPIC)
    if key and not key.startswith("sk-ant-"):
        raise AnalysisError(OTHER_KEY_IN_ANTHROPIC)

    content = []
    if previous_image:
        content += [{"type": "text", "text": "Earlier photo:"}, _image_block(previous_image)]
        content.append({"type": "text", "text": "Latest photo:"})
    content.append(_image_block(image_file))
    content.append({"type": "text", "text": _prompt_text(plant, notes, previous_title)})

    try:
        client = anthropic.Anthropic()
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=system_prompt(),
            messages=[{"role": "user", "content": content}],
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": schema()},
            },
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError:
        raise AnalysisError("Photo analysis isn't set up: the Anthropic API key is missing or invalid.")
    except anthropic.RateLimitError:
        raise AnalysisError("Photo analysis is busy right now. Please try again in a minute.")
    except anthropic.APIConnectionError:
        raise AnalysisError("Couldn't reach the photo analysis service. Check the internet connection.")
    except anthropic.APIStatusError as error:
        raise AnalysisError(f"Photo analysis failed ({error.status_code}). Please try again.")
    except anthropic.AnthropicError:
        raise AnalysisError(NO_CREDENTIALS)
    except TypeError as error:
        # The SDK raises TypeError when no API key or login profile is configured.
        if "authentication" in str(error):
            raise AnalysisError(NO_CREDENTIALS)
        raise

    if response.stop_reason == "refusal":
        raise AnalysisError("This photo couldn't be analysed. Try a clearer photo of the plant.")
    if response.stop_reason == "max_tokens":
        raise AnalysisError("The analysis was cut short. Please try again.")
    return _parse(next((b.text for b in response.content if b.type == "text"), ""))
