import streamlit as st
import requests
import json
import re
from urllib.parse import quote_plus

st.set_page_config(page_title="Movie Workflow — Robust OMDb Lookup", layout="centered")


# -------------------------
# Helpers: OpenRouter LLaMA
# -------------------------
def llama(prompt, max_tokens=300):
    if "OPENROUTER_API_KEY" not in st.secrets:
        st.error("Missing OPENROUTER_API_KEY in st.secrets.")
        st.stop()
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}", "Content-Type": "application/json"}
    payload = {"model": "meta-llama/llama-3-8b-instruct", "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.7}
    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    if not resp.ok:
        st.error(f"OpenRouter Error {resp.status_code}: {resp.text}")
        st.stop()
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        st.error("Unexpected response from OpenRouter.")
        st.write(data)
        st.stop()


# -------------------------
# OMDb helpers (robust)
# -------------------------
def omdb_get_by_title(title):
    """Exact-title lookup using t= parameter. Returns dict (OMDb response)."""
    if "OMDB_API_KEY" not in st.secrets:
        st.error("Missing OMDB_API_KEY in st.secrets.")
        st.stop()
    key = st.secrets["OMDB_API_KEY"]
    url = f"http://www.omdbapi.com/?apikey={key}&t={quote_plus(title)}&plot=full"
    resp = requests.get(url, timeout=10)
    try:
        return resp.json()
    except Exception:
        return {"Response": "False", "Error": "Invalid OMDb response"}


def omdb_search(title):
    """Search using s= parameter; returns list of search results (may be empty)."""
    key = st.secrets["OMDB_API_KEY"]
    url = f"http://www.omdbapi.com/?apikey={key}&s={quote_plus(title)}"
    resp = requests.get(url, timeout=10)
    try:
        data = resp.json()
        if data.get("Response") == "True":
            return data.get("Search", [])
        return []
    except Exception:
        return []


def fetch_movie_data_with_fallback(title, show_debug=False):
    """
    Try exact-title lookup; if not found, try search and pick best match.
    Returns (info_dict, used_title, source) where source is 'exact' or 'search'.
    """
    # Try exact
    exact = omdb_get_by_title(title)
    if exact.get("Response") == "True":
        return exact, exact.get("Title", title), "exact"

    # Try search
    results = omdb_search(title)
    if results:
        # Pick the first result and fetch full data by IMDb ID if present
        first = results[0]
        imdb_id = first.get("imdbID")
        if imdb_id:
            key = st.secrets["OMDB_API_KEY"]
            url = f"http://www.omdbapi.com/?apikey={key}&i={imdb_id}&plot=full"
            resp = requests.get(url, timeout=10)
            try:
                data = resp.json()
                if data.get("Response") == "True":
                    return data, data.get("Title", first.get("Title")), "search"
            except Exception:
                pass
        # If IMDb fetch failed, return the first search item as partial
        return first, first.get("Title", title), "search_partial"

    # Nothing found
    return {"Response": "False", "Error": "Not found"}, title, "none"


# -------------------------
# Title normalization (AI-assisted but robust)
# -------------------------
def normalize_title(movie_input):
    """
    Use AI to suggest title, but guarantee a sensible fallback using Python title-casing.
    Returns final_title and ai_suggestion (may equal final_title).
    """
    # Ask AI for short canonical title (one line)
    try:
        ai_resp = llama(f"Return ONLY the official movie title for this input (one line): {movie_input}", max_tokens=30).strip()
    except Exception:
        ai_resp = ""

    # Clean AI output
    ai_clean = ai_resp.strip(' "\'\n\r\t')
    # If AI gave something non-empty and not obviously garbage, use it; otherwise fallback to title()
    if ai_clean and len(ai_clean) >= 2:
        final = ai_clean.title() if ai_clean.isupper() else ai_clean
    else:
        final = movie_input.title().strip()

    # Always ensure no extra phrase like "The properly capitalized..." by taking only a line
    final = final.splitlines()[0].strip()
    return final, ai_clean


# -------------------------
# UI
# -------------------------
st.title("🎬 Movie Workflow — Robust OMDb Lookup (4 AI Agents)")
st.write("This app will try exact OMDb lookup first, then fallback to search if needed. Put OPENROUTER_API_KEY and OMDB_API_KEY in st.secrets.")

movie_input = st.text_input("What is your favorite movie?")

if st.button("Run 4-Agent Workflow") and movie_input.strip():
    # Agent A - Normalize title (AI-assisted but safe)
    st.header("🧩 Agent A — Title Normalization (AI-assisted)")
    normalized_title, ai_suggestion = normalize_title(movie_input)
    st.write(f"AI suggestion: **{ai_suggestion or '(none)'}**")
    st.success(f"Using title for lookup: **{normalized_title}**")

    # Agent B - Fetch metadata with fallback, then produce AI-generated paragraph
    st.header("🎞️ Agent B — Fetch Metadata & AI Summary")
    info, used_title, source = fetch_movie_data_with_fallback(normalized_title)
    if info.get("Response") == "False":
        # Give clearer instructions to user if key is invalid/ inactive
        err = info.get("Error", "")
        if "Invalid API key" in err or "Invalid API Key" in err or "Invalid key" in err:
            st.error("OMDb returned an invalid API key error. Make sure you activated the key emailed to you and placed ONLY the key value into st.secrets as OMDB_API_KEY.")
            st.stop()
        st.error("Movie not found via OMDb. AI can suggest alternatives or you can try a different title.")
        # Ask AI to propose close matches
        alt = llama(f"OMDb couldn't find '{normalized_title}'. Suggest up to 3 likely alternate official titles or variants, one per line.")
        st.write("AI suggestions:")
        st.write(alt)
        st.stop()

    # Build a clean metadata dict with selected fields for AI context
    metadata_context = {
        "Title": info.get("Title"),
        "Year": info.get("Year"),
        "Genre": info.get("Genre"),
        "Director": info.get("Director"),
        "Actors": info.get("Actors"),
        "Runtime": info.get("Runtime"),
        "IMDB_Rating": info.get("imdbRating"),
    }

    # Show poster if available (no raw JSON dump)
    poster = info.get("Poster")
    if poster and poster != "N/A":
        st.image(poster, width=300)

    # Ask AI to write a short paragraph summarizing the movie metadata (Agent B's AI output)
    prompt_b = (
        f"Write a single short paragraph (2-4 sentences) summarizing this movie's key metadata "
        f"(title, year, genre, director, main actors, runtime, rating). Use natural language, do NOT print raw JSON.\n\n"
        f"Metadata: {json.dumps(metadata_context)}"
    )
    metadata_paragraph = llama(prompt_b, max_tokens=200)
    st.write(metadata_paragraph)
    st.caption(f"(OMDb lookup source: {source})")

    # Agent C - AI synopsis (enrich using OMDb plot)
    st.header("📖 Agent C — AI Synopsis (Generated)")
    omdb_plot = info.get("Plot", "")
    prompt_c = (
        f"Using this plot (below), write a concise, engaging, spoiler-aware synopsis (3-5 sentences) for '{metadata_context['Title']}' ({metadata_context['Year']}).\n\nPlot:\n{omdb_plot}"
    )
    synopsis = llama(prompt_c, max_tokens=250)
    st.write(synopsis)

    # Agent D - Quiz: generate JSON, parse, show interactive quiz + grading + explanations
    st.header("📝 Agent D — Interactive Quiz (AI-generated)")
    quiz_prompt = (
        "Create exactly 5 multiple-choice questions about the movie using the synopsis and metadata provided. "
        "Return ONLY valid JSON exactly in this format with no extra text:\n"
        '{ "questions": [ { "question": \"...\", "choices": [\"A...\",\"B...\",\"C...\",\"D...\"], "answer": "A", "explanation": "..." } ] }\n\n'
        f"Synopsis:\n{synopsis}\n\nMetadata: {json.dumps(metadata_context)}"
    )
    raw_quiz = llama(quiz_prompt, max_tokens=500)

    # Extract JSON safely
    m = re.search(r"\{.*\}", raw_quiz, re.DOTALL)
    if not m:
        st.error("AI returned invalid quiz JSON. Raw output shown for debugging.")
        st.code(raw_quiz)
        st.stop()
    quiz_json_str = m.group(0)
    try:
        quiz_data = json.loads(quiz_json_str)
        questions = quiz_data.get("questions", [])
        if not isinstance(questions, list) or len(questions) != 5:
            # allow flexibility but warn
            st.warning("AI generated a quiz but it didn't contain 5 well-formed questions. Displaying what we got.")
    except Exception as e:
        st.error("Failed to parse quiz JSON. Raw JSON displayed.")
        st.code(quiz_json_str)
        st.stop()

    # Interactive quiz UI
    st.success("Quiz ready — answer the questions below.")
    if "user_answers" not in st.session_state:
        st.session_state.user_answers = {}

    for i, q in enumerate(questions):
        q_text = q.get("question", f"Question {i+1}")
        choices = q.get("choices", [])
        # Ensure choices are strings; pad to 4 if needed
        if not isinstance(choices, list):
            choices = list(choices)
        while len(choices) < 4:
            choices.append("N/A")
        # Present options as "A) text" etc but store label A/B/C/D
        labels = ["A", "B", "C", "D"]
        display_options = [f"{labels[idx]}) {choices[idx]}" for idx in range(4)]
        st.markdown(f"**Q{i+1}. {q_text}**")
        choice_label = st.radio("", options=labels, format_func=lambda lab, opts=display_options, ls=labels: opts[ls.index(lab)], key=f"q{i}")
        st.session_state.user_answers[i] = choice_label

    if st.button("Submit Quiz"):
        total = len(questions)
        score = 0
        st.header("📊 Results")
        for i, q in enumerate(questions):
            correct = q.get("answer", "").strip().upper()
            user_ans = st.session_state.user_answers.get(i, "")
            explanation = q.get("explanation", "No explanation provided.")
            if user_ans == correct:
                st.success(f"Q{i+1}: Correct ({user_ans})")
                score += 1
            else:
                st.error(f"Q{i+1}: Incorrect — you chose {user_ans}, correct is {correct}")
            st.write(f"💡 Explanation: {explanation}")
            st.write("---")
        st.subheader(f"🏁 Final Score: **{score} / {total}**")

    st.success("Workflow complete — Agents A–D used AI and OMDb as appropriate.")
