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

    const handleStart = async () => {
        if (!file) {
            alert("Please upload a resume.");
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
            alert("Failed to start assessment.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="page">
            <div className="container">
                <h1>Candidate Assessment</h1>

                <div className="section">
                    <label>Resume</label>

                    <input
                        type="file"
                        accept=".pdf,.txt"
                        onChange={(e) => setFile(e.target.files[0])}
                    />
                </div>

                <div className="section">
                    <label>Role</label>

                    <select
                        value={role}
                        onChange={(e) => setRole(e.target.value)}
                    >
                        <option value="ai_ml">AI / ML Engineer</option>
                        <option value="backend">Backend Engineer</option>
                    </select>
                </div>

                <button
                    className="primary-btn"
                    onClick={handleStart}
                    disabled={loading}
                >
                    {loading ? "Preparing Assessment..." : "Begin Assessment"}
                </button>
            </div>
        </div>
    );
}