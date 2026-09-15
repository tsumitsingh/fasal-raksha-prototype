const API_URL = window.FASAL_API_URL || "http://localhost:8000";
const scanId = new URLSearchParams(window.location.search).get("scan_id");
const messages = document.getElementById("messages");
const diagnosis = document.getElementById("diagnosis");
const preview = document.getElementById("crop-preview");
const form = document.getElementById("chat-form");
const question = document.getElementById("question");
const accessToken = localStorage.getItem("fasal_access_token");
const language = localStorage.getItem("language") || "en";
const chatText = language === "hi" ? {
    title: "फसल सहायक", subtitle: "आपकी फसल के लिए प्रमाणित सहायता", photo: "आपकी फसल की फोटो",
    loading: "फसल की फोटो की जांच हो रही है...", placeholder: "इलाज, दवा या बचाव के बारे में पूछें...",
    assistant: "फसल रक्षा", sources: "इस्तेमाल किए गए स्रोत", missing: "कोई स्कैन नहीं चुना गया। डैशबोर्ड पर वापस जाएं।",
    loadError: "स्कैन लोड नहीं हो सका।"
} : {
    title: "Crop Assistant", subtitle: "Evidence-based help for your crop", photo: "Your crop photo",
    loading: "Reading the crop image...", placeholder: "Ask about treatment, dosage, or prevention...",
    assistant: "Fasal Raksha", sources: "Sources used", missing: "No crop scan was selected. Go back to the dashboard.",
    loadError: "Scan could not be loaded."
};

if (!accessToken) window.location.href = "login.html";

function addMessage(role, content) {
    const message = document.createElement("div");
    message.className = "message " + role;
    message.innerHTML = "<strong>" + (role === "user" ? (language === "hi" ? "आप" : "You") : chatText.assistant) + "</strong>" + content;
    messages.appendChild(message);
    messages.scrollTop = messages.scrollHeight;
}

async function loadScan() {
    if (!scanId) {
        diagnosis.textContent = chatText.missing;
        return;
    }

    try {
        const response = await fetch(API_URL + "/api/scans/" + encodeURIComponent(scanId), {
            headers: { Authorization: "Bearer " + accessToken }
        });
        if (!response.ok) throw new Error(chatText.loadError);
        const scan = await response.json();
        preview.src = scan.image_url;
        diagnosis.innerHTML = "<strong>" + (language === "hi" ? "संभावित पहचान:" : "Possible finding:") + "</strong> " + scan.disease;
        addMessage("assistant", scan.answer);
        if (scan.sources && scan.sources.length) {
            const sourceList = scan.sources.map(function (source) {
                return "<a href=\"" + source.url + "\" target=\"_blank\" rel=\"noopener\">" + source.title + "</a>";
            }).join("<br>");
            addMessage("assistant", "<strong>" + chatText.sources + "</strong>" + sourceList);
        }
    } catch (error) {
        diagnosis.textContent = error.message + " Start the FastAPI server and reload this page.";
    }
}

form.addEventListener("submit", async function (event) {
    event.preventDefault();
    const text = question.value.trim();
    if (!text || !scanId) return;

    addMessage("user", text);
    question.value = "";
    form.querySelector("button").disabled = true;

    try {
        const response = await fetch(API_URL + "/api/scans/" + encodeURIComponent(scanId) + "/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: "Bearer " + accessToken },
            body: JSON.stringify({ question: text, language: language })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "The assistant could not answer.");
        addMessage("assistant", result.answer);
    } catch (error) {
        addMessage("assistant", error.message);
    } finally {
        form.querySelector("button").disabled = false;
        question.focus();
    }
});

loadScan();

document.getElementById("chat-title").textContent = chatText.title;
document.getElementById("chat-subtitle").textContent = chatText.subtitle;
document.getElementById("photo-label").textContent = chatText.photo;
document.getElementById("loading-text").textContent = chatText.loading;
question.placeholder = chatText.placeholder;
