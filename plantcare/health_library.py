"""Common plant problems and their organic treatments.

Used when the user already knows the problem, and to back up what the photo
analysis finds with tried-and-tested organic remedies. Always test a spray on
one leaf first and apply in the evening or out of direct sun.

Each treatment is one step of the treatment roadmap: ``step`` is its short
title (five words at most), ``when`` says when or how often, and ``how`` gives
the detail. Organic remedies only — see ``is_organic``.
"""
from collections.abc import Mapping

# Reusable treatments ---------------------------------------------------------

NEEM_OIL = {
    "name": "Neem Oil", "step": "Spray with neem oil", "when": "Every 7 days",
    "how": "Mix 1–2 tablespoons of cold-pressed neem oil and a few drops of mild soap in "
           "1 gallon of water. Spray the tops and undersides of the leaves.",
}
INSECTICIDAL_SOAP = {
    "name": "Insecticidal Soap", "step": "Spray with soapy water", "when": "Every 5–7 days for 3 weeks",
    "how": "Mix 1 tablespoon of pure castile soap in 1 litre of water. Spray the pests "
           "directly until dripping — it only works on contact.",
}
WATER_BLAST = {
    "name": "Strong Water Spray", "step": "Hose pests off leaves", "when": "Every 2–3 days for a week",
    "how": "Spray firmly with lukewarm water under the leaves and along the stems.",
}
ALCOHOL_SWAB = {
    "name": "Rubbing Alcohol Swab", "step": "Dab pests with alcohol", "when": "Weekly until gone",
    "how": "Touch each pest with a cotton swab dipped in rubbing alcohol.",
}
STICKY_TRAPS = {
    "name": "Yellow Sticky Traps", "step": "Hang yellow sticky traps", "when": "Replace when full",
    "how": "Place sticky cards just above the soil to catch flying adults and see if "
           "numbers are falling.",
}
PRUNE_AFFECTED = {
    "name": "Remove Affected Leaves", "step": "Cut off sick leaves", "when": "Today",
    "how": "Use clean scissors and bin the leaves — don't compost them.",
}
AIRFLOW = {
    "name": "Improve Airflow & Watering Habits", "step": "Keep the leaves dry", "when": "Every watering",
    "how": "Water the soil, not the leaves, in the morning. Give the plant space so air "
           "can move around it.",
}
BAKING_SODA = {
    "name": "Baking Soda Spray", "step": "Spray baking soda mix", "when": "Every 7 days",
    "how": "Mix 1 tablespoon of baking soda and ½ teaspoon of mild soap in 1 gallon of "
           "water. Spray all leaf surfaces.",
}
MILK_SPRAY = {
    "name": "Milk Spray", "step": "Spray diluted milk", "when": "Every 7 days",
    "how": "Mix 1 part milk with 2 parts water and spray the leaves on a sunny day. "
           "Works best at the first white spots.",
}
COMPOST_TEA = {
    "name": "Compost Tea", "step": "Feed with compost tea", "when": "Every 2 weeks",
    "how": "Soak a cup of compost or worm castings in 1 gallon of water for 24 hours, "
           "strain, and water the soil with it.",
}
ISOLATE = {
    "name": "Isolate the Plant", "step": "Move away from other plants", "when": "Today",
    "how": "Keep it apart until no new spots appear so the problem can't spread.",
}

# Not organic — never shown, even when the photo analysis suggests them.
NOT_ORGANIC = (
    "copper", "sulfur", "sulphur", "bordeaux", "mancozeb", "chlorothalonil", "imidacloprid",
    "permethrin", "bifenthrin", "malathion", "carbaryl", "glyphosate", "synthetic",
    "chemical fungicide", "chemical pesticide", "systemic",
)


def is_organic(treatment):
    text = " ".join(str(treatment.get(k, "")) for k in ("name", "step", "how")).lower()
    return not any(word in text for word in NOT_ORGANIC)


# The starting library, copied into the database by migration 0015.
# Admins manage the live list on the Diseases & Pests page.
DEFAULT_ISSUES = {
    # Pests ---------------------------------------------------------------
    "aphids": {
        "name": "Aphids", "type": "Pest",
        "symptoms": "Clusters of small green, black or white insects on new growth; sticky "
                    "honeydew; curled or yellowing leaves.",
        "treatments": [WATER_BLAST, INSECTICIDAL_SOAP, NEEM_OIL],
        "prevention": "Check new growth weekly, avoid over-feeding with nitrogen, and "
                      "encourage ladybirds outdoors.",
    },
    "spider_mites": {
        "name": "Spider Mites", "type": "Pest",
        "symptoms": "Fine webbing under leaves, tiny pale speckles (stippling), dusty-looking "
                    "or bronzed leaves.",
        "treatments": [WATER_BLAST, INSECTICIDAL_SOAP, NEEM_OIL, {
            "name": "Raise Humidity", "step": "Raise the humidity", "when": "Mist every other day",
            "how": "Mites love dry air. Group plants together or use a pebble tray.",
        }],
        "prevention": "Keep humidity up, wipe leaves monthly, and isolate new plants for 2 weeks.",
    },
    "mealybugs": {
        "name": "Mealybugs", "type": "Pest",
        "symptoms": "White cottony clumps in leaf joints and under leaves; sticky residue; "
                    "slow, weak growth.",
        "treatments": [ALCOHOL_SWAB, INSECTICIDAL_SOAP, NEEM_OIL],
        "prevention": "Inspect leaf joints regularly and quarantine new plants.",
    },
    "scale": {
        "name": "Scale Insects", "type": "Pest",
        "symptoms": "Small brown or tan bumps stuck to stems and leaf veins; sticky leaves; "
                    "yellowing.",
        "treatments": [{
            "name": "Scrape Off", "step": "Scrape scales off gently", "when": "Today",
            "how": "Use a fingernail or soft toothbrush, then wipe the area clean.",
        }, ALCOHOL_SWAB, NEEM_OIL],
        "prevention": "Check stems when watering; scale is easiest to clear when caught early.",
    },
    "whiteflies": {
        "name": "Whiteflies", "type": "Pest",
        "symptoms": "Clouds of tiny white flies when the plant is moved; yellowing leaves; "
                    "honeydew.",
        "treatments": [STICKY_TRAPS, INSECTICIDAL_SOAP, NEEM_OIL],
        "prevention": "Keep plants well ventilated and check leaf undersides weekly.",
    },
    "thrips": {
        "name": "Thrips", "type": "Pest",
        "symptoms": "Silvery streaks or patches on leaves, black specks of droppings, "
                    "distorted new growth.",
        "treatments": [{
            "name": "Blue or Yellow Sticky Traps", "step": "Hang blue sticky traps",
            "when": "Replace when full", "how": STICKY_TRAPS["how"],
        }, INSECTICIDAL_SOAP, NEEM_OIL],
        "prevention": "Remove plant debris and isolate infested plants straight away.",
    },
    "fungus_gnats": {
        "name": "Fungus Gnats", "type": "Pest",
        "symptoms": "Small black flies around the soil; larvae in the top layer of soil; "
                    "seedlings wilting.",
        "treatments": [{
            "name": "Let the Soil Dry Out", "step": "Let the soil dry", "when": "Between waterings",
            "how": "Let the top 2–3 cm dry completely — the larvae need moist soil.",
        }, STICKY_TRAPS, {
            "name": "BTI Soil Drench", "step": "Water with BTI soak", "when": "Every watering for 3–4 weeks",
            "how": "Soak mosquito bits (a natural soil bacterium) in water for 30 minutes and "
                   "water the plant with it.",
        }, {
            "name": "Sand Top Layer", "step": "Top the soil with sand", "when": "Once",
            "how": "Cover the soil with 1 cm of coarse sand so adults can't lay eggs.",
        }],
        "prevention": "Don't overwater and use a free-draining mix.",
    },
    "caterpillars": {
        "name": "Caterpillars", "type": "Pest",
        "symptoms": "Holes chewed in leaves, ragged edges, green or black droppings.",
        "treatments": [{
            "name": "Hand-Pick", "step": "Pick caterpillars off", "when": "Each evening",
            "how": "Check the leaves at dusk and remove caterpillars by hand.",
        }, {
            "name": "Bt (Bacillus thuringiensis kurstaki)", "step": "Spray Bt on leaves",
            "when": "Every 5–7 days",
            "how": "A natural soil bacterium that only affects caterpillars. Use the label rate.",
        }, NEEM_OIL],
        "prevention": "Use fine netting outdoors and check leaf undersides for eggs.",
    },

    # Diseases ------------------------------------------------------------
    "powdery_mildew": {
        "name": "Powdery Mildew", "type": "Fungal disease",
        "symptoms": "White or grey powdery patches on leaves and stems; leaves yellow and curl.",
        "treatments": [PRUNE_AFFECTED, BAKING_SODA, MILK_SPRAY, NEEM_OIL],
        "prevention": "Good airflow, morning watering at soil level, and avoid crowding.",
    },
    "leaf_spot": {
        "name": "Fungal Leaf Spot", "type": "Fungal disease",
        "symptoms": "Brown or black spots, often with a yellow halo, that grow and merge.",
        "treatments": [PRUNE_AFFECTED, AIRFLOW, BAKING_SODA, NEEM_OIL],
        "prevention": "Keep leaves dry and clear fallen leaves from the pot.",
    },
    "bacterial_leaf_spot": {
        "name": "Bacterial Leaf Spot", "type": "Bacterial disease",
        "symptoms": "Water-soaked, translucent spots that turn brown or black; may smell.",
        "treatments": [PRUNE_AFFECTED, {
            "name": "Stop Overhead Watering", "step": "Water only at the base", "when": "Every watering",
            "how": "Keep the plant out of the rain until it recovers — bacteria spread in splashes.",
        }, ISOLATE],
        "prevention": "Sterilise tools and avoid wetting the foliage.",
    },
    "root_rot": {
        "name": "Root Rot", "type": "Fungal disease",
        "symptoms": "Wilting despite wet soil, yellow lower leaves, mushy brown roots, sour smell.",
        "treatments": [{
            "name": "Trim & Repot", "step": "Trim mushy roots, repot", "when": "Today",
            "how": "Wash the roots, cut away every brown, mushy one with clean scissors, and "
                   "repot in fresh, free-draining mix.",
        }, {
            "name": "Cinnamon on Cut Roots", "step": "Dust roots with cinnamon", "when": "When repotting",
            "how": "Ground cinnamon is a gentle natural antifungal.",
        }, {
            "name": "Water Less", "step": "Water much less", "when": "Until new growth",
            "how": "Wait until the top half of the soil is dry. Don't feed until new leaves appear.",
        }],
        "prevention": "Use pots with drainage holes and check the soil before every watering.",
    },
    "gray_mold": {
        "name": "Grey Mould (Botrytis)", "type": "Fungal disease",
        "symptoms": "Fuzzy grey growth on flowers, buds or leaves; soft brown rot.",
        "treatments": [PRUNE_AFFECTED, AIRFLOW, BAKING_SODA],
        "prevention": "Remove dead flowers promptly and avoid cool, damp, still air.",
    },
    "rust": {
        "name": "Rust", "type": "Fungal disease",
        "symptoms": "Orange, rusty or brown powdery pustules, mostly under the leaves.",
        "treatments": [PRUNE_AFFECTED, NEEM_OIL, BAKING_SODA],
        "prevention": "Water at soil level and give plants room to breathe.",
    },

    # Care & nutrition ----------------------------------------------------
    "overwatering": {
        "name": "Overwatering", "type": "Care problem",
        "symptoms": "Yellow, soft or drooping leaves with soggy soil; mould on the soil surface.",
        "treatments": [{
            "name": "Let It Dry", "step": "Let the soil dry", "when": "Until top 3–5 cm is dry",
            "how": "Skip watering, empty the saucer and make sure the pot drains.",
        }, {
            "name": "Check the Roots", "step": "Check roots for rot", "when": "If leaves keep yellowing",
            "how": "Unpot and look for mushy roots — treat as root rot if you find them.",
        }],
        "prevention": "Water by checking the soil, not by the calendar alone.",
    },
    "underwatering": {
        "name": "Underwatering", "type": "Care problem",
        "symptoms": "Crispy brown edges, drooping leaves, dry soil pulling away from the pot.",
        "treatments": [{
            "name": "Soak & Drain", "step": "Soak pot, then drain", "when": "Today",
            "how": "Stand the pot in water for 20–30 minutes, then let it drain fully.",
        }, {
            "name": "Water More Regularly", "step": "Water more often", "when": "Check every few days",
            "how": "Shorten the watering interval and feel the soil before each watering.",
        }],
        "prevention": "Mulch outdoor plants and group indoor plants to slow drying.",
    },
    "sunburn": {
        "name": "Sunburn / Leaf Scorch", "type": "Care problem",
        "symptoms": "Bleached, white or brown crispy patches on the leaves facing the light.",
        "treatments": [{
            "name": "Move to Gentler Light", "step": "Move to softer light", "when": "Today",
            "how": "Bright, indirect light, then build up to stronger sun over 1–2 weeks. "
                   "Scorched patches won't recover — trim them if you like.",
        }],
        "prevention": "Introduce plants to direct sun slowly and use a sheer curtain in summer.",
    },
    "nutrient_deficiency": {
        "name": "Nutrient Deficiency", "type": "Care problem",
        "symptoms": "Pale or yellow older leaves (nitrogen), yellow between green veins on new "
                    "leaves (iron/magnesium), slow growth.",
        "treatments": [COMPOST_TEA, {
            "name": "Worm Castings", "step": "Add worm castings on top", "when": "Every 2 months",
            "how": "Spread 1–2 cm of worm castings on the soil and water in.",
        }, {
            "name": "Seaweed / Fish Emulsion", "step": "Feed liquid seaweed", "when": "Every 2–4 weeks",
            "how": "Use liquid seaweed or fish emulsion, about 1 tablespoon per gallon of water.",
        }],
        "prevention": "Repot every 1–2 years in fresh mix and feed during spring and summer.",
    },
}

class _Library(Mapping):
    """key -> issue dict, read from the PlantIssue table on each use (always current)."""

    def _load(self):
        from .models import PlantIssue
        return {issue.key: issue.as_dict() for issue in PlantIssue.objects.all()}

    def __getitem__(self, key):
        from .models import PlantIssue
        issue = PlantIssue.objects.filter(key=key).first()
        if issue is None:
            raise KeyError(key)
        return issue.as_dict()

    def __contains__(self, key):
        from .models import PlantIssue
        return isinstance(key, str) and bool(key) and PlantIssue.objects.filter(key=key).exists()

    def __iter__(self):
        return iter(self._load())

    def __len__(self):
        from .models import PlantIssue
        return PlantIssue.objects.count()

    def items(self):
        return self._load().items()

    def values(self):
        return self._load().values()


ISSUES = _Library()


def choices():
    """(key, name) pairs for the issue drop-downs, A-Z."""
    from .models import PlantIssue
    return list(PlantIssue.objects.values_list("key", "name"))


def get(key):
    return ISSUES.get(key) if key else None
