"""Gold evaluation set: questions mapped to the chunk(s) that should answer them.

Truth is labeled at (source_id, section) granularity — i.e. the specific section a
correct answer lives in, not just the right document. Routing among 7 documents is
trivial, so source-level metrics saturate and can't tell the retrieval strategies
apart; picking the right section among a document's three is the real ranking task,
and the granularity that matters because chunks (not whole docs) feed the prompt.

`relevant` is a set of (source_id, section) tuples — a hit is any one of them.
"""
from __future__ import annotations

GOLD: list[dict] = [
    # Protein (sections: Daily protein intake / Per-meal dose and distribution /
    # Timing and source quality)
    {"q": "How much protein per kilogram should I eat to build muscle?",
     "relevant": {("issn-protein-2017", "Daily protein intake")}},
    {"q": "What's the best amount of protein to eat in a single meal?",
     "relevant": {("issn-protein-2017", "Per-meal dose and distribution")}},
    {"q": "Is it worth having a protein shake before bed?",
     "relevant": {("issn-protein-2017", "Timing and source quality"),
                  ("issn-nutrient-timing-2017", "Practical priorities")}},
    {"q": "Which protein sources are best for muscle growth?",
     "relevant": {("issn-protein-2017", "Timing and source quality")}},
    # Creatine (What creatine does / Dosing protocols / Safety)
    {"q": "How do I load creatine when I start taking it?",
     "relevant": {("issn-creatine-2017", "Dosing protocols")}},
    {"q": "Will creatine damage my kidneys?",
     "relevant": {("issn-creatine-2017", "Safety")}},
    {"q": "Which form of creatine actually works?",
     "relevant": {("issn-creatine-2017", "What creatine does")}},
    {"q": "Why did I gain weight in my first week on creatine?",
     "relevant": {("issn-creatine-2017", "Safety")}},
    # Caffeine (Performance effects / Dosing and timing / Individual variation)
    {"q": "How much caffeine should I take before training?",
     "relevant": {("issn-caffeine-2021", "Dosing and timing")}},
    {"q": "Does coffee actually help endurance performance?",
     "relevant": {("issn-caffeine-2021", "Performance effects")}},
    {"q": "How long before a workout should I have caffeine?",
     "relevant": {("issn-caffeine-2021", "Dosing and timing")}},
    {"q": "Why do some people respond to caffeine more than others?",
     "relevant": {("issn-caffeine-2021", "Individual variation")}},
    # Nutrient timing (Carbohydrate timing and glycogen / Protein timing /
    # Practical priorities)
    {"q": "How much carbohydrate do I need to refill glycogen after training?",
     "relevant": {("issn-nutrient-timing-2017", "Carbohydrate timing and glycogen")}},
    {"q": "Is the post-workout anabolic window real?",
     "relevant": {("issn-nutrient-timing-2017", "Protein timing")}},
    # Diets & body composition (Energy balance is the foundation / Protein during
    # fat loss / Rate of weight change)
    {"q": "How fast can I lose weight without losing muscle?",
     "relevant": {("issn-diets-body-composition-2017", "Rate of weight change")}},
    {"q": "Does it matter whether I go low-carb or low-fat to lose fat?",
     "relevant": {("issn-diets-body-composition-2017", "Energy balance is the foundation")}},
    {"q": "How much protein should I eat while cutting?",
     "relevant": {("issn-diets-body-composition-2017", "Protein during fat loss")}},
    # Beta-alanine (Mechanism / Dosing / Performance effects)
    {"q": "What does beta-alanine do for performance?",
     "relevant": {("issn-beta-alanine-2015", "Performance effects")}},
    {"q": "What dose of beta-alanine increases muscle carnosine?",
     "relevant": {("issn-beta-alanine-2015", "Dosing")}},
    {"q": "Why does my pre-workout make my skin tingle?",
     "relevant": {("issn-beta-alanine-2015", "Dosing")}},
    # Meal frequency (Meal frequency and body composition / Athletes and energy
    # restriction / Protein distribution)
    {"q": "Does eating more often boost my metabolism?",
     "relevant": {("issn-meal-frequency-2011", "Meal frequency and body composition")}},
    {"q": "How many meals a day is best for body composition?",
     "relevant": {("issn-meal-frequency-2011", "Meal frequency and body composition")}},
    {"q": "Should I spread my protein across several meals?",
     "relevant": {("issn-meal-frequency-2011", "Protein distribution"),
                  ("issn-protein-2017", "Per-meal dose and distribution")}},
]
