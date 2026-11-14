"""Common plant problems and their organic treatments.

Used when the user already knows the problem, and to back up what the photo
analysis finds with tried-and-tested organic remedies. Always test a spray on
one leaf first and apply in the evening or out of direct sun.
"""

# Reusable treatments ---------------------------------------------------------

NEEM_OIL = {
    "name": "Neem Oil",
    "how": "Derived from the neem tree, this disrupts insect hormones and manages "
           "soft-bodied pests like aphids, whiteflies, thrips, and caterpillars. Mix 1–2 "
           "tablespoons per gallon of water (plus a few drops of mild liquid soap so it "
           "mixes) and apply weekly, covering the undersides of leaves.",
}
INSECTICIDAL_SOAP = {
    "name": "Insecticidal Soap",
    "how": "Mix 1 tablespoon of pure castile soap per litre of water (about 5 tablespoons "
           "per gallon). Spray pests directly until dripping — it only works on contact. "
           "Repeat every 5–7 days for 3 weeks to catch new hatchlings.",
}
WATER_BLAST = {
    "name": "Strong Water Spray",
    "how": "Knock pests off with a firm spray of lukewarm water, especially under leaves "
           "and along stems. Repeat every 2–3 days for a week.",
}
ALCOHOL_SWAB = {
    "name": "Rubbing Alcohol Swab",
    "how": "Dab each pest with a cotton swab dipped in 70% isopropyl alcohol. For larger "
           "outbreaks spray 1 part alcohol to 3 parts water. Repeat weekly until gone.",
}
STICKY_TRAPS = {
    "name": "Yellow Sticky Traps",
    "how": "Place yellow sticky cards just above the soil or among the leaves to catch "
           "flying adults and track whether numbers are falling. Replace when full.",
}
PRUNE_AFFECTED = {
    "name": "Remove Affected Leaves",
    "how": "Cut off badly affected leaves with clean scissors (wipe blades with alcohol "
           "between cuts) and bin them — don't compost diseased material.",
}
AIRFLOW = {
    "name": "Improve Airflow & Watering Habits",
    "how": "Space plants apart, water at soil level in the morning and keep leaves dry so "
           "fungal spores can't take hold.",
}
BAKING_SODA = {
    "name": "Baking Soda Spray",
    "how": "Mix 1 tablespoon of baking soda and ½ teaspoon of liquid soap in 1 gallon of "
           "water. Spray all leaf surfaces every 7 days; it raises leaf pH so mildew "
           "can't spread.",
}
MILK_SPRAY = {
    "name": "Milk Spray",
    "how": "Mix 1 part milk with 2 parts water and spray leaves in sunlight once a week. "
           "Works best as prevention or at the first white spots.",
}
COPPER = {
    "name": "Copper Fungicide (organic-approved)",
    "how": "Use a copper soap product approved for organic gardening, following the label "
           "rate. Spray every 7–10 days in wet weather. Use sparingly — copper builds up "
           "in soil.",
}
COMPOST_TEA = {
    "name": "Compost Tea",
    "how": "Steep a cup of mature compost or worm castings in a gallon of water for 24 "
           "hours, strain, and water the soil every 2 weeks.",
}


ISSUES = {
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
            "name": "Raise Humidity",
            "how": "Mites love dry air. Group plants, use a pebble tray or humidifier, and "
                   "mist the leaves every other day while treating.",
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
            "name": "Scrape Off",
            "how": "Gently scrape scales off with a fingernail or soft toothbrush, then wipe "
                   "the area clean.",
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
            "name": "Blue or Yellow Sticky Traps",
            "how": STICKY_TRAPS["how"],
        }, INSECTICIDAL_SOAP, NEEM_OIL],
        "prevention": "Remove plant debris and isolate infested plants straight away.",
    },
    "fungus_gnats": {
        "name": "Fungus Gnats", "type": "Pest",
        "symptoms": "Small black flies around the soil; larvae in the top layer of soil; "
                    "seedlings wilting.",
        "treatments": [{
            "name": "Let the Soil Dry Out",
            "how": "Allow the top 2–3 cm of soil to dry completely between waterings — the "
                   "larvae need moist soil. Bottom-water while treating.",
        }, STICKY_TRAPS, {
            "name": "BTI Soil Drench",
            "how": "Soak Bacillus thuringiensis israelensis (e.g. mosquito bits) in water "
                   "for 30 minutes and use that water for the plant. Repeat every watering "
                   "for 3–4 weeks.",
        }, {
            "name": "Sand Top Layer",
            "how": "Cover the soil with 1 cm of coarse sand so adults can't lay eggs.",
        }],
        "prevention": "Don't overwater and use a free-draining mix.",
    },
    "caterpillars": {
        "name": "Caterpillars", "type": "Pest",
        "symptoms": "Holes chewed in leaves, ragged edges, green or black droppings.",
        "treatments": [{
            "name": "Hand-Pick",
            "how": "Check leaves at dusk and remove caterpillars by hand.",
        }, {
            "name": "Bt (Bacillus thuringiensis kurstaki)",
            "how": "A natural soil bacterium that only affects caterpillars. Spray leaves "
                   "following the label rate every 5–7 days while they're feeding.",
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
        "treatments": [PRUNE_AFFECTED, AIRFLOW, COPPER],
        "prevention": "Keep leaves dry and clear fallen leaves from the pot.",
    },
    "bacterial_leaf_spot": {
        "name": "Bacterial Leaf Spot", "type": "Bacterial disease",
        "symptoms": "Water-soaked, translucent spots that turn brown or black; may smell.",
        "treatments": [PRUNE_AFFECTED, {
            "name": "Stop Overhead Watering",
            "how": "Water only at the base and keep the plant out of rain until it recovers; "
                   "bacteria spread in water splashes.",
        }, COPPER],
        "prevention": "Sterilise tools and avoid wetting the foliage.",
    },
    "root_rot": {
        "name": "Root Rot", "type": "Fungal disease",
        "symptoms": "Wilting despite wet soil, yellow lower leaves, mushy brown roots, sour smell.",
        "treatments": [{
            "name": "Trim & Repot",
            "how": "Unpot the plant, wash the roots, and cut away every brown, mushy root "
                   "with sterile scissors. Repot in fresh, free-draining mix in a pot with "
                   "drainage holes.",
        }, {
            "name": "Cinnamon on Cut Roots",
            "how": "Dust the trimmed roots with ground cinnamon, a gentle natural antifungal, "
                   "before repotting.",
        }, {
            "name": "Water Less",
            "how": "Wait until the top half of the soil is dry before watering again. Don't "
                   "fertilise until new growth appears.",
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
        "treatments": [PRUNE_AFFECTED, NEEM_OIL, COPPER],
        "prevention": "Water at soil level and give plants room to breathe.",
    },

    # Care & nutrition ----------------------------------------------------
    "overwatering": {
        "name": "Overwatering", "type": "Care problem",
        "symptoms": "Yellow, soft or drooping leaves with soggy soil; mould on the soil surface.",
        "treatments": [{
            "name": "Let It Dry",
            "how": "Skip watering until the top 3–5 cm of soil is dry. Empty saucers and "
                   "make sure the pot drains.",
        }, {
            "name": "Check the Roots",
            "how": "If leaves keep yellowing, unpot and look for mushy roots — treat as root "
                   "rot if you find them.",
        }],
        "prevention": "Water by checking the soil, not by the calendar alone.",
    },
    "underwatering": {
        "name": "Underwatering", "type": "Care problem",
        "symptoms": "Crispy brown edges, drooping leaves, dry soil pulling away from the pot.",
        "treatments": [{
            "name": "Soak & Drain",
            "how": "Stand the pot in a bowl of water for 20–30 minutes until the soil is "
                   "evenly moist, then let it drain fully.",
        }, {
            "name": "Water More Regularly",
            "how": "Shorten the watering interval and check the soil every few days.",
        }],
        "prevention": "Mulch outdoor plants and group indoor plants to slow drying.",
    },
    "sunburn": {
        "name": "Sunburn / Leaf Scorch", "type": "Care problem",
        "symptoms": "Bleached, white or brown crispy patches on the leaves facing the light.",
        "treatments": [{
            "name": "Move to Gentler Light",
            "how": "Shift the plant to bright, indirect light. Acclimatise it to stronger sun "
                   "gradually over 1–2 weeks. Scorched patches won't recover — trim them if "
                   "unsightly.",
        }],
        "prevention": "Introduce plants to direct sun slowly and use a sheer curtain in summer.",
    },
    "nutrient_deficiency": {
        "name": "Nutrient Deficiency", "type": "Care problem",
        "symptoms": "Pale or yellow older leaves (nitrogen), yellow between green veins on new "
                    "leaves (iron/magnesium), slow growth.",
        "treatments": [COMPOST_TEA, {
            "name": "Worm Castings",
            "how": "Top-dress the soil with 1–2 cm of worm castings and water in. Repeat "
                   "every 2 months in the growing season.",
        }, {
            "name": "Seaweed / Fish Emulsion",
            "how": "Feed with liquid seaweed or fish emulsion at the label rate (typically "
                   "about 1 tablespoon per gallon) every 2–4 weeks while growing.",
        }],
        "prevention": "Repot every 1–2 years in fresh mix and feed during spring and summer.",
    },
}

CHOICES = [(key, issue["name"]) for key, issue in ISSUES.items()]


def get(key):
    return ISSUES.get(key)
