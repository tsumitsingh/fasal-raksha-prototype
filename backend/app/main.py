import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from huggingface_hub import InferenceClient
from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from pydantic import BaseModel
from supabase import Client, create_client

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent.parent
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client | None = (
    create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
    else None
)


def new_auth_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=503, detail="Add Supabase credentials to backend/.env.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

app = FastAPI(title="Fasal Raksha AI", version="1.0.0")
origins = [origin.strip() for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str
    language: str = "en"


class AuthRequest(BaseModel):
    phone: str
    password: str
    full_name: str = ""


def normalized_phone(phone: str) -> str:
    digits = "".join(character for character in phone if character.isdigit())
    if len(digits) == 10:
        return "+91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    raise HTTPException(status_code=400, detail="Enter a valid 10-digit Indian mobile number.")


def auth_email(phone: str) -> str:
    return phone.replace("+", "") + "@auth.fasalraksha.app"


def response_language(language: str) -> str:
    return "hi" if language.lower().startswith("hi") else "en"


def localized_disease(disease: str, language: str) -> str:
    if language != "hi":
        return disease
    replacements = {
        "Healthy": "स्वस्थ",
        "Plant": "पौधा",
        "Strawberry": "स्ट्रॉबेरी",
        "Tomato": "टमाटर",
        "Potato": "आलू",
        "Corn": "मक्का",
        "Apple": "सेब",
        "Grape": "अंगूर",
        "Disease": "रोग",
        "Leaf": "पत्ती",
        "Blight": "झुलसा रोग",
        "Mildew": "फफूंदी",
        "Rust": "रस्ट रोग",
        "Spot": "धब्बा रोग",
        "Yellow": "पीला",
        "Virus": "वायरस",
        "Bacteria": "बैक्टीरिया",
    }
    for english, hindi in replacements.items():
        disease = disease.replace(english, hindi)
    return disease


def signed_image_url(client: Client, storage_path: str) -> str:
    result = client.storage.from_(os.getenv("SUPABASE_STORAGE_BUCKET", "crop-images")).create_signed_url(storage_path, 3600)
    return result.get("signedURL") or result.get("signedUrl") or result.get("signed_url")


def require_supabase() -> Client:
    if not supabase:
        raise HTTPException(status_code=503, detail="Add Supabase credentials to backend/.env.")
    return supabase


def current_user(authorization: str | None = Header(default=None), client: Client = Depends(require_supabase)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Please log in first.")
    try:
        user_response = client.auth.get_user(authorization.split(" ", 1)[1])
        if not user_response.user:
            raise ValueError
        return {"id": str(user_response.user.id), "phone": user_response.user.phone}
    except Exception as error:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.") from error


def detect_disease(image_path: Path) -> str:
    token = os.getenv("HF_TOKEN")
    if not token:
        return "Disease detection is waiting for HF_TOKEN in backend/.env."

    client = InferenceClient(token=token)
    try:
        predictions = client.image_classification(image_path, model=os.getenv("HF_VISION_MODEL"))
    except Exception as error:
        raise RuntimeError(
            "Plant AI model could not process this image. Check HF_VISION_MODEL and HF_TOKEN."
        ) from error
    if not predictions:
        return "No clear disease signal was found in the image."
    top = predictions[0]
    return f"{top.label} ({top.score:.0%} model confidence)"


def search_guidance(query: str) -> list[dict[str, str]]:
    if not os.getenv("TAVILY_API_KEY"):
        return []
    search = TavilySearchAPIWrapper(tavily_api_key=os.environ["TAVILY_API_KEY"])
    results = search.results(query, max_results=5)
    return [
        {
            "title": item.get("title", "Source"),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
        }
        for item in results
        if item.get("url")
    ]


def answer_with_langchain(disease: str, question: str, sources: list[dict[str, str]], language: str = "en") -> str:
    if not os.getenv("HF_TOKEN"):
        if language == "hi":
            return fallback_answer(disease, question, sources, language)
        return (
            f"The current finding is: {disease}\n\n"
            "Add HF_TOKEN and TAVILY_API_KEY to backend/.env for an AI explanation "
            "with current, source-backed treatment guidance. Do not apply chemicals "
            "until the crop, product label, and local agriculture advice are confirmed."
        )

    source_text = "\n".join(f"- {source['title']}: {source['url']}" for source in sources)
    language_instruction = "Respond entirely in Hindi using simple Devanagari. Keep the product name Fasal Raksha exactly as written." if language == "hi" else "Respond entirely in English. Keep the product name Fasal Raksha exactly as written."
    prompt = f"""You are a careful agricultural assistant for Indian farmers.
Possible crop finding: {disease}
Farmer question: {question}
Web sources:
{source_text or 'No web sources were available.'}

Give a practical answer in simple language. Separate likely cause, immediate steps,
prevention, and a safety note. Never invent pesticide dosage; tell the farmer to
follow the product label and consult a local agriculture officer when uncertain.
{language_instruction}
"""
    try:
        endpoint = HuggingFaceEndpoint(
            repo_id=os.getenv("HF_CHAT_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
            huggingfacehub_api_token=os.environ["HF_TOKEN"],
            temperature=0.2,
            max_new_tokens=500,
        )
        response = ChatHuggingFace(llm=endpoint).invoke(prompt)
        return response.content
    except Exception:
        return fallback_answer(disease, question, sources, language)


def fallback_answer(disease: str, question: str, sources: list[dict[str, str]], language: str = "en") -> str:
    evidence = "\n\n".join(
        f"{source['title']}: {source.get('content', '').strip()}"
        for source in sources[:3]
        if source.get("content")
    )
    if language == "hi":
        return (
            f"संभावित पहचान: {disease}\n\n"
            "सबसे पहले प्रभावित पत्तियों और पौधों को अलग करें। पत्तियों पर ऊपर से पानी न डालें "
            "और खेत में हवा का आवागमन बनाए रखें। उपचार करने से पहले फसल, बीमारी और उत्पाद का लेबल जांचें।\n\n"
            "इंटरनेट से मिले स्रोतों के आधार पर समाधान: प्रभावित हिस्से हटाएं, साफ औजारों का उपयोग करें, "
            "पानी जमा न होने दें और उत्पाद के लेबल के अनुसार ही उपचार करें। तेज संक्रमण होने पर स्थानीय "
            "कृषि अधिकारी से सलाह लें। नीचे दिए गए स्रोतों में अधिक जानकारी देखें।"
        )
    return (
        f"Possible finding: {disease}\n\n"
        f"For your question ({question}), start by isolating affected leaves, avoiding overhead watering, "
        "and checking the crop and product label before using any treatment. The following current web "
        f"guidance was found:\n\n{evidence or 'No detailed web summary was returned.'}\n\n"
        "Use the linked sources below and consult a local agriculture officer before applying chemicals."
    )


def make_answer(disease: str, question: str, language: str = "en") -> tuple[str, list[dict[str, str]]]:
    sources = search_guidance(f"{disease} treatment prevention India agriculture {question}")
    display_disease = localized_disease(disease, language)
    return answer_with_langchain(display_disease, question, sources, language), sources


@app.get("/health")
def health() -> dict[str, Any]:
    schema_ready = False
    if supabase:
        try:
            supabase.table("farmer_profiles").select("user_id").limit(1).execute()
            supabase.table("scans").select("id").limit(1).execute()
            schema_ready = True
        except Exception:
            schema_ready = False
    return {
        "status": "ok",
        "huggingface_configured": bool(os.getenv("HF_TOKEN")),
        "tavily_configured": bool(os.getenv("TAVILY_API_KEY")),
        "supabase_configured": bool(supabase),
        "database_schema_ready": schema_ready,
        "otp_enabled": False,
    }


@app.post("/api/auth/signup")
def signup(request: AuthRequest, client: Client = Depends(require_supabase)) -> dict[str, Any]:
    try:
        phone = normalized_phone(request.phone)
        full_name = request.full_name.strip()
        if not full_name:
            raise HTTPException(status_code=400, detail="Full name is required for registration.")
        existing_response = client.table("farmer_profiles").select("user_id").eq("phone", phone).maybe_single().execute()
        existing_data = getattr(existing_response, "data", None)
        if existing_data:
            raise HTTPException(status_code=409, detail="This mobile number is already registered. Please log in.")
        result = client.auth.admin.create_user({
            "email": auth_email(phone),
            "password": request.password,
            "email_confirm": True,
            "user_metadata": {"full_name": full_name, "phone": phone},
        })
        if not result.user:
            raise HTTPException(status_code=400, detail="Supabase did not create the farmer account.")
        client.table("farmer_profiles").insert({"user_id": str(result.user.id), "phone": phone, "full_name": full_name}).execute()
        session_result = new_auth_client().auth.sign_in_with_password({"email": auth_email(phone), "password": request.password})
        return {
            "message": "Registration complete. You can start scanning your crops.",
            "access_token": session_result.session.access_token,
            "user": result.user,
        }
    except HTTPException:
        raise
    except Exception as error:
        if "duplicate key" in str(error).lower() or "already been registered" in str(error).lower():
            raise HTTPException(status_code=409, detail="This mobile number is already registered. Please log in.") from error
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/auth/login")
def login(request: AuthRequest, client: Client = Depends(require_supabase)) -> dict[str, Any]:
    try:
        phone = normalized_phone(request.phone)
        profile_response = client.table("farmer_profiles").select("user_id,full_name").eq("phone", phone).maybe_single().execute()
        profile_data = getattr(profile_response, "data", None)
        if not profile_data:
            raise HTTPException(status_code=401, detail="Invalid mobile number or password.")
        result = new_auth_client().auth.sign_in_with_password({"email": auth_email(phone), "password": request.password})
        full_name = profile_data.get("full_name", "") if profile_data else ""
        if not full_name:
            full_name = (getattr(result.user, "user_metadata", {}) or {}).get("full_name", "Farmer")
        return {"access_token": result.session.access_token, "user": result.user, "full_name": full_name}
    except Exception as error:
        raise HTTPException(status_code=401, detail="Invalid mobile number or password.") from error


@app.post("/api/scans")
async def create_scan(image: UploadFile = File(...), language: str = "en", user: dict[str, Any] = Depends(current_user), client: Client = Depends(require_supabase)) -> dict[str, Any]:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Please upload an image file.")

    extension = Path(image.filename or "crop.jpg").suffix.lower() or ".jpg"
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=415, detail="Use JPG, PNG, or WEBP images.")

    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be smaller than 10 MB.")

    scan_id = str(uuid.uuid4())
    storage_path = f"{user['id']}/{scan_id}{extension}"
    client.storage.from_(os.getenv("SUPABASE_STORAGE_BUCKET", "crop-images")).upload(storage_path, image_bytes, {"content-type": image.content_type})
    try:
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temporary_image:
            temporary_image.write(image_bytes)
            temporary_image_path = Path(temporary_image.name)
        disease = detect_disease(temporary_image_path)
        language = response_language(language)
        first_question = "मुझे सबसे पहले क्या करना चाहिए?" if language == "hi" else "What should I do first?"
        answer, sources = make_answer(disease, first_question, language)
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="AI guidance service is temporarily unavailable. Please try again.") from error
    finally:
        if "temporary_image_path" in locals():
            temporary_image_path.unlink(missing_ok=True)
    scan_record = {"id": scan_id, "user_id": user["id"], "image_path": storage_path, "disease": disease, "answer": answer, "sources": sources, "language": language}
    try:
        client.table("scans").insert(scan_record).execute()
    except Exception as error:
        if "language" not in str(error).lower() or "schema cache" not in str(error).lower():
            raise HTTPException(status_code=502, detail="Scan could not be saved. Please try again.") from error
        client.table("scans").insert({key: value for key, value in scan_record.items() if key != "language"}).execute()
    return {"scan_id": scan_id, "image_url": signed_image_url(client, storage_path), "disease": localized_disease(disease, language), "answer": answer, "sources": sources, "language": language}


@app.get("/api/scans")
def list_scans(user: dict[str, Any] = Depends(current_user), client: Client = Depends(require_supabase)) -> list[dict[str, Any]]:
    try:
        result = client.table("scans").select("id,image_path,disease,created_at,language").eq("user_id", user["id"]).order("created_at", desc=True).limit(30).execute()
    except Exception as error:
        error_text = str(error).lower()
        if "language" not in error_text or ("schema cache" not in error_text and "column scans.language does not exist" not in error_text):
            raise HTTPException(status_code=502, detail="Scan history could not be loaded.") from error
        result = client.table("scans").select("id,image_path,disease,created_at").eq("user_id", user["id"]).order("created_at", desc=True).limit(30).execute()
    history = []
    for scan in result.data or []:
        history.append({
            "scan_id": scan["id"],
            "image_url": signed_image_url(client, scan["image_path"]),
            "disease": scan["disease"],
            "created_at": scan["created_at"],
            "language": scan.get("language", "en"),
        })
    return history


@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: str, user: dict[str, Any] = Depends(current_user), client: Client = Depends(require_supabase)) -> dict[str, Any]:
    result = client.table("scans").select("*").eq("id", scan_id).eq("user_id", user["id"]).single().execute()
    scan = result.data
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found. Please upload the image again.")
    language = scan.get("language", "en")
    return {"scan_id": scan["id"], "image_url": signed_image_url(client, scan["image_path"]), "disease": localized_disease(scan["disease"], language), "answer": scan["answer"], "sources": scan["sources"], "language": language}


@app.post("/api/scans/{scan_id}/chat")
def chat(scan_id: str, request: ChatRequest, user: dict[str, Any] = Depends(current_user), client: Client = Depends(require_supabase)) -> dict[str, Any]:
    result = client.table("scans").select("disease").eq("id", scan_id).eq("user_id", user["id"]).single().execute()
    scan = result.data
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found. Please upload the image again.")
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Please enter a question.")
    language = response_language(request.language)
    answer, sources = make_answer(scan["disease"], request.question.strip(), language)
    return {"answer": answer, "sources": sources}
