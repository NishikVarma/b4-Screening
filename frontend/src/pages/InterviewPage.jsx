import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
    getNextQuestion,
    submitAnswer,
} from "../services/api";

export default function InterviewPage() {
    const navigate = useNavigate();

    const sessionId = localStorage.getItem("sessionId");

    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    const [question, setQuestion] = useState(null);
    const [questionNumber, setQuestionNumber] = useState(1);
    const [totalQuestions, setTotalQuestions] = useState(0);

    const [answer, setAnswer] = useState("");

    const loadQuestion = async () => {
        try {
            const data = await getNextQuestion(sessionId);

            if (data.is_complete) {
                navigate("/results");
                return;
            }

            setQuestion(data.question);
            setQuestionNumber(data.question_number);
            setTotalQuestions(data.total_questions);
        } catch (err) {
            console.error(err);
            alert("Failed to load question.");
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
            alert("Please enter a response.");
            return;
        }

        try {
            setSubmitting(true);

            const result = await submitAnswer(
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
            setQuestionNumber((prev) => prev + 1);
        } catch (err) {
            console.error(err);
            alert("Failed to submit answer.");
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div className="page">
                <div className="container">
                    <h1>Loading Assessment...</h1>
                </div>
            </div>
        );
    }

    return (
        <div className="page">
            <div className="container">
                <h1>Candidate Assessment</h1>

                <div className="meta">
                    Question {questionNumber} of {totalQuestions}
                </div>

                <div className="question-card">
                    {question?.text}
                </div>

                <div className="section">
                    <label>Your Response</label>

                    <textarea
                        value={answer}
                        onChange={(e) => setAnswer(e.target.value)}
                        placeholder="Enter your answer..."
                    />
                </div>

                <button
                    className="primary-btn"
                    onClick={handleSubmit}
                    disabled={submitting}
                >
                    {submitting
                        ? "Submitting..."
                        : "Submit Response"}
                </button>
            </div>
        </div>
    );
}