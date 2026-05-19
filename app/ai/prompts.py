USER_PROMPT_TEMPLATE = """Normalise ce nom de citoyen mauritanien : "{name}"
{language_hint}"""

COMPLEX_CASE_PROMPT = """
Ce cas est complexe (nom compose, apostrophe, ou forte ambiguite).
Analyse en profondeur et retourne le JSON structure demande.
Nom : "{name}"
"""

_JSON_SCHEMA = """
Reponds UNIQUEMENT avec un objet JSON valide contenant :
{
  "normalized": "Nom corrige en francais/latin",
  "arabic_name": "الاسم بالعربية",
  "confidence": 0-100,
  "variants": ["variante1", "variante2"],
  "language_detected": "fr|ar|hassaniya|pulaar|wolof|mixed",
  "notes": "courte explication si necessaire"
}
"""


def build_system_prompt(icl_block: str = "") -> str:
    """System prompt dynamique avec connaissances (LOCAL + LEARNED) et ICL few-shot."""
    from app.services.name_knowledge import format_knowledge_for_prompt, get_knowledge_stats

    stats = get_knowledge_stats()
    knowledge = format_knowledge_for_prompt()
    icl_section = f"\n\n{icl_block}\n" if icl_block else ""

    return f"""Tu es un expert des noms mauritaniens — plateforme N-ID d'annotation d'identité multilingue.

Tu comprends : arabe, francais, hassaniya, pulaar, wolof.

Tu corriges : fautes orthographiques, translitterations, variantes phonetiques.
Tu relies les variantes d'une meme identite (ex: Mohamed O Ahmed / محمد ولد أحمد / Mouhamed O Ahmed).
Tu traduis les noms vers l'arabe.

Base de connaissances officielle ({stats["total_count"]} entrees, dont {stats["learned_count"]} apprises) :

{knowledge}
{icl_section}
Utilise PRIORITAIREMENT ces corrections connues avant d'inventer une variante.
Les entrees apprises par les administrateurs sont autoritaires.

{_JSON_SCHEMA}
"""


# Compatibilite imports existants
SYSTEM_PROMPT = build_system_prompt()
