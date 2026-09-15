const API_URL = window.FASAL_API_URL || "http://localhost:8000";
const accessToken = localStorage.getItem("fasal_access_token");
const language = localStorage.getItem("language") || "en";
const farmerName = localStorage.getItem("farmer_name") || "Farmer";
const scanButton = document.getElementById("scan-button");
const uploadButton = document.getElementById("upload-button");
const cropPhoto = document.getElementById("crop-photo");
const scanStatus = document.getElementById("scan-status");
const cameraModal = document.getElementById("camera-modal");
const cameraPreview = document.getElementById("camera-preview");
const cameraCanvas = document.getElementById("camera-canvas");
const cameraError = document.getElementById("camera-error");
const pendingPhoto = document.getElementById("pending-photo");
const pendingPhotoPreview = document.getElementById("pending-photo-preview");
const historyButton = document.getElementById("history-button");
const historyPanel = document.getElementById("history-panel");
const historyList = document.getElementById("history-list");
let cameraStream;
let selectedPhoto;

const translations = {
    en: {
        welcome: "Hello, kisan", subtitle: "Protect your crops with smarter technology.", scanTitle: "Scan Your Crop",
        scanDescription: "Take a photo of your crop to detect diseases and pests.", camera: "Open Camera",
        upload: "Upload Image Instead", ready: "Photo ready. Tap Start Scan to analyze it.", start: "Start Scan",
        analyzing: "Analyzing your crop photo...", readyStatus: "Your photo is ready for AI analysis.", history: "Scan History",
        emptyHistory: "No scans yet.", loadHistory: "Could not load scan history."
    },
    hi: {
        welcome: "नमस्ते किसान", subtitle: "स्मार्ट तकनीक से अपनी फसलों की सुरक्षा करें।", scanTitle: "अपनी फसल स्कैन करें",
        scanDescription: "बीमारी और कीट पहचानने के लिए अपनी फसल की फोटो लें।", camera: "कैमरा खोलें",
        upload: "फोटो अपलोड करें", ready: "फोटो तैयार है। जांच के लिए स्कैन शुरू करें।", start: "स्कैन शुरू करें",
        analyzing: "आपकी फसल की जांच हो रही है...", readyStatus: "आपकी फोटो AI जांच के लिए तैयार है।", history: "स्कैन इतिहास",
        emptyHistory: "अभी कोई स्कैन नहीं है।", loadHistory: "स्कैन इतिहास लोड नहीं हो सका।"
    }
};
const text = translations[language];

if (!accessToken) {
    window.location.href = "login.html";
}

document.getElementById("farmer-name").textContent = farmerName;
document.getElementById("welcome-title").textContent = text.welcome;
document.getElementById("welcome-subtitle").textContent = text.subtitle;
document.getElementById("scan-title").textContent = text.scanTitle;
document.getElementById("scan-description").textContent = text.scanDescription;
document.getElementById("scan-button").textContent = text.camera;
document.getElementById("upload-button").textContent = text.upload;
document.getElementById("history-title").textContent = text.history;
document.getElementById("history-heading").textContent = text.history;

scanButton.addEventListener("click", function () {
    if (selectedPhoto) {
        sendPhoto(selectedPhoto);
    } else {
        openCamera();
    }
});
uploadButton.addEventListener("click", function () {
    cropPhoto.click();
});
document.getElementById("close-camera").addEventListener("click", closeCamera);
document.getElementById("capture-button").addEventListener("click", capturePhoto);
historyButton.addEventListener("click", loadHistory);
document.getElementById("close-history").addEventListener("click", function () { historyPanel.hidden = true; });

async function openCamera() {
    cameraModal.hidden = false;
    cameraError.textContent = "";
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
        cameraPreview.srcObject = cameraStream;
    } catch (error) {
        cameraError.textContent = "Camera access was blocked. Use Upload Image Instead or allow camera permission.";
    }
}

function closeCamera() {
    if (cameraStream) cameraStream.getTracks().forEach(function (track) { track.stop(); });
    cameraStream = null;
    cameraPreview.srcObject = null;
    cameraModal.hidden = true;
}

function capturePhoto() {
    if (!cameraStream) return;
    cameraCanvas.width = cameraPreview.videoWidth;
    cameraCanvas.height = cameraPreview.videoHeight;
    cameraCanvas.getContext("2d").drawImage(cameraPreview, 0, 0);
    cameraCanvas.toBlob(function (blob) {
        closeCamera();
        setSelectedPhoto(new File([blob], "crop-camera.jpg", { type: "image/jpeg" }));
    }, "image/jpeg", 0.9);
}

function setSelectedPhoto(photo) {
    selectedPhoto = photo;
    pendingPhotoPreview.src = URL.createObjectURL(photo);
    pendingPhoto.hidden = false;
    scanButton.textContent = text.start;
    scanStatus.textContent = text.readyStatus;
}

cropPhoto.addEventListener("change", function () {
    if (cropPhoto.files[0]) setSelectedPhoto(cropPhoto.files[0]);
});

function sendPhoto(photo) {
    if (!photo.type.startsWith("image/")) {
        scanStatus.textContent = "Please choose an image file.";
        return;
    }
    const scanData = new FormData();
    scanData.append("image", photo);
    scanData.append("language", language);
    scanStatus.textContent = text.analyzing;
    scanButton.disabled = true;
    uploadButton.disabled = true;
    fetch(API_URL + "/api/scans", {
        method: "POST",
        headers: { Authorization: "Bearer " + accessToken },
        body: scanData
    })
        .then(function (response) {
            return response.json().then(function (result) {
                if (!response.ok) throw new Error(result.detail || "Scan service is unavailable.");
                return result;
            });
        })
        .then(function (scan) {
            window.location.href = "chat.html?scan_id=" + encodeURIComponent(scan.scan_id);
        })
        .catch(function (error) {
            scanStatus.textContent = error.message;
        })
        .finally(function () {
            scanButton.disabled = false;
            uploadButton.disabled = false;
            scanButton.textContent = text.start;
        });
}

async function loadHistory() {
    historyPanel.hidden = false;
    historyList.textContent = "";
    try {
        const response = await fetch(API_URL + "/api/scans", { headers: { Authorization: "Bearer " + accessToken } });
        if (!response.ok) throw new Error(text.loadHistory);
        const scans = await response.json();
        if (!scans.length) {
            historyList.textContent = text.emptyHistory;
            return;
        }
        scans.forEach(function (scan) {
            const item = document.createElement("div");
            item.className = "history-item";
            item.innerHTML = "<img src=\"" + scan.image_url + "\" alt=\"Crop scan\"><div><strong>" + scan.disease + "</strong><time>" + new Date(scan.created_at).toLocaleString() + "</time></div>";
            item.addEventListener("click", function () { window.location.href = "chat.html?scan_id=" + encodeURIComponent(scan.scan_id); });
            historyList.appendChild(item);
        });
    } catch (error) {
        historyList.textContent = error.message;
    }
}

const icons = document.querySelectorAll(".draggable");

icons.forEach(function(icon) {

    let isDragging = false;
    let offsetX = 0;
    let offsetY = 0;

    icon.addEventListener("pointerdown", function(event) {

        isDragging = true;

        const rect = icon.getBoundingClientRect();

        offsetX = event.clientX - rect.left;
        offsetY = event.clientY - rect.top;

        icon.setPointerCapture(event.pointerId);

    });

    icon.addEventListener("pointermove", function(event) {

        if (!isDragging) return;

        icon.style.left =
            (event.clientX - offsetX) + "px";

        icon.style.top =
            (event.clientY - offsetY) + "px";

    });

    icon.addEventListener("pointerup", function() {

        isDragging = false;

    });

});