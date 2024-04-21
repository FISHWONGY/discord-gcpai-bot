from discord.ext import commands
from discord.ui import View, Button
import discord
import emoji
from helpers.gcp_secrets import GCPSecrets
from helpers.gcp_storage import GCPStorage
from datetime import datetime

secrets = GCPSecrets()
gcsapi = GCPStorage()


class DiscordBot:
    def __init__(self) -> None:
        self.intents = discord.Intents.all()
        self.activity = discord.Activity(
            type=discord.ActivityType.competing, name="/help | !help"
        )
        self.status = discord.Status.online
        self.TEST_SER_ID = secrets.get_secret("dc-ser-id1")
        self.DC_SER_ID = secrets.get_secret("dc-ser-id2")
        self.DEMO_SER_ID = secrets.get_secret("dc-ser-id3")
        self.TOKEN = secrets.get_secret("dc-bot-token")
        self.DC_ID = [secrets.get_secret("dc-id")]
        self.DC_BUCKET = gcsapi.get_gcs_bucket("gcp-prj-123-discord-gcpai-bot")

        self.HELP_MSG_DEATILS = {
            "gemini": "**/gemini** followed by question you want to ask\n\nExample:\n\n`/gemini prompt: How far is Mars from Earth`",
            "img": "**/img** followed by the your prompt\n\nExample:\n\n`/img prompt: soft purl the streams, the birds renew their notes, and through the air their mingled music floats`\n\nOptionally, you could also define image style:\n`/img prompt: soft purl the streams, the birds renew their notes, and through the air their mingled music floats style: cyberpunk`\n\nAvailable image style: photograph/ digital_art/ landscape/ sketch/ watercolor/ cyberpunk/ pop_art",
            "rag": "**/rag** followed by the your prompt\n\nExample:\n\n`/rag question: What is Formula 1 regulation`",
            "lang": "**/lang** followed by question you want to ask\n\nExample:\n\n`/lang prompt: How far is Mars from Earth`",
            "py": "**/py** followed by question you want to ask\n\nExample:\n\n`/py prompt: How to print hello world`",
            "pycode": "**/pycode** followed by the python question you want to ask\n\nExample:\n\n`pycode prompt: how to print hello world`",
            "hist": "**/hist** followed by an integer between 1-100 of how many chat history you want to fetch, default is 10 when not specified\n\nExample:\n\n`/hist` or `/hist limit: 20`",
        }

    def bot_initiate(self):
        return commands.Bot(
            command_prefix="!", intents=self.intents, activity=self.activity
        )

    @staticmethod
    def split_response(response: str, max_length: int = 1500) -> list:
        chunks = [
            response[i : i + max_length] for i in range(0, len(response), max_length)
        ]

        for i in range(len(chunks)):
            if len(chunks[i]) > max_length:
                last_whitespace = chunks[i].rfind(" ")
                if last_whitespace != -1:
                    chunks[i] = chunks[i][:last_whitespace]

            if chunks[i].count("```") % 2 != 0:
                code_open_pos = chunks[i].rfind("```")
                code_close_pos = chunks[i].find("\n", code_open_pos)

                code_lang = chunks[i][code_open_pos + 3 : code_close_pos]

                chunks[i] += "\n```"

                if i + 1 < len(chunks):
                    chunks[i + 1] = f"```{code_lang}\n" + chunks[i + 1]

        return chunks

    @staticmethod
    def format_embed(
        chunk: str,
        description: str,
        color: discord.Colour,
        author_name: str,
        res_name: str = "Chat Bot Response",
    ) -> discord.Embed:
        embed = discord.Embed(
            # title="Gojo AI",
            description=description,
            color=color,
        )
        embed.add_field(name=res_name, value=f"{chunk}")
        embed.set_author(
            name=author_name,
            icon_url="https://pnghq.com/wp-content/uploads/pnghq.com-jujutsu-kaisen-satoru-gojo-smile-sticker.png",
        )

        return embed

    @staticmethod
    def slash_help_embed() -> discord.Embed:
        embed = discord.Embed(
            title=emoji.emojize(":robot: Google Powered AI Bot! :robot:"),
            description="\n\n"
            "• **Quickstart** with Gemini `!g <your-input>`\n"
            "• For More info on `!` Bot Command do `!help`\n\n"
            "• For More info on **Slash Command** do  `/help <command>`\n"
            "  Example: `/help gemini`\n\n\n",
            color=discord.Colour.from_rgb(31, 102, 138),
        )
        embed.add_field(
            name="Slash Command Categories:",
            value="\n\n"
            "• `/gemini`: Chat with Google's Gemini\n"
            "• `/img`: Generate **AI image** with Vertex AI\n"
            "• `/rag`: RAG System for Formula 1 Regulation\n"
            "• `/lang`: Chat with Google's Bison LLM\n"
            "• `/py`: Chat with Google Gemini Powered Python Assistant\n"
            "• `/pycode`: Chat with Google Codey Powered Python Assistant\n"
            "• `/hist`: Retrieve and save chat history to GCS bucket\n"
            f"{emoji.emojize(':smiling_face_with_sunglasses:  Elevate your Discord experience with Gojo AI :smiling_face_with_sunglasses:')}\n\n",
        )

        embed.timestamp = datetime.utcnow()
        embed.set_footer(text="\u200b")
        embed.set_author(
            name="Gojo AI",
            icon_url="https://pnghq.com/wp-content/uploads/pnghq.com-jujutsu-kaisen-satoru-gojo-smile-sticker.png",
        )
        embed.set_thumbnail(
            url="https://pnghq.com/wp-content/uploads/pnghq.com-jujutsu-kaisen-satoru-gojo-smile-sticker.png"
        )

        return embed

    @staticmethod
    def get_embed(description: str, color: discord.Colour) -> discord.Embed:
        embed = discord.Embed(
            description=description,
            color=color,
        )

        return embed