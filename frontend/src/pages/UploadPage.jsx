import { useState } from "react";
import { useNavigate } from "react-router-dom";

import {
    createSession,
    uploadResume,
} from "../services/api";

export default function UploadPage() {
    const navigate = useNavigate();

    const [role, setRole] = useState("ai_ml");
    const [file, setFile] = useState(null);
    const [loading, setLoading] = useState(false);
    const [toast, setToast] = useState(null);

    const showToast = (message) => {
        setToast(message);

        setTimeout(() => {
            setToast(null);
        }, 3500);
    };

    const handleStart = async () => {
        if (!file) {
            showToast("Please upload a resume.");
            return;
        }

        try {
            setLoading(true);

            const session = await createSession(role);

            await uploadResume(session.id, file);

            localStorage.setItem("sessionId", session.id);

            navigate("/interview");
        } catch (err) {
            console.error(err);
            showToast("Failed to start assessment.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            {toast && (
                <div className="toast">
                    {toast}
                </div>
            )}

            <div className="page">
                <div className="container">
                    <h1>Candidate Assessment</h1>

                    <p className="subtitle">
                        Upload your resume and select a role to begin the
                        technical assessment.
                    </p>

                    <div className="form-section">
                        <label>Resume</label>

                        <label className="upload-box">
                            <input
                                type="file"
                                accept=".pdf,.txt"
                                hidden
                                onChange={(e) => setFile(e.target.files[0])}
                            />

                            <div>
                                <div className="upload-title">
                                    {file
                                        ? file.name
                                        : "Select Resume"}
                                </div>

                                <div className="upload-subtitle">
                                    .pdf or .txt format (Max 5MB)
                                </div>
                            </div>
                        </label>
                    </div>

                    <div className="form-section">
                        <label>Role</label>

                        <select
                            value={role}
                            onChange={(e) =>
                                setRole(e.target.value)
                            }
                        >
                            <option value="ai_ml">
                                AI / ML Engineer
                            </option>

                            <option value="backend">
                                Backend Engineer
                            </option>
                        </select>
                    </div>

                    <button
                        className="primary-btn"
                        onClick={handleStart}
                        disabled={loading}
                    >
                        {loading && (
                            <span className="spinner"></span>
                        )}

                        {loading
                            ? "Analyzing Resume..."
                            : "Begin Assessment"}
                    </button>
                </div>
            </div>
        </>
    );
}