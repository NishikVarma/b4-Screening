import axios from "axios";

const api = axios.create({
    baseURL:
        import.meta.env.VITE_API_URL ||
        "http://127.0.0.1:8000",
});

export const createSession = async (role) => {
    const { data } = await api.post("/sessions", { role });
    return data;
};

export const uploadResume = async (sessionId, file) => {
    const formData = new FormData();
    formData.append("file", file);

    const { data } = await api.post(
        `/sessions/${sessionId}/resume`,
        formData,
        {
            headers: {
                "Content-Type": "multipart/form-data",
            },
        }
    );

    return data;
};

export const getNextQuestion = async (sessionId) => {
    const { data } = await api.get(
        `/sessions/${sessionId}/next-question`
    );

    return data;
};

export const submitAnswer = async (
    sessionId,
    questionId,
    text
) => {
    const { data } = await api.post(
        `/sessions/${sessionId}/questions/${questionId}/answer`,
        { text }
    );

    return data;
};

export const skipQuestion = async (
    sessionId,
    questionId
) => {
    const { data } = await api.post(
        `/sessions/${sessionId}/questions/${questionId}/skip`
    );

    return data;
};

export const getSummary = async (sessionId) => {
    const { data } = await api.get(
        `/sessions/${sessionId}/summary`
    );

    return data;
};

export default api;