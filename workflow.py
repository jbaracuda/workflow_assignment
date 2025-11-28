import streamlit as st
import requests
import json

st.set_page_config(page_title="Movie Workflow (4 AI Agents)", layout="centered")


# ======================================================
# AI CALL — LLaMA via OpenRouter
# ======================================================
def llama(prompt, max_tokens=300):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "meta-llama/llama-3-8b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens
    }

    res = requests.post(url, json=payload, headers=headers)
    if not res.ok:
        st.error(f"OpenRouter Error {res.status_code}: {res.text}")
        st.stop()

    try:
        data = res.json()
        return data["choices"][0]["message"]["content"]
    except:
        st.error("Invalid AI Response")
        st.write(res.text)
        st.stop()


# ======================================================
# OMDb API (Agent B Uses It)
# ======================================================
def get_movie_data(title):
    url = f"http://www.omdbapi.com/?t={title}&apikey={st.secrets['OMDB_API_KEY']}&plot=full"
    return requests.get(url).json()


# ======================================================
# Streamlit UI
# ======================================================
st.title("🎬 4-Agent Movie Workflow System")
st.caption("Each agent uses AI according to assignment requirements.")

movie_title = st.text_input("What movie would you like to analyze?")


# ======================================================
# RUN WORKFLOW
# ======================================================
if st.button("Run 4-Agent Workflow") and movie_title.strip():

    # --------------------------------------------------
    # AGENT A — Normalize Movie Title
    # --------------------------------------------------
    st.header("🧩 Agent A — Title Normalization")

    normalized = llama(
        f"Normalize and return ONLY the official, properly capitalized movie title for: {movie_title}",
        max_tokens=20
    ).strip()

    st.success(f"Normalized Title: **{normalized}**")


    # --------------------------------------------------
    # AGENT B — AI-Generated Metadata Paragraph
    # --------------------------------------------------
    st.header("🎞️ Agent B — AI Metadata Summary")

    info = get_movie_data(normalized)

    if info.get("Response") == "False":
        st.error("Movie not found in OMDb.")
        st.stop()

    # Poster Image
    if info.get("Poster") and info["Poster"] != "N/A":
        st.image(info["Poster"], width=300)

    # AI-Generated Paragraph Summary
    metadata_str = json.dumps(info)
    agent_b_summary = llama(
        f"""
        Using the following movie metadata (JSON below), write a short, friendly,
        AI-generated paragraph summarizing the movie. Do NOT list the raw JSON.
        Make it sound natural.

        METADATA:
        {metadata_str}
        """,
        max_tokens=200,
    )

    st.write(agent_b_summary)


    # --------------------------------------------------
    # AGENT C — Synopsis
    # --------------------------------------------------
    st.header("📖 Agent C — AI Movie Synopsis")

    synopsis = llama(
        f"Write a detailed but spoiler-free synopsis of the movie '{normalized}'.",
        max_tokens=250,
    )

    st.write(synopsis)


    # --------------------------------------------------
    # AGENT D — Interactive Quiz
    # --------------------------------------------------
    st.header("📝 Agent D — Interactive Quiz Generator")

    quiz_raw = llama(
        f"""
        Create exactly **5 multiple-choice questions** about the movie '{normalized}'.
        Use this synopsis for context:

        {synopsis}

        Return ONLY valid JSON in the following format:

        {{
            "questions": [
                {{
                    "question": "...",
                    "choices": ["A", "B", "C", "D"],
                    "answer": "A",
                    "explanation": "Why the correct answer is right."
                }}
            ]
        }}
        }}
        """,
        max_tokens=500,
    )

    # Validate JSON output
    try:
        quiz = json.loads(quiz_raw)
    except:
        st.error("❌ AI returned invalid JSON. Here is the raw output:")
        st.code(quiz_raw)
        st.stop()

    st.success("Quiz Loaded! Answer the questions below:")

    # ------------------------------
    # Interactive Quiz Logic
    # ------------------------------
    st.subheader("🎯 Your Quiz")

    user_answers = {}
    correct_count = 0

    for i, q in enumerate(quiz["questions"]):
        st.markdown(f"### Q{i+1}: {q['question']}")

        user_choice = st.radio(
            f"Your answer for Q{i+1}",
            q["choices"],
            key=f"q{i}"
        )

        user_answers[i] = user_choice

    # Submit button
    if st.button("Submit Answers"):
        st.subheader("📊 Results")
        correct_count = 0

        for i, q in enumerate(quiz["questions"]):
            correct = q["answer"]
            user = user_answers[i]

            if user == correct:
                st.success(f"Q{i+1}: Correct! 🎉")
                correct_count += 1
            else:
                st.error(f"Q{i+1}: Incorrect. 😢")
                st.write(f"**Correct Answer:** {correct}")

            st.caption(f"💡 {q['explanation']}")
            st.write("---")

        st.subheader(f"🏁 Final Score: **{correct_count} / 5**")


# END
