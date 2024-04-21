# discord-gcpai-bot

<p align="left">
  <a href="https://fishwongy.github.io/" target="_blank"><img src="https://img.shields.io/badge/Blog-Read%20About%20This%20Project-blue.svg" /></a>
  <!--<a href="https://twitter.com/intent/follow?screen_name=fishwongxd" target="_blank"><img src="https://img.shields.io/twitter/follow/fishwongxd?style=social" /></a>-->
</p>

Gemini AI assistant w/ Discord integration

This project is a Discord Chatbot that uses various LLM model frpm Google to provide automated responses. It was developed in Python and uses the Vertex API and Discord API for chat operations.

## ✨ Demo
![dc-demo](https://github.com/FISHWONGY/discord-gcpai-bot/assets/59711659/0e928194-e2b3-4cc2-a1c8-6528f7d9ca0c)



## ✨ Background

The core functionality of the chatbot is provided by Googel's Generative Language model, specifically with the Gemini, Bison and Code-Bison Model.
Discord is a collaboration platform that can be used as a messsaging tool. This project uses the Python `pycord` library to interact with users on the platform.

## 📁 Folder Structure
```
.
├── Dockerfile
├── README.md
├── app
│   ├── commands.py
│   ├── helpers
│   │   ├── common_func.py
│   │   ├── gcp_ai.py
│   │   ├── gcp_secrets.py
│   │   ├── gcp_storage.py
│   │   ├── gcp_vertexai_rag.py
│   │   ├── prompts.py
│   │   └── pycordapi.py
│   ├── main.py
│   └── utils
│       ├── matching_engine.py
│       └── matching_engine_utils.py
├── deploy
│   ├── common
│   │   ├── config.yaml
│   │   ├── deployment.yaml
│   │   ├── kustomization.yaml
│   │   └── serviceaccount.yaml
│   └── production
│       └── kustomization.yaml
├── poetry.lock
├── pyproject.toml
└── skaffold.yaml


```

## 💡 Software Architecture
![dc-architecture](https://github.com/FISHWONGY/discord-gcpai-bot/assets/59711659/111dcbd6-2202-4fc4-9938-47949517a3c0)

## 🚀 Installation
1. ```git clone https://github.com/FISHWONGY/discord-gcpai-bot/```

2. ```poetry install```

3. Set all env var

4. ```python main.py```


## 😎 Getting Started
Just type `/help` to ge started</br></br>

![dc-help](https://github.com/FISHWONGY/discord-gcpai-bot/assets/59711659/103ad5a6-0ec2-4038-a4c7-babf7c666bdf)


 ## ✨ Features

    - General Chat Response: Your choice on which LLM to interact with! The chatbot can understand human language and return a logical response.
    - Generate AI Image: The chatbot will generate AI images for useres based on input.
    - Code Assistance: The chatbot can provide assistance with code-related issues.
    - Save History: Fetch previous chat history from the channel and save to GCS bucket
    - Clear History: Owner can clear a specified number of message from the discord channel.


 ## ✨ Usage

To use the bot, send messages to it on Discord using the following command format:
- For RAG: ```/rag <your query>```

- For AI Generated images: ```/img <your prompt>```


- For Gemini one-off conversation: ```/gemini <your question>```


- For Gemini one-off python assistant conversation: ```/py <your question>```


- For codechat-bison one-off python assistant conversation: ```/pycode <your question>```


- For Bison V2 LLM one-off conversation: ```/lang <your question>```


- For chat history retrieval: ```/hist <optional int: 1-100, default: 10>```


- Clear chat history: ```!clear <optional int: 1-100, default: 10>```
