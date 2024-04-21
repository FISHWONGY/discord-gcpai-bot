from google.oauth2 import service_account
import google.auth.transport.requests
import vertexai
from vertexai.preview.generative_models import (
    GenerativeModel,
    ChatSession,
    Content,
    Part,
)
from vertexai.language_models import (
    ChatModel,
    CodeChatModel,
    InputOutputTextPair,
    ChatMessage,
)
from helpers.prompts import Prompts
from helpers.gcp_secrets import GCPSecrets
from helpers.gcp_storage import GCPStorage
from helpers.common_func import Helpers
import base64
from datetime import datetime
from os import getenv

GCP_PROJECT = getenv("GCP_PROJECT_ID")
helpers = Helpers()
prompts = Prompts()
secrets = GCPSecrets()
gcsapi = GCPStorage()


class GCPAI:
    def __init__(self) -> None:
        vertexai.init(project=GCP_PROJECT, location="us-central1")

        self.chat_model = ChatModel.from_pretrained("chat-bison@002")
        self.chat_context = prompts.USER_PROMPT1
        self.chat_history = [
            InputOutputTextPair(
                input_text="Who do you work for?",
                output_text="I work for you.",
            ),
            InputOutputTextPair(
                input_text=prompts.USER_PROMPT2,
                output_text=prompts.SYSTEM_PROMPT2,
            ),
        ]
        self.chat_agent = self.chat_model.start_chat(
            context=self.chat_context, examples=self.chat_history
        )

        self.codechat_model = CodeChatModel.from_pretrained("codechat-bison")
        self.codechat_context = prompts.PYTHON_CONTEXT_PROMPT
        self.codechat_history = [
            ChatMessage(author="user", content=prompts.PYTHON_USER_PROMPT2),
            ChatMessage(author="bot", content=prompts.PYTHON_SYSTEM_PROMPT2),
            ChatMessage(author="user", content=prompts.PYTHON_USER_PROMPT3),
            ChatMessage(author="bot", content=prompts.PYTHON_SYSTEM_PROMPT3),
        ]
        self.codechat_agent = self.codechat_model.start_chat(
            context=self.chat_context, message_history=self.codechat_history
        )

        self.gem_model = GenerativeModel("gemini-pro")
        self.gem_code_history = [
            Content(
                role="user",
                parts=[Part.from_text(prompts.PYTHON_CONTEXT_PROMPT)],
            ),
            Content(
                role="model",
                parts=[Part.from_text(prompts.PYTHON_SYSTEM_PROMPT1)],
            ),
            Content(
                role="user",
                parts=[Part.from_text(prompts.PYTHON_USER_PROMPT2)],
            ),
            Content(
                role="model",
                parts=[Part.from_text(prompts.PYTHON_SYSTEM_PROMPT2)],
            ),
            Content(
                role="user",
                parts=[Part.from_text(prompts.PYTHON_USER_PROMPT3)],
            ),
            Content(
                role="model",
                parts=[Part.from_text(prompts.PYTHON_SYSTEM_PROMPT3)],
            ),
        ]
        self.gem_agent = self.gem_model.start_chat()
        self.gem_code_agent = self.gem_model.start_chat(history=self.gem_code_history)

        self.agents_config = {
            "gem": {
                "agent": self.gem_agent,
                "model": GenerativeModel("gemini-pro"),
                "clean_chat_params": {"history": []},
            },
            "gem_code": {
                "agent": self.gem_code_agent,
                "model": GenerativeModel("gemini-pro"),
                "clean_chat_params": {"history": []},
                "start_chat_params": {"history": self.gem_code_history},
            },
            "chat": {
                "agent": self.chat_agent,
                "model": ChatModel.from_pretrained("chat-bison@002"),
                "clean_chat_params": {"examples": []},
                "start_chat_params": {
                    "context": self.chat_context,
                    "examples": self.chat_history,
                },
            },
            "code_chat": {
                "agent": self.codechat_agent,
                "model": CodeChatModel.from_pretrained("codechat-bison"),
                "clean_chat_params": {"message_history": []},
                "start_chat_params": {
                    "context": self.codechat_context,
                    "message_history": self.codechat_history,
                },
            },
        }

        self.SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
        self.gcp_creds = secrets.get_secret("creds-json")
        self.gcp_creds_dict = helpers.extract_json_string(self.gcp_creds)
        self.credentials = service_account.Credentials.from_service_account_info(
            self.gcp_creds_dict, scopes=self.SCOPES
        )
        self.img_gen5_endpoint = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{GCP_PROJECT}/locations/us-central1/publishers/google/models/imagegeneration:predict"
        self.img_gen2_endpoint = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{GCP_PROJECT}/locations/us-central1/publishers/google/models/imagegeneration@002:predict"
        self.img_styles = [
            "photograph",
            "digital_art",
            "landscape",
            "sketch",
            "watercolor",
            "cyberpunk",
            "pop_art",
        ]
        self.img_bucket = gcsapi.get_gcs_bucket(f"{GCP_PROJECT}-aigen-image")

    def get_response(
        self, prompt: str, response_type: str, use_existing_session: bool = True
    ) -> str:
        agent_info = self.agents_config[response_type]
        if use_existing_session:
            agent_to_use = agent_info["agent"]
        else:
            model = agent_info["model"]
            agent_to_use = model.start_chat(**agent_info.get("start_chat_params", {}))

        response = agent_to_use.send_message(prompt)
        return response.text

    def img_gen(self, prompt: str, style: str = None) -> bytes:
        authed_session = google.auth.transport.requests.AuthorizedSession(
            self.credentials
        )
        data = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1}}

        if style is not None:
            data["parameters"]["sampleImageStyle"] = f"{style}"
            response = authed_session.post(self.img_gen2_endpoint, json=data)
        else:
            response = authed_session.post(self.img_gen5_endpoint, json=data)

        response_data = response.json()
        predictions = response_data.get("predictions", [])

        image_data = predictions[0]["bytesBase64Encoded"]

        return base64.b64decode(image_data)

    def get_img_url(self, prompt: str, key_word: str, style: str = None) -> str:
        data = self.img_gen(prompt, style)
        url = gcsapi.upload_img(
            f'{datetime.now().strftime("%Y%m%d")}/image_{datetime.now().strftime("%Y%m%d%H%M%S")}_{key_word}.png',
            self.img_bucket,
            data,
        )
        return url
