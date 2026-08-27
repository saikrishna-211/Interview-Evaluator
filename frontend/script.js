const API_BASE_URL = "http://127.0.0.1:8000";
const MAX_QUESTIONS = 5;
const MAX_ANSWER_LENGTH = 2000;

const $ = (id) => document.getElementById(id);

// =========================================================
// DOM
// =========================================================

const startButton = $("startInterviewButton");
const navStartButton = $("navStartButton");

const roleInput = $("role");
const topicInput = $("topic");
const difficultyOptions =
    document.querySelectorAll(".difficulty-option");

const abandonButton = $("abandonButton");
const skipButton = $("skipButton");
const submitAnswerButton = $("submitAnswerButton");
const nextQuestionButton = $("nextQuestionButton");

const answerInput = $("answerInput");
const characterCount = $("characterCount");

const questionText = $("questionText");
const questionDifficulty = $("questionDifficulty");
const questionCounter = $("questionCounter");
const progressSteps = $("progressSteps");

const evaluationScore = $("evaluationScore");
const evaluationFeedback = $("evaluationFeedback");
const evaluationStrengths = $("evaluationStrengths");
const evaluationWeaknesses = $("evaluationWeaknesses");

const averageScore = $("averageScore");
const overallFeedback = $("overallFeedback");
const reportStrengths = $("reportStrengths");
const reportWeaknesses = $("reportWeaknesses");
const reportRecommendations = $("reportRecommendations");
const reportQuestions = $("reportQuestions");

const newInterviewButton = $("newInterviewButton");

const loadingOverlay = $("loadingOverlay");
const loadingTitle = $("loadingTitle");
const loadingText = $("loadingText");

const abandonModal = $("abandonModal");
const cancelAbandonButton = $("cancelAbandonButton");
const confirmAbandonButton = $("confirmAbandonButton");

// =========================================================
// STATE
// =========================================================

let selectedDifficulty = "medium";
let currentSessionId = null;
let currentQuestion = null;
let currentQuestionNumber = 1;

let isBusy = false;

// =========================================================
// INIT
// =========================================================

document.addEventListener("DOMContentLoaded", init);

async function init() {
    setupDifficulty();
    setupEvents();
    updateCharacterCount();
    updateProgress(1);

    await restoreState();
}

// =========================================================
// EVENTS
// =========================================================

function setupEvents() {
    startButton?.addEventListener(
        "click",
        startInterview
    );

    navStartButton?.addEventListener(
        "click",
        () => {
            showScreen("setupScreen");

            document
                .querySelector(".setup-card")
                ?.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });

            setTimeout(() => {
                roleInput?.focus();
            }, 400);
        }
    );

    answerInput?.addEventListener(
        "input",
        updateCharacterCount
    );

    submitAnswerButton?.addEventListener(
        "click",
        submitAnswer
    );

    skipButton?.addEventListener(
        "click",
        skipQuestion
    );

    nextQuestionButton?.addEventListener(
        "click",
        handleNext
    );

    abandonButton?.addEventListener(
        "click",
        () => {
            abandonModal?.classList.add("active");
        }
    );

    cancelAbandonButton?.addEventListener(
        "click",
        () => {
            abandonModal?.classList.remove("active");
        }
    );

    confirmAbandonButton?.addEventListener(
        "click",
        abandonInterview
    );

    newInterviewButton?.addEventListener(
        "click",
        startNewInterview
    );

    roleInput?.addEventListener(
        "keydown",
        (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                startInterview();
            }
        }
    );

    topicInput?.addEventListener(
        "keydown",
        (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                startInterview();
            }
        }
    );

    document.addEventListener(
        "keydown",
        (e) => {
            if (
                e.key === "Escape" &&
                abandonModal?.classList.contains("active")
            ) {
                abandonModal.classList.remove("active");
            }
        }
    );
}

// =========================================================
// DIFFICULTY
// =========================================================

function setupDifficulty() {
    difficultyOptions.forEach((option) => {
        option.addEventListener(
            "click",
            () => {
                difficultyOptions.forEach(
                    (btn) =>
                        btn.classList.remove(
                            "active"
                        )
                );

                option.classList.add("active");

                selectedDifficulty =
                    option.dataset.difficulty ||
                    "medium";
            }
        );
    });
}

// =========================================================
// SCREEN
// =========================================================

function showScreen(
    id,
    save = true
) {
    document
        .querySelectorAll(".screen")
        .forEach((screen) => {
            screen.classList.remove("active");
        });

    const screen = $(id);

    if (!screen) {
        console.error(
            `Screen not found: ${id}`
        );

        return false;
    }

    screen.classList.add("active");

    if (save) {
        localStorage.setItem(
            "app_screen",
            id
        );
    }

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });

    return true;
}

// =========================================================
// LOADING
// =========================================================

function showLoading(
    title,
    text
) {
    if (!loadingOverlay) {
        return;
    }

    if (loadingTitle) {
        loadingTitle.textContent = title;
    }

    if (loadingText) {
        loadingText.textContent = text;
    }

    loadingOverlay.classList.add("active");
}

function hideLoading() {
    loadingOverlay?.classList.remove(
        "active"
    );
}

// =========================================================
// API
// =========================================================

async function api(
    url,
    options = {},
    timeout = 120000
) {
    const controller =
        new AbortController();

    const timer = setTimeout(
        () => {
            controller.abort();
        },
        timeout
    );

    try {
        const response = await fetch(
            url,
            {
                ...options,
                signal:
                    controller.signal
            }
        );

        const contentType =
            response.headers.get(
                "content-type"
            ) || "";

        let data;

        if (
            contentType.includes(
                "application/json"
            )
        ) {
            data =
                await response
                    .json()
                    .catch(() => ({}));
        } else {
            const text =
                await response.text();

            data = {
                detail: text
            };
        }

        return {
            response,
            data
        };

    } catch (error) {
        if (
            error.name ===
            "AbortError"
        ) {
            throw new Error(
                "The server took too long to respond. Please try again."
            );
        }

        throw new Error(
            "Cannot connect to the backend. Make sure FastAPI is running on http://127.0.0.1:8000."
        );

    } finally {
        clearTimeout(timer);
    }
}

function getError(
    data,
    fallback
) {
    if (!data) {
        return fallback;
    }

    if (
        Array.isArray(data.detail)
    ) {
        return data.detail
            .map((item) =>
                typeof item === "string"
                    ? item
                    : item.msg ||
                      JSON.stringify(item)
            )
            .join(", ");
    }

    return (
        data.detail ||
        data.message ||
        fallback
    );
}

// =========================================================
// STORAGE
// =========================================================

function saveQuestion(
    question
) {
    currentQuestion =
        question;

    currentQuestionNumber =
        Number(
            question.question_number ||
            1
        );

    localStorage.setItem(
        "current_question",
        JSON.stringify(question)
    );
}

function getSavedQuestion() {
    try {
        const value =
            localStorage.getItem(
                "current_question"
            );

        return value
            ? JSON.parse(value)
            : null;

    } catch {
        localStorage.removeItem(
            "current_question"
        );

        return null;
    }
}

function saveEvaluation(
    evaluation
) {
    localStorage.setItem(
        "current_evaluation",
        JSON.stringify(evaluation)
    );
}

function getSavedEvaluation() {
    try {
        const value =
            localStorage.getItem(
                "current_evaluation"
            );

        return value
            ? JSON.parse(value)
            : null;

    } catch {
        localStorage.removeItem(
            "current_evaluation"
        );

        return null;
    }
}

function saveReport(
    report
) {
    localStorage.setItem(
        "interview_report",
        JSON.stringify(report)
    );
}

function getSavedReport() {
    try {
        const value =
            localStorage.getItem(
                "interview_report"
            );

        return value
            ? JSON.parse(value)
            : null;

    } catch {
        localStorage.removeItem(
            "interview_report"
        );

        return null;
    }
}

function clearInterviewStorage() {
    [
        "interview_session_id",
        "current_question",
        "current_evaluation",
        "interview_role",
        "interview_topic",
        "interview_difficulty",
        "app_screen"
    ].forEach((key) => {
        localStorage.removeItem(key);
    });

    currentSessionId = null;
    currentQuestion = null;
    currentQuestionNumber = 1;
}

// =========================================================
// RESTORE AFTER REFRESH
// =========================================================

async function restoreState() {
    const savedScreen =
        localStorage.getItem(
            "app_screen"
        );

    const savedReport =
        getSavedReport();

    // -----------------------------------------------------
    // Report survives refresh
    // -----------------------------------------------------

    if (
        savedScreen ===
            "reportScreen" &&
        savedReport
    ) {
        displayReport(savedReport);
        showScreen("reportScreen");

        return;
    }

    const sessionId =
        localStorage.getItem(
            "interview_session_id"
        );

    if (!sessionId) {
        showScreen("setupScreen");
        return;
    }

    currentSessionId =
        sessionId;

    try {
        const {
            response,
            data
        } = await api(
            `${API_BASE_URL}/interviews/${encodeURIComponent(sessionId)}`,
            {
                headers: {
                    Accept:
                        "application/json"
                }
            },
            60000
        );

        // -------------------------------------------------
        // Invalid session
        // -------------------------------------------------

        if (
            response.status === 404
        ) {
            clearInterviewStorage();
            showScreen("setupScreen");

            return;
        }

        // -------------------------------------------------
        // Temporary backend problem
        // -------------------------------------------------

        if (!response.ok) {
            console.error(
                "Could not restore session:",
                data
            );

            return;
        }

        // -------------------------------------------------
        // Completed
        // -------------------------------------------------

        if (
            data.status ===
            "completed"
        ) {
            const report =
                getSavedReport();

            if (report) {
                displayReport(report);
                showScreen(
                    "reportScreen"
                );
            }

            return;
        }

        // -------------------------------------------------
        // Abandoned
        // -------------------------------------------------

        if (
            data.status ===
            "abandoned"
        ) {
            clearInterviewStorage();
            showScreen("setupScreen");

            return;
        }

        // -------------------------------------------------
        // Active interview
        // -------------------------------------------------

        if (
            data.status ===
            "active"
        ) {
            const question =
                data.current_question ||
                getSavedQuestion();

            if (question) {
                saveQuestion(question);

                // Restore evaluation screen
                if (
                    savedScreen ===
                    "evaluationScreen"
                ) {
                    const evaluation =
                        getSavedEvaluation();

                    if (evaluation) {
                        displayEvaluation(
                            evaluation
                        );

                        showScreen(
                            "evaluationScreen"
                        );

                        return;
                    }
                }

                // Restore question
                showInterview();
            }
        }

    } catch (error) {
        console.error(
            "Restore error:",
            error
        );
    }
}

// =========================================================
// START INTERVIEW
// =========================================================

async function startInterview() {
    if (isBusy) {
        return;
    }

    const role =
        roleInput?.value.trim();

    const topic =
        topicInput?.value.trim();

    // -----------------------------------------------------
    // Basic frontend validation
    // -----------------------------------------------------

    if (!role) {
        alert(
            "Please enter the job role."
        );

        roleInput?.focus();

        return;
    }

    if (!topic) {
        alert(
            "Please enter the interview topic."
        );

        topicInput?.focus();

        return;
    }

    isBusy = true;

    const oldHTML =
        startButton?.innerHTML;

    if (startButton) {
        startButton.disabled = true;

        startButton.innerHTML =
            "<span>Starting...</span>";
    }

    showLoading(
        "Preparing your interview",
        "Checking your role and topic..."
    );

    try {
        // -------------------------------------------------
        // Remove previous interview state
        // -------------------------------------------------

        clearInterviewStorage();

        // =================================================
        // VALIDATE ROLE + TOPIC
        // =================================================

        showLoading(
            "Checking your interview topic",
            "Making sure the role and topic are suitable..."
        );

        const validation =
            await api(
                `${API_BASE_URL}/interviews/validate-input`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json",

                        Accept:
                            "application/json"
                    },

                    body: JSON.stringify({
                        role,
                        topic,
                        difficulty:
                            selectedDifficulty
                    })
                }
            );

        if (
            !validation.response.ok
        ) {
            throw new Error(
                getError(
                    validation.data,
                    "Please enter a valid professional role and interview topic."
                )
            );
        }

        if (
            validation.data?.valid !==
            true
        ) {
            throw new Error(
                validation.data?.message ||
                "Please enter a valid professional role and interview topic."
            );
        }

        // =================================================
        // CREATE INTERVIEW
        // =================================================

        showLoading(
            "Preparing your interview",
            "Creating your personalized interview..."
        );

        const create =
            await api(
                `${API_BASE_URL}/interviews`,
                {
                    method:
                        "POST",

                    headers: {
                        "Content-Type":
                            "application/json",

                        Accept:
                            "application/json"
                    },

                    body: JSON.stringify({
                        role,
                        topic,
                        difficulty:
                            selectedDifficulty
                    })
                }
            );

        if (
            !create.response.ok
        ) {
            throw new Error(
                getError(
                    create.data,
                    "Failed to create interview."
                )
            );
        }

        if (
            !create.data?.session_id
        ) {
            throw new Error(
                "The server did not return a session ID."
            );
        }

        currentSessionId =
            String(
                create.data.session_id
            );

        localStorage.setItem(
            "interview_session_id",
            currentSessionId
        );

        localStorage.setItem(
            "interview_role",
            role
        );

        localStorage.setItem(
            "interview_topic",
            topic
        );

        localStorage.setItem(
            "interview_difficulty",
            selectedDifficulty
        );

        // =================================================
        // START INTERVIEW
        // =================================================

        showLoading(
            "Generating your first question",
            "Please wait..."
        );

        const start =
            await api(
                `${API_BASE_URL}/interviews/${encodeURIComponent(currentSessionId)}/start`,
                {
                    method:
                        "POST",

                    headers: {
                        Accept:
                            "application/json"
                    }
                }
            );

        if (
            !start.response.ok
        ) {
            throw new Error(
                getError(
                    start.data,
                    "Failed to start the interview."
                )
            );
        }

        if (
            !start.data?.id ||
            start.data?.question ===
                undefined
        ) {
            console.error(
                "Invalid question response:",
                start.data
            );

            throw new Error(
                "The server did not return a valid question."
            );
        }

        saveQuestion(
            start.data
        );

        localStorage.setItem(
            "app_screen",
            "interviewScreen"
        );

        showInterview();

    } catch (error) {
        console.error(
            "Start interview error:",
            error
        );

        clearInterviewStorage();

        alert(
            error.message ||
            "Something went wrong while starting the interview."
        );

    } finally {
        isBusy = false;

        hideLoading();

        if (startButton) {
            startButton.disabled =
                false;

            startButton.innerHTML =
                oldHTML;
        }
    }
}

// =========================================================
// INTERVIEW SCREEN
// =========================================================

function showInterview() {
    if (!currentQuestion) {
        currentQuestion =
            getSavedQuestion();
    }

    if (!currentQuestion) {
        alert(
            "No interview question is available."
        );

        return;
    }

    displayQuestion(
        currentQuestion
    );

    showScreen(
        "interviewScreen"
    );
}

function displayQuestion(
    question
) {
    currentQuestion =
        question;

    currentQuestionNumber =
        Number(
            question.question_number ||
            1
        );

    questionText.textContent =
        question.question ||
        "Your interview question will appear here.";

    const difficulty =
        String(
            question.difficulty ||
            selectedDifficulty ||
            "medium"
        ).toLowerCase();

    questionDifficulty.textContent =
        capitalize(difficulty);

    questionDifficulty.className =
        `difficulty-badge ${difficulty}`;

    questionCounter.textContent =
        `Question ${currentQuestionNumber} of ${MAX_QUESTIONS}`;

    updateProgress(
        currentQuestionNumber
    );

    if (answerInput) {
        answerInput.value = "";
        answerInput.disabled =
            false;
    }

    updateCharacterCount();

    if (submitAnswerButton) {
        submitAnswerButton.disabled =
            false;
    }

    if (skipButton) {
        skipButton.disabled =
            false;
    }
}

// =========================================================
// PROGRESS
// =========================================================

function updateProgress(
    active
) {
    if (!progressSteps) {
        return;
    }

    progressSteps.innerHTML = "";

    for (
        let i = 1;
        i <= MAX_QUESTIONS;
        i++
    ) {
        const step =
            document.createElement(
                "div"
            );

        step.className =
            "progress-step";

        if (i < active) {
            step.classList.add(
                "completed"
            );
        }

        if (i === active) {
            step.classList.add(
                "active"
            );
        }

        progressSteps.appendChild(
            step
        );
    }
}

// =========================================================
// CHARACTER COUNT
// =========================================================

function updateCharacterCount() {
    if (
        !answerInput ||
        !characterCount
    ) {
        return;
    }

    characterCount.textContent =
        `${answerInput.value.length} / ${MAX_ANSWER_LENGTH}`;
}

// =========================================================
// SUBMIT ANSWER
// =========================================================

async function submitAnswer() {
    if (isBusy) {
        return;
    }

    if (
        !currentSessionId ||
        !currentQuestion
    ) {
        alert(
            "Your interview session could not be found."
        );

        return;
    }

    isBusy = true;

    if (submitAnswerButton) {
        submitAnswerButton.disabled =
            true;
    }

    if (skipButton) {
        skipButton.disabled =
            true;
    }

    const answer =
        answerInput?.value.trim() ||
        "";

    try {
        // -------------------------------------------------
        // Save answer
        // -------------------------------------------------

        showLoading(
            "Submitting your answer",
            "Saving your response..."
        );

        const answerResult =
            await api(
                `${API_BASE_URL}/questions/${encodeURIComponent(currentQuestion.id)}/answers`,
                {
                    method:
                        "POST",

                    headers: {
                        "Content-Type":
                            "application/json",

                        Accept:
                            "application/json"
                    },

                    body: JSON.stringify({
                        answer
                    })
                }
            );

        if (
            !answerResult.response.ok
        ) {
            throw new Error(
                getError(
                    answerResult.data,
                    "Failed to submit your answer."
                )
            );
        }

        if (
            !answerResult.data?.id
        ) {
            throw new Error(
                "The server did not return an answer ID."
            );
        }

        // -------------------------------------------------
        // Evaluate answer
        // -------------------------------------------------

        showLoading(
            "Evaluating your answer",
            "Our AI interviewer is analyzing your response..."
        );

        const evaluation =
            await api(
                `${API_BASE_URL}/answers/${encodeURIComponent(answerResult.data.id)}/evaluate`,
                {
                    method:
                        "POST",

                    headers: {
                        Accept:
                            "application/json"
                    }
                }
            );

        if (
            !evaluation.response.ok
        ) {
            throw new Error(
                getError(
                    evaluation.data,
                    "Failed to evaluate your answer."
                )
            );
        }

        saveEvaluation(
            evaluation.data
        );

        displayEvaluation(
            evaluation.data
        );

        showScreen(
            "evaluationScreen"
        );

    } catch (error) {
        console.error(
            "Answer/evaluation error:",
            error
        );

        alert(
            error.message ||
            "Something went wrong while evaluating your answer."
        );

        if (submitAnswerButton) {
            submitAnswerButton.disabled =
                false;
        }

        if (skipButton) {
            skipButton.disabled =
                false;
        }

    } finally {
        isBusy = false;
        hideLoading();
    }
}

// =========================================================
// SKIP QUESTION
// =========================================================

async function skipQuestion() {
    if (isBusy) {
        return;
    }

    if (
        !currentSessionId ||
        !currentQuestion
    ) {
        alert(
            "Your interview session could not be found."
        );

        return;
    }

    isBusy = true;

    if (submitAnswerButton) {
        submitAnswerButton.disabled =
            true;
    }

    if (skipButton) {
        skipButton.disabled =
            true;
    }

    showLoading(
        "Skipping question",
        "Saving this question as skipped..."
    );

    try {
        const result =
            await api(
                `${API_BASE_URL}/questions/${encodeURIComponent(currentQuestion.id)}/skip`,
                {
                    method:
                        "POST",

                    headers: {
                        Accept:
                            "application/json"
                    }
                }
            );

        if (
            !result.response.ok
        ) {
            throw new Error(
                getError(
                    result.data,
                    "Failed to skip the question."
                )
            );
        }

        // Backend already records:
        // empty answer + score 0.

        const evaluation = {
            score: 0,

            feedback:
                "This question was skipped.",

            strengths:
                "No answer was provided.",

            weaknesses:
                "Try to attempt every question when possible."
        };

        saveEvaluation(
            evaluation
        );

        displayEvaluation(
            evaluation
        );

        showScreen(
            "evaluationScreen"
        );

    } catch (error) {
        console.error(
            "Skip error:",
            error
        );

        alert(
            error.message ||
            "Could not skip this question."
        );

        if (submitAnswerButton) {
            submitAnswerButton.disabled =
                false;
        }

        if (skipButton) {
            skipButton.disabled =
                false;
        }

    } finally {
        isBusy = false;
        hideLoading();
    }
}

// =========================================================
// EVALUATION
// =========================================================

function displayEvaluation(
    data
) {
    const score =
        Number(
            data?.score ?? 0
        );

    if (evaluationScore) {
        evaluationScore.textContent =
            Number.isFinite(score)
                ? Math.max(
                      0,
                      Math.min(
                          10,
                          score
                      )
                  ).toFixed(1)
                : "0.0";
    }

    if (evaluationFeedback) {
        evaluationFeedback.textContent =
            displayValue(
                data?.feedback,
                "No feedback was provided."
            );
    }

    if (evaluationStrengths) {
        evaluationStrengths.textContent =
            displayValue(
                data?.strengths,
                "No strengths were provided."
            );
    }

    if (evaluationWeaknesses) {
        evaluationWeaknesses.textContent =
            displayValue(
                data?.weaknesses,
                "No improvement areas were provided."
            );
    }

    if (nextQuestionButton) {
        nextQuestionButton.disabled =
            false;

        nextQuestionButton.innerHTML =
            currentQuestionNumber >=
            MAX_QUESTIONS
                ? "Complete interview <span>→</span>"
                : "Next question <span>→</span>";
    }
}

// =========================================================
// NEXT QUESTION
// =========================================================

async function handleNext() {
    if (isBusy) {
        return;
    }

    if (!currentSessionId) {
        alert(
            "Your interview session could not be found."
        );

        return;
    }

    // -----------------------------------------------------
    // Question 5 = complete
    // -----------------------------------------------------

    if (
        currentQuestionNumber >=
        MAX_QUESTIONS
    ) {
        await completeInterview();
        return;
    }

    isBusy = true;

    if (nextQuestionButton) {
        nextQuestionButton.disabled =
            true;
    }

    showLoading(
        "Preparing your next question",
        "The difficulty is adapting to your performance..."
    );

    try {
        const result =
            await api(
                `${API_BASE_URL}/interviews/${encodeURIComponent(currentSessionId)}/generate-question`,
                {
                    method:
                        "POST",

                    headers: {
                        Accept:
                            "application/json"
                    }
                }
            );

        if (
            !result.response.ok
        ) {
            throw new Error(
                getError(
                    result.data,
                    "Failed to generate the next question."
                )
            );
        }

        if (
            !result.data?.id ||
            result.data?.question ===
                undefined
        ) {
            throw new Error(
                "The server did not return a valid next question."
            );
        }

        localStorage.removeItem(
            "current_evaluation"
        );

        saveQuestion(
            result.data
        );

        showInterview();

    } catch (error) {
        console.error(
            "Next question error:",
            error
        );

        alert(
            error.message ||
            "Could not generate the next question."
        );

        if (nextQuestionButton) {
            nextQuestionButton.disabled =
                false;
        }

    } finally {
        isBusy = false;
        hideLoading();
    }
}

// =========================================================
// COMPLETE INTERVIEW
// =========================================================

async function completeInterview() {
    if (isBusy) {
        return;
    }

    if (!currentSessionId) {
        alert(
            "Your interview session could not be found."
        );

        return;
    }

    isBusy = true;

    if (nextQuestionButton) {
        nextQuestionButton.disabled =
            true;
    }

    showLoading(
        "Completing your interview",
        "Generating your final performance report..."
    );

    try {
        // -------------------------------------------------
        // COMPLETE
        // -------------------------------------------------

        const complete =
            await api(
                `${API_BASE_URL}/interviews/${encodeURIComponent(currentSessionId)}/complete`,
                {
                    method:
                        "POST",

                    headers: {
                        Accept:
                            "application/json"
                    }
                }
            );

        console.log(
            "COMPLETE RESPONSE:",
            complete.data
        );

        /*
         * "Already completed" is okay.
         */

        if (
            !complete.response.ok
        ) {
            const message =
                getError(
                    complete.data,
                    "Failed to complete the interview."
                );

            if (
                !message
                    .toLowerCase()
                    .includes(
                        "already completed"
                    )
            ) {
                throw new Error(
                    message
                );
            }
        }

        // -------------------------------------------------
        // REPORT
        // -------------------------------------------------

        showLoading(
            "Preparing your report",
            "Loading your final performance..."
        );

        const report =
            await api(
                `${API_BASE_URL}/interviews/${encodeURIComponent(currentSessionId)}/report`,
                {
                    method:
                        "GET",

                    headers: {
                        Accept:
                            "application/json"
                    }
                }
            );

        console.log(
            "REPORT RESPONSE:",
            report.data
        );

        if (
            !report.response.ok
        ) {
            throw new Error(
                getError(
                    report.data,
                    "The interview is complete, but the report could not be loaded."
                )
            );
        }

        // -------------------------------------------------
        // Save before showing report
        // -------------------------------------------------

        saveReport(
            report.data
        );

        displayReport(
            report.data
        );

        // -------------------------------------------------
        // Remove active interview state
        // -------------------------------------------------

        localStorage.removeItem(
            "interview_session_id"
        );

        localStorage.removeItem(
            "current_question"
        );

        localStorage.removeItem(
            "current_evaluation"
        );

        localStorage.setItem(
            "app_screen",
            "reportScreen"
        );

        currentSessionId = null;
        currentQuestion = null;

        showScreen(
            "reportScreen"
        );

    } catch (error) {
        console.error(
            "Completion/report error:",
            error
        );

        alert(
            error.message ||
            "Could not complete the interview."
        );

        if (nextQuestionButton) {
            nextQuestionButton.disabled =
                false;
        }

    } finally {
        isBusy = false;
        hideLoading();
    }
}

// =========================================================
// REPORT
// =========================================================

function displayReport(
    report
) {
    if (!report) {
        console.error(
            "Empty report."
        );

        return;
    }

    const score =
        Number(
            report.average_score ??
            report.averageScore ??
            report.score ??
            0
        );

    if (averageScore) {
        averageScore.textContent =
            Number.isFinite(score)
                ? score.toFixed(1)
                : "0.0";
    }

    if (overallFeedback) {
        overallFeedback.textContent =
            displayValue(
                report.overall_feedback ??
                report.overallFeedback ??
                report.feedback,

                "No overall feedback was provided."
            );
    }

    if (reportStrengths) {
        reportStrengths.textContent =
            displayValue(
                report.key_strengths ??
                report.keyStrengths ??
                report.strengths,

                "No strengths were provided."
            );
    }

    if (reportWeaknesses) {
        reportWeaknesses.textContent =
            displayValue(
                report.areas_to_improve ??
                report.areasToImprove ??
                report.weaknesses,

                "No improvement areas were provided."
            );
    }

    if (reportRecommendations) {
        reportRecommendations.textContent =
            displayValue(
                report.recommendations,

                "No recommendations were provided."
            );
    }

    renderReportQuestions(
        report
    );
}

// =========================================================
// REPORT QUESTIONS
// =========================================================

function renderReportQuestions(
    report
) {
    if (!reportQuestions) {
        return;
    }

    reportQuestions.innerHTML = "";

    const questions =
        report.questions ||
        report.question_breakdown ||
        report.questionBreakdown ||
        [];

    if (
        !Array.isArray(
            questions
        ) ||
        questions.length === 0
    ) {
        const empty =
            document.createElement(
                "p"
            );

        empty.textContent =
            "No question breakdown is available.";

        empty.style.color =
            "var(--muted)";

        reportQuestions.appendChild(
            empty
        );

        return;
    }

    questions.forEach(
        (item, index) => {
            const card =
                document.createElement(
                    "div"
                );

            card.className =
                "report-summary-card";

            const label =
                document.createElement(
                    "span"
                );

            label.textContent =
                `QUESTION ${index + 1}`;

            const question =
                document.createElement(
                    "p"
                );

            question.textContent =
                displayValue(
                    item.question ??
                    item.question_text,

                    "Question"
                );

            const score =
                document.createElement(
                    "p"
                );

            score.style.marginTop =
                "8px";

            score.textContent =
                `Score: ${formatScore(
                    item.score ??
                    item.evaluation?.score
                )}`;

            card.append(
                label,
                question,
                score
            );

            reportQuestions.appendChild(
                card
            );
        }
    );
}

// =========================================================
// ABANDON
// =========================================================

function abandonInterview() {
    clearInterviewStorage();

    localStorage.removeItem(
        "interview_report"
    );

    abandonModal?.classList.remove(
        "active"
    );

    showScreen(
        "setupScreen"
    );
}

// =========================================================
// NEW INTERVIEW
// =========================================================

function startNewInterview() {
    clearInterviewStorage();

    localStorage.removeItem(
        "interview_report"
    );

    if (roleInput) {
        roleInput.value = "";
    }

    if (topicInput) {
        topicInput.value = "";
    }

    if (answerInput) {
        answerInput.value = "";
    }

    selectedDifficulty =
        "medium";

    difficultyOptions.forEach(
        (button) => {
            button.classList.toggle(
                "active",
                button.dataset.difficulty ===
                    "medium"
            );
        }
    );

    updateCharacterCount();
    updateProgress(1);

    showScreen(
        "setupScreen"
    );

    setTimeout(() => {
        roleInput?.focus();
    }, 300);
}

// =========================================================
// HELPERS
// =========================================================

function displayValue(
    value,
    fallback = ""
) {
    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return fallback;
    }

    if (
        Array.isArray(value)
    ) {
        return value
            .map((item) =>
                typeof item ===
                "object"
                    ? (
                        item.text ||
                        item.value ||
                        item.description ||
                        JSON.stringify(item)
                    )
                    : String(item)
            )
            .join(", ");
    }

    if (
        typeof value ===
        "object"
    ) {
        return (
            value.text ||
            value.value ||
            value.description ||
            JSON.stringify(value)
        );
    }

    return String(value);
}

function formatScore(
    value
) {
    const score =
        Number(value);

    if (
        !Number.isFinite(score)
    ) {
        return "0.0 / 10";
    }

    return (
        Math.max(
            0,
            Math.min(
                10,
                score
            )
        ).toFixed(1) +
        " / 10"
    );
}

function capitalize(
    value
) {
    return value
        ? value.charAt(0).toUpperCase() +
              value.slice(1)
        : "";
}