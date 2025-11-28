import streamlit as st
import requests

st.set_page_config(page_title="Movie Study Guide Workflow", layout="centered")

# ---------------------------------------------------------
# OPENROUTER API CALL
# ---------------------------------------------------------
def ask_openrouter(prompt, max_tokens=400):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "meta-llama/llama-3.1-70b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens
    }

    response = requests.post(url, json=payload, headers=headers)
    if not response.ok:
        st.error(f"OpenRouter Error {response.status_code}: {response.text}")
        st.stop()

    return response.json()["choices"][0]["message"]["content"]


# ---------------------------------------------------------
# OMDb API
# ---------------------------------------------------------
def fetch_movie_data(title):
    url = f"http://www.omdbapi.com/?t={title}&apikey={st.secrets['OMDB_API_KEY']}&plot=full"
    data = requests.get(url).json()
    if data.get("Response") == "False":
        return None
    return data


# ---------------------------------------------------------
# UI HEADER
# ---------------------------------------------------------
st.title("🎬 Movie Study Guide Workflow")
st.write("Enter a movie and generate a study guide, metadata, and a quiz.")

movie = st.text_input("🎥 What is your favorite movie?")


# ---------------------------------------------------------
# RUN WORKFLOW
# ---------------------------------------------------------
if movie.strip():

    # -----------------------------------------
    # Agent A — Normalize Title
    # -----------------------------------------
    st.header("🟥 Agent A — Normalize Title")

    normalized_title = ask_openrouter(
        f"Return the official, properly capitalized title for this movie: {movie}",
        max_tokens=40
    )

    st.write(f"**Normalized Title:** {normalized_title}")

    # -----------------------------------------
    # Agent B — AI Movie Metadata Paragraph
    # -----------------------------------------
    st.header("🟧 Agent B — Movie Metadata")

    movie_data = fetch_movie_data(normalized_title)

    if not movie_data:
        st.error("Movie not found in OMDb. Check your movie title or OMDb key.")
        st.stop()

    # Poster  
    poster = movie_data.get("Poster", "")
    if poster and poster != "N/A":
        st.image(poster, width=300)

    # Rewrite metadata nicely
    metadata_text = ask_openrouter(
        f"Rewrite the following movie metadata in one clean, descriptive paragraph:\n{movie_data}",
        max_tokens=300
    )

    st.write(metadata_text)

    # -----------------------------------------
    # Agent C — Study Guide Summary
    # -----------------------------------------
    st.header("🟨 Agent C — Study Guide Summary")

    summary = ask_openrouter(
        f"Write a study guide summary for the movie '{normalized_title}'. "
        f"Explain plot, themes, symbolism, tone, and film style.",
        max_tokens=350
    )

    st.write(summary)

    # -----------------------------------------
    # Agent D — Quiz
    # -----------------------------------------
    st.header("🟩 Agent D — Quiz")

    quiz_json = ask_openrouter(
        f"""
        Create a multiple-choice quiz based ONLY on this study guide:

        {summary}

        Requirements:
        - 5 questions
        - Each question must have choices A, B, C, D
        - Include the correct answer letter
        - Include a one-sentence explanation
        Return the result in JSON format:
        {{
            "questions": [
                {{
                    "question": "...",
                    "choices": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
                    "answer": "A",
                    "explanation": "..."
                }}
            ]
        }}
        """
    )

    # Try reading JSON
    import json
    try:
        quiz = json.loads(quiz_json)
    except:
        st.error("AI returned invalid quiz JSON. Showing raw output instead:")
        st.write(quiz_json)
        st.stop()

    # Store quiz for session
    if "quiz_data" not in st.session_state:
        st.session_state.quiz_data = quiz
        st.session_state.quiz_answers = {}

    st.subheader("📘 Answer the Quiz")

    for idx, q in enumerate(st.session_state.quiz_data["questions"]):
        question_key = f"question_{idx}"

        st.write(f"**Q{idx+1}. {q['question']}**")

        st.session_state.quiz_answers[question_key] = st.radio(
            "Choose an answer:",
            ["A", "B", "C", "D"],
            key=question_key,
            index=None
        )

    # ---------------------------------------------------------
    # SHOW RESULTS BUTTON
    # ---------------------------------------------------------
    if st.button("Submit Answers"):
        st.subheader("📊 Results")

        correct = 0
        for idx, q in enumerate(st.session_state.quiz_data["questions"]):
            key = f"question_{idx}"
            user_ans = st.session_state.quiz_answers.get(key)
            correct_ans = q["answer"]

            if user_ans == correct_ans:
                correct += 1
                st.success(f"Q{idx+1}: Correct! {q['explanation']}")
            else:
                st.error(f"Q{idx+1}: Incorrect. Correct answer: {correct_ans}. {q['explanation']}")

        st.info(f"**Final Score: {correct} / {len(st.session_state.quiz_data['questions'])}**")

