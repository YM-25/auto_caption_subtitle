"""
AI Service for Prompt Expansion and Translation using Gemini and ChatGPT.
Enhanced with ChatGPT Engineering Spec:
- Provider Normalization (gpt/gemini aliases)
- System + User Prompt Architecture
- Keyword Bag Sanitization
- Deep Glossary Integration
- GPT-5 Temperature compatibility guard & cache
"""
from __future__ import annotations
import os
import re
from typing import Optional

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# Cache for models that reject temperature
_NO_TEMPERATURE_MODELS: set[str] = set()

def _normalize_provider(provider: str) -> str:
    """Normalize provider names to 'gpt' or 'gemini'."""
    p = str(provider).lower().strip()
    if p in ("gpt", "openai", "chatgpt", "gpt-4", "gpt-5"):
        return "gpt"
    if p in ("gemini", "google", "google-gemini"):
        return "gemini"
    return p

def should_send_temperature(
    provider: str,
    model: str,
    reasoning_effort: Optional[str] = None,
) -> bool:
    """
    OpenAI compatibility rule:
    - GPT-5 family often doesn't support temperature.
    - GPT-5.2 only supports it if reasoning_effort is none.
    """
    provider = _normalize_provider(provider)
    model = (model or "").strip()

    if provider != "gpt":
        return True  # Gemini supports temperature

    if model in _NO_TEMPERATURE_MODELS:
        return False

    # Older/Base GPT-5 family models do NOT support temperature
    if model.startswith("gpt-5") and not model.startswith("gpt-5.2"):
        return False

    # GPT-5.2 supports sampling only when reasoning_effort is none
    if model.startswith("gpt-5.2"):
        eff = (reasoning_effort or "none").strip().lower()
        return eff == "none"

    return True

def _is_temperature_unsupported_error(err: Exception) -> bool:
    msg = str(err).lower()
    return "temperature" in msg and ("unsupported" in msg or "only the default" in msg)

def call_openai_chat_completions_with_guard(
    client,
    *,
    model: str,
    messages: list[dict],
    temperature: float,
    max_completion_tokens: int,
    reasoning_effort: Optional[str] = None,
    **extra_kwargs,
) -> str:
    """
    Executes OpenAI request with temperature guard and one-time retry without temperature.
    """
    kwargs = dict(
        model=model,
        messages=messages,
        max_completion_tokens=max_completion_tokens,
        **extra_kwargs,
    )

    if should_send_temperature("gpt", model, reasoning_effort):
        kwargs["temperature"] = temperature

    try:
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
    except Exception as e:
        # If temperature is unsupported, cache and retry once
        if _is_temperature_unsupported_error(e):
            print(f"DEBUG: Model {model} does not support temperature. Retrying without it...")
            _NO_TEMPERATURE_MODELS.add(model)
            kwargs.pop("temperature", None)
            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        raise

def _sanitize_keywords(text, max_keywords=40):
    """Clean up AI-generated keyword strings for Whisper consumption."""
    if not text:
        return ""
    # Split by common separators
    raw_list = re.split(r'[,\n;，]', text)
    # Strip, remove empty, and deduplicate
    clean_list = []
    seen = set()
    for k in raw_list:
        # Remove markdown bold/italic and quotes
        k = k.strip().strip('"').strip("'").strip("*").strip("-").strip("_")
        if k and k.lower() not in seen:
            clean_list.append(k)
            seen.add(k.lower())
    
    # Limit to max_keywords
    final_list = clean_list[:max_keywords]
    return ", ".join(final_list)

def expand_prompt(filename, user_prompt=None, provider="gemini", api_key=None, model=None, glossary=None):
    """
    Expand a simple prompt/filename into a rich background context for Whisper.
    """
    if not api_key:
        return user_prompt or ""

    provider_id = _normalize_provider(provider)
    default_models = {"gemini": "gemini-3-flash", "gpt": "gpt-5-mini"}
    active_model = model if model else default_models.get(provider_id)

    # SYSTEM PROMPT
    system_instruction = (
        "You generate a compact keyword bag to help a speech-to-text model correctly recognize technical terms and proper nouns.\n\n"
        "Rules:\n"
        "- Output ONLY a single line of comma-separated keywords.\n"
        "- No sentences, no explanations, no numbering, no quotes, no brackets.\n"
        "- Prefer: technical terms, proper names, acronyms, product/library names, datasets, version numbers.\n"
        "- Avoid generic filler words. Avoid duplicates.\n"
        "- 20–80 keywords total.\n"
        "- If glossary terms are provided, include them verbatim (do NOT translate glossary terms)."
    )

    # USER PROMPT
    glossary_terms = ""
    if glossary:
        glossary_terms = "\n".join(glossary.keys())

    prompt_msg = f"Video title / filename: {filename}\n"
    if user_prompt:
        prompt_msg += f"User context (optional): {user_prompt}\n"
    
    if glossary_terms:
        prompt_msg += f"\nGlossary terms (optional, verbatim; one per line):\n{glossary_terms}"

    try:
        if provider_id == "gemini" and HAS_GEMINI:
            genai.configure(api_key=api_key)
            genai_model = genai.GenerativeModel(active_model, system_instruction=system_instruction)
            response = genai_model.generate_content(prompt_msg, generation_config={"temperature": 0.2, "max_output_tokens": 300})
            keywords = _sanitize_keywords(response.text.strip(), max_keywords=80)
        
        elif provider_id == "gpt" and HAS_OPENAI:
            client = OpenAI(api_key=api_key)
            content = call_openai_chat_completions_with_guard(
                client,
                model=active_model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt_msg}
                ],
                temperature=0.2,
                max_completion_tokens=300
            )
            keywords = _sanitize_keywords(content, max_keywords=80)
        else:
            return user_prompt or ""

        # Final Formatting for Whisper
        if not keywords:
            return user_prompt or ""
        
        if user_prompt:
            return f"{user_prompt}\nKeywords: {keywords}"
        else:
            return f"Keywords: {keywords}"

    except Exception as e:
        print(f"AI Prompt Expansion Error ({provider_id}): {e}")
        print(f"Falling back to default prompt: {user_prompt or '[No Prompt]'}")
        return user_prompt or ""

def ai_translate_text(text, target_lang, provider="gemini", api_key=None, model=None, glossary=None):
    """
    Single block translation via AI with strict system rules and glossary injection.
    """
    if not api_key:
        return None
    
    if not text.strip():
        return text

    provider_id = _normalize_provider(provider)
    default_models = {"gemini": "gemini-3-flash", "gpt": "gpt-5-mini"}
    active_model = model if model else default_models.get(provider_id)

    # SYSTEM PROMPT
    system_instruction = (
        "You are translating subtitle text.\n\n"
        "Rules:\n"
        "- Output ONLY the translated text. No preamble, no quotes, no extra commentary.\n"
        "- Preserve line breaks exactly.\n"
        "- Preserve tone and register (formal/informal) from the source.\n"
        "- Keep proper nouns consistent; follow the glossary if provided.\n"
        "- If target language is English, use British spelling."
    )

    # USER PROMPT
    glossary_map = ""
    if glossary:
        glossary_map = "\n".join([f"{k} = {v}" for k, v in glossary.items()])

    prompt_msg = f"Target language: {target_lang}\n\n"
    if glossary_map:
        prompt_msg += f"Glossary (optional, term = preferred translation):\n{glossary_map}\n\n"
    
    prompt_msg += f"Text:\n{text}"

    try:
        if provider_id == "gemini" and HAS_GEMINI:
            genai.configure(api_key=api_key)
            genai_model = genai.GenerativeModel(active_model, system_instruction=system_instruction)
            response = genai_model.generate_content(prompt_msg, generation_config={"temperature": 0.2, "max_output_tokens": 2048})
            return response.text.strip()
        
        elif provider_id == "gpt" and HAS_OPENAI:
            client = OpenAI(api_key=api_key)
            return call_openai_chat_completions_with_guard(
                client,
                model=active_model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt_msg}
                ],
                temperature=0.2,
                max_completion_tokens=2048
            )

    except Exception as e:
        print(f"AI Translation Error ({provider_id}): {e}")
        print("Falling back to offline (Google) translation...")
    
    return None

def verify_api_key(provider, api_key):
    """
    Verify if the API key is valid by making a minimal request.
    """
    if not api_key:
        return False, "API Key is empty."

    provider_id = _normalize_provider(provider)
    
    try:
        if provider_id == "gemini":
            if not HAS_GEMINI:
                return False, "Gemini library not installed."
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content("Hi", generation_config={"max_output_tokens": 5})
            if response and response.text:
                return True, "Success"
            return False, "No response from Gemini."

        elif provider_id == "gpt":
            if not HAS_OPENAI:
                return False, "OpenAI library not installed."
            try:
                client = OpenAI(api_key=api_key)
                content = call_openai_chat_completions_with_guard(
                    client,
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=0.7,
                    max_completion_tokens=5
                )
                if content:
                    return True, "Success"
                return False, "No response from OpenAI."
            except Exception as e:
                return False, f"OpenAI Error: {str(e)}"

    except Exception as e:
        error_msg = str(e)
        if "API_KEY_INVALID" in error_msg or "invalid_api_key" in error_msg or "401" in error_msg:
            return False, "Invalid API Key."
        return False, f"Connection Failed: {error_msg[:100]}..."

    return False, "Unknown provider."
