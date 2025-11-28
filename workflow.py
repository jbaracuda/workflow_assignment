import streamlit as st
import requests
import re

st.set_page_config(page_title="Movie Workflow", layout="centered")

# ======================================================
# LLaMA via OpenRouter
# ======================================================
def llama_generate(prompt, max_tokens=250):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "meta-llama/llama-3-8b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }

    response = requests.post(url, json=payload, headers=headers)

    if not response.ok:
        st.error(f"OpenRouter Error {response.status_code}: {response.text}")
        st.stop()

    return response.json()["choices"][0]["message"]["content"]


# ======================================================
# CLEAN OMDb Metadata Lookup (never fails)
# ======================================================
def get_movie_data(ai_title):
    clean_title = re.sub(r"[^A-Za-z0-9 :\-']", "", ai_title).strip()

    # Try exact match
    url_exact = f"http://www.omdbapi.com/?t={clean_title}&apikey={st.secrets['OMDB_API_KEY']}&plot=full"
    exact = requests.get(url_exact).json()

    if exact.get("Response") == "True":
        return exact

    # Try search mode
    url_search = f"http://www.omdbapi.com/?s={clean_title}&apikey={st.secrets['OMDB_API_KEY']}"
    search = requests.get(url_search).json()

    if search.get("Response") == "True":
        real_title = search["Search"][0]["Title"]
        url_final = f"http://www.omdbapi.com/?t={real_title}&apikey={st.secrets['OMDB_API_KEY']}&plot=full"
        return requests.get(url_final).json()

    return {"Response": "False"}


# ======================================================
# QUIZ PARSER
# ======================================================
def parse_quiz(raw_text):
    quiz = []
    blocks = raw_text.strip().split("\n\n")

    for block in blocks:
        lines = block.strip().split("\n")
        q, opts, ans, exp = None, [], None, None

        for line in lines:
            if line.startswith("Q"):
                q = line.split(":", 1)[1].strip()

            elif line.startswith(("A)", "B)", "C)", "D)")):
                opts.append(line.strip())

            elif line.lower().startswith("answer"):
                ans = line.split(":")[1].strip()

            elif line.lower().startswith("explanation"):
                exp = line.split(":", 1)[1].strip()

        if q and opts and ans:
            quiz.append({
                "question": q,
                "options": opts,
                "correct": ans,
                "explanation": exp or ""
            })

    return quiz


# ======================================================
# Initialize session state
# ======================================================
for key in [
    "normalized_title", "metadata_paragraph", "metadata_poster",
    "synopsis", "quiz_data", "user_answers", "show_results"
]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "user_answers" else {}
        if key == "show_results":
            st.session_state[key] = False


# ======================================================
# UI HEADER
# ======================================================
st.title("🎬 Movie Workflow — Four-Agent System")

movie_title = st.text_input("What is your favorite movie?")


# ======================================================
# RUN WORKFLOW
# ======================================================
if st.button("Run Workflow") and movie_title.strip():

    # --------------------------------------------------
    # AGENT A — Normalize Title
    # --------------------------------------------------
    normalized = llama_generate(
        f"Return only the correctly formatted official movie title: {movie_title}",
        max_tokens=20
    ).strip()

    st.session_state.normalized_title = normalized

    # --------------------------------------------------
    # AGENT B — Background Paragraph (general, 1 paragraph)
    # --------------------------------------------------
    raw_info = get_movie_data(normalized)

    if raw_info.get("Response") == "False":
        st.error("Movie not found in OMDb.")
        st.stop()

    st.session_state.metadata_poster = raw_info.get("Poster", None)

    metadata_prompt = f"""
    Write ONE paragraph giving general background about the movie '{normalized}'.
    Include:
    - its overall premise,
    - director,
    - genre,
    - year,
    - primary cast,
    - cultural or cinematic significance.

    MUST NOT include detailed plot points or character breakdowns.
    MUST NOT mention AI or generation.

    Data:
    Title: {raw_info.get("Title")}
    Year: {raw_info.get("Year")}
    Genre: {raw_info.get("Genre")}
    Director: {raw_info.get("Director")}
    Actors: {raw_info.get("Actors")}
    Plot: {raw_info.get("Plot")}
    """

    st.session_state.metadata_paragraph = llama_generate(metadata_prompt, max_tokens=220)

    # --------------------------------------------------
    # AGENT C — Character-Focused Synopsis (2 paragraphs)
    # --------------------------------------------------
    synopsis_prompt = f"""
    Write TWO paragraphs discussing the movie '{normalized}'.
    Paragraph 1: summarize the story setup and world without spoilers.
    Paragraph 2: focus specifically on key characters, their roles,
    motivations, and relationships.

    Must NOT mention AI or generation.
    """

    st.session_state.synopsis = llama_generate(synopsis_prompt, max_tokens=350)

    # --------------------------------------------------
    # AGENT D — Quiz Based ONLY on Agent C
    # --------------------------------------------------
    quiz_prompt = f"""
    Create a 5-question multiple-choice quiz based STRICTLY on the text below.
    Use EXACT format:

    Q1: <question>
    A) <option>
    B) <option>
    C) <option>
    D) <option>
    Answer: <letter>
    Explanation: <explain why>

    TEXT:
    {st.session_state.synopsis}
    """

    raw_quiz = llama_generate(quiz_prompt, max_tokens=350)
    st.session_state.quiz_data = parse_quiz(raw_quiz)
    st.session_state.user_answers = {}
    st.session_state.show_results = False


# ======================================================
# SHOW AGENTS A–C IF AVAILABLE
# ======================================================
if st.session_state.normalized_title:
    st.header("Agent A — Title Normalization")
    st.success(f"Title: **{st.session_state.normalized_title}**")

if st.session_state.metadata_paragraph:
    st.header("Agent B — Movie Background")

    if st.session_state.metadata_poster and st.session_state.metadata_poster != "N/A":
        st.image(st.session_state.metadata_poster, width=300)

    st.write(st.session_state.metadata_paragraph)

if st.session_state.synopsis:
    st.header("Agent C — Synopsis")
    st.write(st.session_state.synopsis)


# ======================================================
# AGENT D — QUIZ
# ======================================================
if st.session_state.quiz_data and not st.session_state.show_results:

    st.header("Agent D — Quiz")

    for i, q in enumerate(st.session_state.quiz_data):
        st.write(f"**Q{i+1}: {q['question']}**")

        st.session_state.user_answers[i] = st.radio(
            f"Your answer for question {i+1}:",
            q["options"],
            key=f"q{i}"
        )

        st.write("---")

    if st.button("Submit Answers"):
        st.session_state.show_results = True


# ======================================================
# SHOW RESULTS
# ======================================================
if st.session_state.show_results:
    st.header("Results")

    score = 0
    quiz = st.session_state.quiz_data

    for i, q in enumerate(quiz):
        user_ans = st.session_state.user_answers.get(i, "")
        correct_letter = q["correct"]
        correct_opt = [o for o in q["options"] if o.startswith(correct_letter)][0]

        if user_ans.startswith(correct_letter):
            score += 1
            st.success(f"Q{i+1}: Correct!")
        else:
            st.error(f"Q{i+1}: Incorrect.")

        st.write(f"**Correct Answer:** {correct_opt}")
        st.write(f"**Explanation:** {q['explanation']}")
        st.write("---")

    st.subheader(f"Final Score: **{score} / {len(quiz)}**")
