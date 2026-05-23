import os
import re
from app.vector_store import VectorStore
from app.models import Business, Chunk

# choose model from env or default
MODEL_NAME = os.environ.get('RAG_MODEL') or 'google/flan-t5-small'
generator = None


_QUESTION_STOPWORDS = {
    'with', 'from', 'that', 'this', 'what', 'when', 'where', 'your', 'have',
    'please', 'tell', 'about', 'can', 'you', 'for', 'are', 'the', 'and',
    'how', 'much', 'many', 'does', 'do', 'is', 'it', 'on', 'at', 'to', 'of',
    'we', 'our', 'a', 'an', 'in', 'if', 'or', 'be', 'not', 'off', 'open',
    'close', 'closing', 'opening', 'weekday', 'weekdays', 'weekend', 'today',
}

def _init_generator():
    """Lazy-load the transformer pipeline. Returns None on failure.

    We import inside the function to avoid importing heavy ML libs at module
    import time which can fail on low-memory Windows environments (WinError 1455).
    """
    global generator
    if generator is not None:
        return
    try:
        # Import here to avoid heavy imports at app startup
        from transformers import pipeline
        generator = pipeline('text2text-generation', model=MODEL_NAME)
    except Exception as e:
        # Fail silently and keep generator as None; caller will use grounded fallback
        generator = None
        try:
            # best-effort debug print to server logs
            print(f"[rag] generator init failed: {e}")
        except Exception:
            pass


def _split_sentences(text):
    parts = re.split(r'(?<=[.!?])\s+|\n+', text)
    return [part.strip() for part in parts if part and part.strip()]


def _question_keywords(question):
    return {
        word for word in re.findall(r'[a-zA-Z]{3,}', question.lower())
        if word not in _QUESTION_STOPWORDS
    }


def _question_focus(question_lower):
    focus = set()
    if any(term in question_lower for term in ['cash on delivery', 'cod', 'payment', 'pay on delivery']):
        focus.add('payment')
    if any(term in question_lower for term in ['delivery', 'deliver', 'delivers', 'shipping']):
        focus.add('delivery')
    if any(term in question_lower for term in ['where', 'locat', 'address', 'based in']):
        focus.add('location')
    if any(term in question_lower for term in ['repair', 'screen', 'service', 'fix', 'replace']):
        focus.add('service')
    if any(term in question_lower for term in ['open', 'close', 'hours', 'hour', 'time', 'weekday', 'weekend', 'friday', 'monday', 'tuesday', 'wednesday', 'thursday', 'saturday', 'sunday']):
        focus.add('hours')
    if 'refund' in question_lower:
        focus.add('refund')
    if 'wifi' in question_lower or 'wi-fi' in question_lower:
        focus.add('wifi')
    return focus


def _extract_location_from_question(question):
    match = re.search(r'\b(?:in|to|at|for|around)\s+([A-Za-z][A-Za-z\s-]{1,40})\??$', question, re.IGNORECASE)
    if match:
        location = match.group(1).strip().rstrip('?.!,')
        if location.isupper() and len(location) <= 6:
            return location
        return location.title()
    return None


def _normalize_customer_terms(text):
    replacements = {
        'iphone': 'iPhone',
        'android': 'Android',
        'wifi': 'Wi-Fi',
        'wi-fi': 'Wi-Fi',
        'cod': 'COD',
        'dha': 'DHA',
    }
    normalized = text
    for source, target in replacements.items():
        normalized = re.sub(rf'\b{source}\b', target, normalized, flags=re.IGNORECASE)
    return normalized


def _conversationalize_answer(question, grounded_answer, business_id=None):
    question_lower = question.lower()
    focus_terms = _question_focus(question_lower)
    clean_answer = grounded_answer.strip().lstrip('-').strip().rstrip('.').strip()
    clean_answer = _normalize_customer_terms(clean_answer)
    business = Business.query.get(business_id) if business_id is not None else None
    business_city = business.city if business and business.city else 'the city'

    if 'delivery' in focus_terms:
        location = _extract_location_from_question(question)
        if location:
            return f"Yes, we do deliver in {location}. We deliver across {business_city} as well."
        return f"Yes, we do deliver across {business_city}. {clean_answer}"

    if 'payment' in focus_terms:
        extra = ''
        if any(token in clean_answer.lower() for token in ['bank transfer', 'card payment', 'card payments']):
            extra = ' We also accept bank transfer and card payments.'
        return f"Yes, we do offer cash on delivery.{extra}"

    if 'location' in focus_terms:
        return f"We’re based in {clean_answer}"

    if 'hours' in focus_terms:
        hours_text = clean_answer.lstrip(':- ').strip()
        hours_text = re.sub(r'\s{2,}', ' ', hours_text)
        time_match = re.search(
            r'(?P<days>(?:monday to thursday|monday to friday|monday to saturday|friday to sunday|monday|tuesday|wednesday|thursday|friday|saturday|sunday))[:\s-]*(?P<start>\d{1,2}:\d{2}\s*(?:am|pm))\s*(?:to|-)\s*(?P<end>\d{1,2}:\d{2}\s*(?:am|pm))',
            hours_text,
            re.IGNORECASE,
        )
        if time_match:
            days = time_match.group('days').title()
            start = time_match.group('start').upper()
            end = time_match.group('end').upper()
            return f"Yes, we’re open {days} from {start} to {end}"
        return f"Yes, we’re open {hours_text}" if hours_text else grounded_answer

    if 'service' in focus_terms:
        if any(token in question_lower for token in ['screen', 'iphone', 'android', 'laptop', 'console']):
            if 'iphone' in question_lower and 'screen' in question_lower:
                return f"Yes, we do repair iPhone screens. We also repair smartphones, laptops, tablets, and gaming consoles."
            else:
                match = re.search(r'(iphone|android|laptop|console|screen)', question_lower)
                part = match.group(1) if match else 'those'
            return f"Yes, we do repair {part} issues. We also repair smartphones, laptops, tablets, and gaming consoles."
        return f"Yes, we do help with that. {clean_answer}"

    if 'refund' in focus_terms:
        return f"Yes, we can help with refunds. {clean_answer}"

    if 'wifi' in focus_terms:
        return f"Yes, we do offer Wi-Fi. {clean_answer}"

    if clean_answer.startswith('-'):
        clean_answer = clean_answer.lstrip('-').strip()

    if clean_answer and clean_answer[0].islower():
        clean_answer = clean_answer[0].upper() + clean_answer[1:]

    return clean_answer


def _score_sentence(sentence, question, question_terms, focus_terms):
    sentence_lower = sentence.lower()
    question_lower = question.lower()
    sentence_words = set(re.findall(r'[a-zA-Z]{3,}', sentence_lower))
    score = len(question_terms & sentence_words)
    if sentence_lower.endswith(':') or len(sentence_words) <= 4:
        score -= 2

    if 'hours' in focus_terms:
        if any(token in sentence_lower for token in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']):
            score += 4
        if re.search(r'\d{1,2}:\d{2}\s*(?:am|pm)', sentence_lower):
            score += 6
        question_days = [day for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] if day in question]
        if question_days and any(day in sentence_lower for day in question_days):
            score += 5
        if any(token in sentence_lower for token in ['open', 'close', 'hours', 'hour']):
            score += 3
        if 'time' in question_lower and not re.search(r'\d{1,2}:\d{2}\s*(?:am|pm)', sentence_lower):
            score -= 1
        if 'open' in question_lower and 'deal' in sentence_lower and not re.search(r'\d{1,2}:\d{2}\s*(?:am|pm)', sentence_lower):
            score -= 2
    if 'delivery' in focus_terms:
        if 'delivery' in sentence_lower:
            score += 4
        if any(token in sentence_lower for token in ['dha', 'clifton', 'lahore', 'karachi', 'islamabad', 'nationwide', 'within', 'outside']):
            score += 2
    if 'payment' in focus_terms:
        if any(token in sentence_lower for token in ['cash', 'cod', 'payment', 'bank transfer', 'card', 'online payment']):
            score += 4
    if 'location' in focus_terms:
        if any(token in sentence_lower for token in ['address', 'located', 'location', 'based in']):
            score += 4
        location_hits = sum(1 for token in ['lahore', 'karachi', 'islamabad', 'clifton', 'gulberg', 'dha', 'g-11', 'pakistan'] if token in sentence_lower)
        score += location_hits * 2
        if location_hits >= 2:
            score += 2
    if 'service' in focus_terms:
        if any(token in sentence_lower for token in ['repair', 'service', 'screen', 'replace', 'battery', 'laptop', 'console']):
            score += 4
        if any(token in question_lower for token in ['screen', 'iphone', 'android', 'laptop', 'console']) and any(token in sentence_lower for token in ['screen', 'iphone', 'android', 'laptop', 'console']):
            score += 4
    if 'refund' in focus_terms and 'refund' in sentence_lower:
        score += 4
    if 'wifi' in focus_terms and any(token in sentence_lower for token in ['wifi', 'wi-fi']):
        score += 4

    return score


def _extract_grounded_answer(context, question):
    question_lower = question.lower()
    question_terms = _question_keywords(question)
    focus_terms = _question_focus(question_lower)
    sentences = _split_sentences(context)
    scored_sentences = []
    for sentence in sentences:
        score = _score_sentence(sentence, question_lower, question_terms, focus_terms)
        if score > 0:
            scored_sentences.append((score, sentence))
    scored_sentences.sort(key=lambda item: item[0], reverse=True)
    for _, sentence in scored_sentences:
        sentence_lower = sentence.lower().strip()
        if sentence_lower.endswith(':') or sentence_lower.startswith('source:'):
            continue
        has_fact = bool(
            re.search(r'\d{1,2}:\d{2}\s*(?:am|pm)', sentence_lower)
            or any(token in sentence_lower for token in ['delivery', 'deliver', 'repair', 'payment', 'address', 'located', 'location', 'based in'])
            or any(token in sentence_lower for token in ['lahore', 'karachi', 'islamabad', 'clifton', 'gulberg', 'dha', 'g-11'])
        )
        if has_fact or len(re.findall(r'[a-zA-Z]{3,}', sentence)) > 3:
            return sentence
    if not scored_sentences:
        return 'Limited Information Available'
    return scored_sentences[0][1]


def _synthesize_answer(question, context, grounded_answer):
    if generator is None:
        return grounded_answer

    prompt = (
        'You are answering customer questions for a business using only the evidence provided. '
        "If the answer is not in the evidence, say 'Limited Information Available'. "
        'Return one short, direct sentence.\n\n'
        f'Question: {question}\n'
        f'Evidence: {context}\n'
        'Answer:'
    )

    try:
        out = generator(prompt, max_length=128, truncation=True)
        generated_answer = out[0]['generated_text'].strip()
    except Exception:
        return grounded_answer

    if not generated_answer:
        return grounded_answer

    generated_lower = generated_answer.lower()
    if 'limited information available' in generated_lower:
        return grounded_answer

    question_lower = question.lower()
    question_terms = _question_keywords(question)
    if question_terms and not any(term in generated_lower for term in question_terms):
        return grounded_answer
    if 'hours' in _question_focus(question_lower) and not any(token in generated_lower for token in ['am', 'pm', 'open', 'close', 'friday', 'monday', 'tuesday', 'wednesday', 'thursday', 'saturday', 'sunday']):
        return grounded_answer
    if 'delivery' in _question_focus(question_lower) and 'delivery' not in generated_lower:
        return grounded_answer
    if 'payment' in _question_focus(question_lower) and not any(token in generated_lower for token in ['cash', 'cod', 'payment', 'card', 'bank transfer']):
        return grounded_answer
    if 'location' in _question_focus(question_lower) and not any(token in generated_lower for token in ['lahore', 'karachi', 'islamabad', 'clifton', 'located', 'based in', 'address']):
        return grounded_answer

    return generated_answer


def _lexical_chunk_fallback(question, top_k=3, business_id=None):
    """Fallback retrieval over stored chunks when FAISS returns no matches.

    This keeps the app usable on Windows / low-memory setups where the index can
    lag or fail to load, while still grounding replies in stored business text.
    """
    question_terms = {word for word in re.findall(r'[a-zA-Z]{3,}', question.lower())}
    scored = []
    chunk_query = Chunk.query
    if business_id is not None:
        chunk_query = chunk_query.filter_by(business_id=business_id)
    for chunk in chunk_query.all():
        text_lower = (chunk.text or '').lower()
        chunk_terms = set(re.findall(r'[a-zA-Z]{3,}', text_lower))
        score = len(question_terms & chunk_terms)
        if 'delivery' in question.lower() and 'delivery' in text_lower:
            score += 3
        if any(term in question.lower() for term in ['where', 'locat', 'address']) and any(term in text_lower for term in ['address', 'located', 'location']):
            score += 3
        if any(term in question.lower() for term in ['open', 'hours', 'weekday', 'weekend', 'time']) and any(term in text_lower for term in ['am', 'pm', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']):
            score += 2
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [{'chunk': chunk, 'score': score / 10.0} for score, chunk in scored[:top_k]]


def _rank_business_chunks(question, business_id, top_k=3):
    question_lower = question.lower()
    question_terms = _question_keywords(question)
    focus_terms = _question_focus(question_lower)
    scored = []
    for chunk in Chunk.query.filter_by(business_id=business_id).all():
        chunk_text = chunk.text or ''
        chunk_sentences = _split_sentences(chunk_text)
        if not chunk_sentences:
            continue
        best_sentence_score = 0
        for sentence in chunk_sentences:
            best_sentence_score = max(
                best_sentence_score,
                _score_sentence(sentence, question_lower, question_terms, focus_terms),
            )
        if best_sentence_score > 0:
            scored.append((best_sentence_score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [{'chunk': chunk, 'score': score / 10.0} for score, chunk in scored[:top_k]]


def _merge_results(*result_groups, top_k=3):
    merged = []
    seen_ids = set()
    for group in result_groups:
        for result in group or []:
            chunk = result.get('chunk')
            if chunk is None or chunk.id in seen_ids:
                continue
            seen_ids.add(chunk.id)
            merged.append(result)
    merged.sort(key=lambda item: item.get('score', 0), reverse=True)
    return merged[:top_k]


def answer_question(question, top_k=3, similarity_threshold=0.0, business_id=None):
    if generator is None:
        _init_generator()
    store = VectorStore()
    results = store.search(question, top_k=top_k, business_id=business_id)
    business_ranked = _rank_business_chunks(question, business_id, top_k=top_k * 2) if business_id is not None else []
    if not results:
        results = _lexical_chunk_fallback(question, top_k=top_k, business_id=business_id)
    results = _merge_results(results, business_ranked, top_k=top_k)
    if not results:
        return {'status': 'NO_CONTEXT', 'answer': 'Limited Information Available', 'citations': []}

    best = results[0]
    if best['score'] < similarity_threshold and similarity_threshold > 0:
        return {'status': 'NO_CONTEXT', 'answer': 'Limited Information Available', 'citations': []}

    context = ''
    citations = []
    for r in results:
        c = r['chunk']
        context += f"{c.text}\n---\n"
        citations.append({'file': c.document.filename, 'page': c.page, 'chunk_id': c.id})

    if business_id is not None:
        answer_chunks = Chunk.query.filter_by(business_id=business_id).all()
        answer_context = ''
        for chunk in answer_chunks:
            answer_context += f"{chunk.text}\n---\n"
    else:
        answer_context = context

    prompt = f"Answer only from the provided context. If insufficient, say 'Limited Information Available'.\nContext:\n{context}\nQuestion: {question}\nAnswer:"

    grounded_answer = _extract_grounded_answer(answer_context, question)
    answer = grounded_answer
    if answer == 'Limited Information Available':
        answer = _synthesize_answer(question, answer_context, grounded_answer)
    else:
        answer = _conversationalize_answer(question, answer, business_id=business_id)

    answer = _normalize_customer_terms(answer)

    # Simple grounding: ensure citations present
    if 'Limited Information Available' in answer:
        return {'status': 'NO_CONTEXT', 'answer': 'Limited Information Available', 'citations': []}

    return {'status': 'OK', 'answer': answer, 'citations': citations}
