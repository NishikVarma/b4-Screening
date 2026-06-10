import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSummary } from "../services/api";

export default function ResultsPage() {
    const navigate = useNavigate();
    const sessionId = localStorage.getItem("sessionId");

    const [summary, setSummary] = useState(null);
    const [showDetails, setShowDetails] = useState(false); // New State

    useEffect(() => {
        if (!sessionId) {
            navigate("/");
            return;
        }

        const loadSummary = async () => {
            try {
                const data = await getSummary(sessionId);
                setSummary(data);
            } catch (err) {
                console.error(err);
            }
        };

        loadSummary();
    }, []);

    if (!summary) {
        return (
            <div className="page">
                <div className="container">
                    <h1>Loading Results...</h1>
                </div>
            </div>
        );
    }

    return (
        <div className="page">
            <div className="results-container">
                <h1>Assessment Complete</h1>

                {summary.feedback_summary && (
                    <div className="overall-summary-card">
                        <h2>Overall Assessment</h2>

                        <p
                            style={{
                                whiteSpace: "pre-wrap",
                            }}
                        >
                            {summary.feedback_summary}
                        </p>
                    </div>
                )}

                <div className="summary-grid">
                    <div className="summary-card">
                        <h3>Average Score</h3>
                        <p className="score-large">
                            {summary.average_score ?? "-"}/10
                        </p>
                    </div>

                    <div className="summary-card">
                        <h3>Questions</h3>
                        <p>{summary.total_questions}</p>
                    </div>

                    <div className="summary-card">
                        <h3>Answered</h3>
                        <p>{summary.answered}</p>
                    </div>

                    <div className="summary-card">
                        <h3>Status</h3>
                        <p>{summary.session.status}</p>
                    </div>
                </div>

                {/* New Action Buttons Section */}
                <div className="action-buttons">
                    <button
                        className="secondary-btn"
                        onClick={() => setShowDetails(!showDetails)}
                    >
                        {showDetails ? "Hide Detailed Analysis" : "Check Detailed Analysis"}
                    </button>

                    <button
                        className="primary-btn"
                        onClick={() => {
                            localStorage.removeItem("sessionId");
                            navigate("/");
                        }}
                    >
                        Start New Assessment
                    </button>
                </div>

                <div
                    className={`detailed-analysis-section ${
                        showDetails ? "open" : ""
                    }`}
                >
                    <div className="results-list">
                        {summary.question_details.map((item, index) => (
                            <div key={index} className="result-card">
                                <div className="result-header">
                                    <h3>Question {index + 1}</h3>

                                    <span className="result-score">
                        {item.score === null
                            ? "Skipped"
                            : `${item.score}/10`}
                    </span>
                                </div>

                                <p className="result-question">
                                    {item.question}
                                </p>

                                {item.answer === "[SKIPPED]" ? (
                                    <div className="result-section">
                                        <strong>Status</strong>
                                        <p>Skipped</p>
                                    </div>
                                ) : (
                                    <>
                                        <div className="result-section">
                                            <strong>Response</strong>
                                            <p>{item.answer}</p>
                                        </div>

                                        <div className="result-section">
                                            <strong>Feedback</strong>
                                            <p>{item.feedback}</p>
                                        </div>
                                    </>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}