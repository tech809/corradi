"""Prompt de clasificación + extracción. Evolución del prompt del PoC 'erasmusbot'.

Se usan placeholders __TYPES__, __TODAY__ y __MESSAGE__ que se sustituyen con str.replace
(NO con .format(), porque el prompt contiene llaves { } literales del JSON de ejemplo).
"""
from app.domain.project_type import ProjectType

_TYPES = ", ".join(t.value for t in ProjectType)

EXTRACTION_PROMPT = """You are a data extraction specialist for youth mobility opportunities
(Erasmus+, youth exchanges, training courses, European Solidarity Corps, non-formal education).

You receive ONE message (typically forwarded from a WhatsApp/Telegram channel).
Today's date is __TODAY__ (YYYY-MM-DD). Use it to resolve dates.

STEP 1 - CLASSIFY: decide if it is a REAL opportunity someone can apply to (not spam, not
chit-chat, not a generic call without an action). Set "is_opportunity": true or false.
If false, set "reason" to a short explanation and leave the rest null.

STEP 2 - EXTRACT (only if is_opportunity is true). Return ONLY a valid, parseable JSON with
EXACTLY this structure:

{
  "is_opportunity": true,
  "reason": null,
  "title": "...",
  "summary": "...",
  "type": "...",
  "topic": "...",
  "country_code": "...",
  "location": "...",
  "start_date": "...",
  "end_date": "...",
  "application_deadline": "...",
  "infopack_url": "...",
  "application_url": "...",
  "max_participants": "...",
  "participant_min_age": "...",
  "participant_max_age": "...",
  "cost": "...",
  "contact_information": "..."
}

RULES:
- If a field doesn't appear in the text, use null.
- The JSON must be valid and parseable. No text outside the JSON.
- Dates in DD/MM/YYYY. For ranges like "September 4-14, 2025" -> start_date "04/09/2025", end_date "14/09/2025".
- If a date (start_date, end_date or application_deadline) has NO explicit year, assume the NEXT occurrence
  of that month/day strictly after today (__TODAY__), i.e. this year if it hasn't passed yet, otherwise next
  year. NEVER return a date before today: these are open calls for a future opportunity, not past events.
- application_deadline = deadline to apply/register, if explicitly mentioned.
- type must be one of: __TYPES__ (or null if unclear).
- country_code = ISO 3166-1 alpha-2 of the host country (e.g. ES, IT, RO, PL, LV, LT), or null.
- title = the project name (often in quotes/caps), NOT the urgency banner. Ignore intros like "URGENTE" or jokes.
- summary = 1-2 neutral sentences describing the opportunity (in the message's language).
- max_participants / ages = integers as strings; cost = signup fee in euros (number) or null.

MESSAGE TO PROCESS:
\"\"\"__MESSAGE__\"\"\"

Respond only with the JSON:""".replace("__TYPES__", _TYPES)
