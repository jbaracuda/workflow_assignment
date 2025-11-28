import streamlit as st
import requests
import json
import re

st.set_page_config(page_title="Movie Workflow — 4 AI Agents", layout="centered")

# ---------------------------
# Utilities: OpenRouter LLaMA
# ---------------------------
def llama_generate(prompt, max_tokens=300, model="meta-llama/llama-3-8b-instruct"):
    """
    Call OpenRouter chat completions endpoint (LLaMA). Requires OPENROUTER_API_KEY in st.secrets.
    Returns the assistant content string or stops the app on error.
    """
    if "OPENROUTER_API_KEY" not in st.secrets:
        st.error("Missing OPENROUTER_API_KEY in st.secrets.")
        st.stop()

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }

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

# ---------------------------
# OMDb helper
# ---------------------------
def get_movie_data(title):
    if "OMDB_API_KEY" not in st.secrets:
        st.error("Missing OMDB_API_KEY in st.secrets.")
        st.stop()
    key = st.secrets["OMDB_API_KEY"]
    url = f"http://www.omdbapi.com/?apikey={key}&t={requests.utils.requote_uri(title)}&plot=full"
    resp = requests.get(url, timeout=20)
    try:
        return resp.json()
    except Exception:
        st.error("Failed to parse OMDb response.")
        st.write(resp.text)
        st.stop()

# ---------------------------
# UI - header
# ---------------------------
st.title("🎬 Movie Workflow — 4 AI Agents")
st.write(
    "This demo runs 4 AI agents in sequence. Each agent uses LLaMA (via OpenRouter) to perform a unique task. "
    "Only required setup: put `OPENROUTER_API_KEY` and `OMDB_API_KEY` into Streamlit Secrets."
)

movie_input = st.text_input("What is your favorite movie?")

# Reserve session state for quiz persistence
if "quiz_questions" not in st.session_state:
    st.session_state.quiz_questions = None
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}

# Run workflow
if st.button("Run Workflow") and movie_input.strip():
    st.session_state.quiz_questions = None
    st.session_state.user_answers = {}

    # ---------------------------
    # Agent A: AI Title Normalization (uses AI but we post-process for robustness)
    # ---------------------------
    st.header("🧩 Agent A — Title Normalizer (AI-assisted)")
    # Ask the model for official/canonical title; force short, one-line answer
    prompt_a = (
        f"Return ONLY the official, properly capitalized movie title for the following user input.\n"
        f"User input: \"{movie_input}\"\n"
        f"Return one line containing just the title, nothing else."
    )
    ai_title = llama_generate(prompt_a, max_tokens=40).strip()

    # Post-process to ensure OMDb matching: take model answer, remove quotes, then python-title-case fallback
    ai_title = ai_title.strip(' "\'').strip()
    # If model returned in all caps or clearly wrong casing, apply title() as fallback
    normalized_title = ai_title.title() if ai_title.isupper() or ai_title == "" else ai_title
    # final fallback: basic title-case of user input
    if not normalized_title:
        normalized_title = movie_input.title().strip()

    st.success(f"AI suggested title: **{ai_title}** — Normalized to **{normalized_title}**")

    # ---------------------------
    # Agent B: OMDb fetch + AI actor/director backgrounds (AI-enriched metadata)
    # ---------------------------
    st.header("🎞️ Agent B — Fetch Metadata & AI Backgrounds")
    info = get_movie_data(normalized_title)

    if info.get("Response") == "False":
        # If OMDb didn't find it, ask AI to suggest likely canonical titles and show suggestions
        st.warning("OMDb did not find the movie. Asking the model for alternate titles...")
        alt_prompt = (
            f"OMDb could not find the title '{normalized_title}'. Provide up to three likely alternate official titles "
            f"or common variants (one per line) that could match that movie name. If none, reply 'NONE'."
        )
        alt_resp = llama_generate(alt_prompt, max_tokens=100)
        st.write("AI alternatives / variants (try one of these):")
        st.write(alt_resp)
        st.stop()

    # Show core metadata
    st.subheader("Basic Metadata (OMDb)")
    meta = {
        "Title": info.get("Title"),
        "Year": info.get("Year"),
        "Genre": info.get("Genre"),
        "Director": info.get("Director"),
        "Actors": info.get("Actors"),
        "Runtime": info.get("Runtime"),
        "IMDB Rating": info.get("imdbRating"),
    }
    st.json(meta)

    # Poster
    poster_url = info.get("Poster")
    if poster_url and poster_url != "N/A":
        st.image(poster_url, width=280)

    # Use AI to produce short bios/backgrounds of main actors and director (AI-generated content)
    people_prompt = (
        f"Given the following movie metadata, write a short (1-2 sentence) background for each actor and the director. "
        f"Only include backgrounds for the names listed. Format as JSON: {{'people':[{{'name':'', 'role':'actor/director', 'background':''}}]}}.\n\n"
        f"Metadata:\nTitle: {info.get('Title')}\nActors: {info.get('Actors')}\nDirector: {info.get('Director')}\nYear: {info.get('Year')}"
    )
    people_resp = llama_generate(people_prompt, max_tokens=300)

    # Try to extract JSON if model returned JSON-like text
    try:
        people_json_str = re.search(r"\{.*\}", people_resp, re.DOTALL).group(0)
        people_data = json.loads(people_json_str)
        st.subheader("AI-generated backgrounds")
        st.write(people_data)
    except Exception:
        # If parsing fails, just display raw AI text
        st.subheader("AI-generated backgrounds (raw)")
        st.write(people_resp)

    # ---------------------------
    # Agent C: AI-generated Synopsis (from OMDb plot + AI enrichment)
    # ---------------------------
    st.header("📖 Agent C — AI Synopsis (Generated)")
    # Use OMDb plot as context and ask AI to write a concise, spoiler-aware synopsis
    omdb_plot = info.get("Plot", "")
    synopsis_prompt = (
        f"Write a clear, engaging, and concise synopsis (3-6 sentences) for the movie '{info.get('Title')}' ({info.get('Year')}). "
        f"Use the following plot as context and enrich with natural flow, but keep it spoiler-avoiding:\n\n{omdb_plot}\n\n"
        f"Return only the synopsis text."
    )
    synopsis = llama_generate(synopsis_prompt, max_tokens=250)
    st.write(synopsis)

    # ---------------------------
    # Agent D: AI Quiz Generator → parse JSON → interactive quiz UI → grading + explanations
    # ---------------------------
    st.header("📝 Agent D — Interactive Quiz (AI-generated questions & explanations)")
    quiz_prompt = (
        "Create 5 multiple-choice questions about the movie, based on the following synopsis and metadata. "
        "Return ONLY valid JSON in this exact format (no extra text):\n\n"
        '{ "questions": [ '
        '{"question":"...","choices":["A...","B...","C...","D..."],"answer":"A","explanation":"..."}'
        ' ] }\n\n'
        f"Synopsis:\n{synopsis}\n\nMetadata: Title: {info.get('Title')}; Year: {info.get('Year')}; Director: {info.get('Director')}; Actors: {info.get('Actors')}"
    )

    raw_quiz = llama_generate(quiz_prompt, max_tokens=500)

    # Extract JSON substring to be robust against extra text
    json_match = re.search(r"\{.*\}", raw_quiz, re.DOTALL)
    if not json_match:
        st.error("AI returned invalid quiz JSON. Raw output:")
        st.write(raw_quiz)
        st.stop()

    quiz_json_str = json_match.group(0)
    try:
        quiz_data = json.loads(quiz_json_str)
        questions = quiz_data.get("questions", [])
        if not isinstance(questions, list) or len(questions) == 0:
            raise ValueError("No questions found in JSON.")
    except Exception as e:
        st.error("Failed to parse quiz JSON. Raw JSON:")
        st.write(quiz_json_str)
        st.stop()

    # Save questions in session for grading
    st.session_state.quiz_questions = questions

    st.write("Answer the following questions:")

    # Display interactive questions
    for i, q in enumerate(questions):
        q_text = q.get("question", "")
        choices = q.get("choices", [])
        # Ensure choices are labeled A-D; if model returned text choices, we present labels
        labels = ["A", "B", "C", "D"]
        if len(choices) < 4:
            # pad with placeholders if malformed
            while len(choices) < 4:
                choices.append("N/A")
        options_display = [f"{labels[idx]}. {choices[idx]}" for idx in range(4)]

        st.write(f"**Q{i+1}. {q_text}**")
        # Use radio with options A-D but show text
        selection = st.radio("", options=labels, format_func=lambda x, opts=options_display, lbls=labels: opts[lbls.index(x)], key=f"q{i}")
        st.session_state.user_answers[i] = selection

    if st.button("Submit Quiz"):
        # Grade answers and show explanations
        correct = 0
        total = len(questions)
        st.markdown("## 📊 Results")
        for i, q in enumerate(questions):
            user_ans = st.session_state.user_answers.get(i, "")
            correct_ans = q.get("answer", "").strip().upper()
            explanation = q.get("explanation", "No explanation provided.")

            if user_ans == correct_ans:
                st.success(f"Q{i+1}: Correct — {user_ans}")
                correct += 1
            else:
                st.error(f"Q{i+1}: Incorrect. You chose {user_ans}. Correct answer: {correct_ans}")

            st.write(f"💡 Explanation: {explanation}")
            st.write("---")

        st.markdown(f"### 🏁 Final Score: **{correct} / {total}**")

    st.success("Workflow complete — all information above was generated or enriched by AI where applicable.")
