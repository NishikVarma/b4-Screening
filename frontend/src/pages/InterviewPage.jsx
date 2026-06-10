import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    getNextQuestion,
    submitAnswer,
    skipQuestion,
} from "../services/api";

export default function InterviewPage() {
    const navigate = useNavigate();

    const sessionId =
        localStorage.getItem("sessionId");

    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] =
        useState(false);
    const [showExitModal, setShowExitModal] =
        useState(false);

    const [toast, setToast] = useState(null);

    const [question, setQuestion] = useState(null);
    const [questionNumber, setQuestionNumber] =
        useState(1);
    const [totalQuestions, setTotalQuestions] =
        useState(0);

    const [answer, setAnswer] = useState("");

    const showToast = (message) => {
        setToast(message);

        setTimeout(() => {
            setToast(null);
        }, 3500);
    };

    const loadQuestion = async () => {
        try {
            const data =
                await getNextQuestion(sessionId);

            if (data.is_complete) {
                navigate("/results");
                return;
            }

            setQuestion(data.question);
            setQuestionNumber(
                data.question_number
            );
            setTotalQuestions(
                data.total_questions
            );
        } catch (err) {
            console.error(err);
            showToast("Failed to load question.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!sessionId) {
            navigate("/");
            return;
        }

        loadQuestion();
    }, []);

    const handleSubmit = async () => {
        if (!answer.trim()) {
            showToast(
                "Please enter a response."
            );
            return;
        }

        try {
            setSubmitting(true);

            const result =
                await submitAnswer(
                    sessionId,
                    question.id,
                    answer
                );

            setAnswer("");

            if (result.is_complete) {
                navigate("/results");
                return;
            }

            setQuestion(result.next_question);
            setQuestionNumber(
                (prev) => prev + 1
            );
        } catch (err) {
            console.error(err);
            showToast(
                "Failed to submit answer."
            );
        } finally {
            setSubmitting(false);
        }
    };

    const handleSkip = async () => {
        try {
            setSubmitting(true);

            const result =
                await skipQuestion(
                    sessionId,
                    question.id
                );

            setAnswer("");

            if (result.is_complete) {
                navigate("/results");
                return;
            }

            setQuestion(result.next_question);
            setQuestionNumber(
                (prev) => prev + 1
            );
        } catch (err) {
            console.error(err);
            showToast(
                "Failed to skip question."
            );
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div className="page">
                <div className="container">
                    <h1>
                        Loading Assessment...
                    </h1>
                </div>
            </div>
        );
    }

    return (
        <>
            {toast && (
                <div className="toast">
                    {toast}
                </div>
            )}

            {submitting && (
                <div className="evaluation-overlay">
                    <div className="evaluation-modal">
                        <div className="spinner large-spinner"></div>

                        <h3>
                            Evaluating Response
                        </h3>

                        <p>
                            Please wait while
                            the assessment is
                            processed.
                        </p>
                    </div>
                </div>
            )}

            <div className="page">
                <div className="container">
                    <div className="assessment-header">
                        <h1>
                            Candidate Assessment
                        </h1>

                        <button
                            className="exit-link"
                            onClick={() =>
                                setShowExitModal(
                                    true
                                )
                            }
                        >
                            Exit
                        </button>
                    </div>

                    <div className="meta">
                        Question {questionNumber} of{" "}
                        {totalQuestions}
                    </div>

                    <div className="question-card">
                        {question?.text}
                    </div>

                    <div className="section">
                        <label>
                            Your Response
                        </label>

                        <textarea
                            value={answer}
                            onChange={(e) =>
                                setAnswer(
                                    e.target.value
                                )
                            }
                            placeholder="Enter your answer..."
                            disabled={
                                submitting
                            }
                        />
                    </div>

                    <div className="button-group">
                        <button
                            className="secondary-btn"
                            onClick={
                                handleSkip
                            }
                            disabled={
                                submitting
                            }
                        >
                            Skip Question
                        </button>

                        <button
                            className="primary-btn"
                            onClick={
                                handleSubmit
                            }
                            disabled={
                                submitting
                            }
                        >
                            Submit Response
                        </button>
                    </div>
                </div>
            </div>

            {showExitModal && (
                <div className="modal-overlay">
                    <div className="modal">
                        <h3>
                            Exit Assessment
                        </h3>

                        <p>
                            Your submitted
                            responses will be
                            saved. You can end
                            the assessment now
                            and view your
                            results based on
                            the answers
                            submitted so far.
                        </p>

                        <div className="modal-actions">
                            <button
                                className="secondary-btn"
                                onClick={() =>
                                    setShowExitModal(
                                        false
                                    )
                                }
                            >
                                Continue
                                Assessment
                            </button>

                            <button
                                className="primary-btn"
                                onClick={() => {
                                    setShowExitModal(
                                        false
                                    );

                                    navigate(
                                        "/results"
                                    );
                                }}
                            >
                                Exit &
                                View Results
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}