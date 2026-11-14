"""Find plant health problems in a photo with Claude (vision + structured output).

Credentials come from the environment the usual Anthropic SDK way
(ANTHROPIC_API_KEY, or an `ant auth login` profile). Without them, analysis
fails with a readable message and the user can still pick the issue by hand.
"""
import base64
import io
import json

from django.conf import settings
from PIL import Image

from . import health_library

MODEL = getattr(settings, "PLANT_HEALTH_MODEL", "claude-opus-5-5")
MAX_SIDE = 1568  # larger images are downscaled by the API anyway

ISSUE_KEYS = list(health_library.ISSUES) + ["other"]

SCHEMA = {
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
                    "key": {"type": "string", "enum": ISSUE_KEYS},
                    "name": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "evidence": {"type": "string"},
                    "organic_treatments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "how": {"type": "string"},
                            },
                            "required": ["name", "how"],
                            "additionalProperties": False,
                        },
                    },
                    "prevention": {"type": "string"},
                },
                "required": ["key", "name", "confidence", "evidence", "organic_treatments", "prevention"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["is_plant", "overall", "progress", "summary", "issues"],
    "additionalProperties": False,
}

SYSTEM = (
    "You are a careful plant doctor for home gardeners. You look at a photo of a whole "
    "plant or a single leaf and identify visible pests, diseases and care problems.\n"
    "- Only report problems you can actually see evidence of; say what you see in "
    "'evidence'. If the plant looks healthy, return overall 'healthy' and no issues.\n"
    "- Use a listed issue key when one fits; use 'other' only when none does.\n"
    "- Recommend organic treatments only (no synthetic pesticides or fungicides), with "
    "practical amounts and how often to apply them.\n"
    "- Order issues from most to least likely. Be honest about confidence: a photo "
    "can't confirm everything.\n"
    "- If the image is not a plant, set is_plant false.\n"
    "- When an earlier photo is given, compare the two and set 'progress' to better, "
    "same or worse; otherwise set it to 'first'.\n"
    "Known issue keys: "
    + ", ".join(f"{key} ({issue['name']})" for key, issue in health_library.ISSUES.items())
)


NO_CREDENTIALS = (
    "Photo analysis isn't set up yet: no Anthropic API key was found on the server. "
    "Add ANTHROPIC_API_KEY to the project's .env file and restart the server."
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


def analyse(image_file, *, plant, notes="", previous_image=None, previous_title=""):
    """Return the analysis dict for a photo, or raise AnalysisError."""
    import anthropic  # imported lazily so the app runs without the SDK installed

    species = plant.plant_species
    about = f"Plant: {plant.name}"
    if species:
        about += f" — {species.common_name} ({species.scientific_name})"
    content = []
    if previous_image:
        content += [{"type": "text", "text": "Earlier photo:"}, _image_block(previous_image)]
        content.append({"type": "text", "text": "Latest photo:"})
    content.append(_image_block(image_file))
    text = about + "."
    if previous_title:
        text += f" It is being treated for: {previous_title}."
    if notes:
        text += f" The owner noticed: {notes}"
    content.append({"type": "text", "text": text + "\nWhat problems can you see?"})

    try:
        client = anthropic.Anthropic()
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": content}],
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": SCHEMA},
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
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        raise AnalysisError("The analysis came back incomplete. Please try again.")
    if not result.get("is_plant", True):
        raise AnalysisError("That photo doesn't look like a plant. Try a close-up of the leaves.")
    return result
