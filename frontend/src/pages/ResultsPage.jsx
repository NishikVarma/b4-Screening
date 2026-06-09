import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getSummary } from "../services/api";

export default function ResultsPage() {
    const navigate = useNavigate();

    const [summary, setSummary] = useState(null);

    const sessionId = localStorage.getItem("sessionId");

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
            <div className="container">
                <h1>Assessment Complete</h1>

                <div className="summary-grid">
                    <div className="summary-card">
                        <h3>Total Questions</h3>
                        <p>{summary.total_questions}</p>
                    </div>

                    <div className="summary-card">
                        <h3>Answered</h3>
                        <p>{summary.answered}</p>
                    </div>

                    <div className="summary-card">
                        <h3>Average Score</h3>
                        <p>
                            {summary.average_score
                                ? summary.average_score
                                : "Not Available"}
                        </p>
                    </div>

                    <div className="summary-card">
                        <h3>Status</h3>
                        <p>{summary.session.status}</p>
                    </div>
                </div>

                <div style={{ marginTop: "32px" }}>
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
            </div>
        </div>
    );
}