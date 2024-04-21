from helpers.pycordapi import DiscordBot
from helpers.gcp_ai import GCPAI
from helpers.gcp_vertexai_rag import QuestionAnsweringSystem
from helpers.gcp_storage import GCPStorage
from helpers.common_func import Helpers
import discord
from discord.ext import commands
from datetime import datetime
import emoji
import logging

logger = logging.getLogger(__name__)

helpers = Helpers()
pycordapi = DiscordBot()
gcpaiapi = GCPAI()
qa_system = QuestionAnsweringSystem()
gcsapi = GCPStorage()


bot = pycordapi.bot_initiate()


@bot.event
async def on_ready():
    logger.info(f"We have logged in as {bot.user}")


@bot.command(help="Testing command for bot development")
async def test(ctx, *, args):
    received_msg = "".join(args)

    logger.info(f"Received message: {received_msg} from user {ctx.author} ")

    await ctx.send(f"""Testing. Here is the received message:\n{received_msg}""")


@bot.command(
    pass_context=True, help="Clear a specified number of previous messages from channel"
)
async def clear(ctx, limit: int = 10):
    if limit < 1 or limit > 100:
        await ctx.send(
            embed=pycordapi.get_embed(
                "Error\nClear command format: `!clear {int: 1-100}`",
                discord.Colour.brand_red(),
            )
        )
        return

    channel = ctx.message.channel
    messages = []
    async for message in channel.history(limit=limit):
        messages.append(message)

    if str(ctx.author).split("#")[0] in pycordapi.DC_ID:
        await channel.delete_messages(messages)
        await ctx.send(f"{limit} messages deleted")
    else:
        await ctx.send(
            embed=pycordapi.get_embed(
                emoji.emojize(
                    ":smiling_face_with_sunglasses: Only owner is allowed to delete message :smiling_face_with_sunglasses:"
                ),
                discord.Colour.brand_red(),
            )
        )


@clear.error
async def clear_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument) or isinstance(
        error, commands.BadArgument
    ):
        await ctx.send(
            embed=pycordapi.get_embed(
                "Error\nClear command format: `!clear {int: 1-100}`",
                discord.Colour.brand_red(),
            )
        )


@bot.slash_command(
    name="help",
    guild_ids=[pycordapi.TEST_SER_ID, pycordapi.DC_SER_ID, pycordapi.DEMO_SER_ID],
    description="To show all commands",
)
async def help(ctx, command: str = None):
    await ctx.defer()
    if command is None:
        await ctx.respond(embed=pycordapi.slash_help_embed())
    else:
        help_message = pycordapi.HELP_MSG_DEATILS.get(command)
        if help_message is not None:
            await ctx.respond(
                embed=pycordapi.get_embed(
                    f"{help_message}",
                    discord.Colour.from_rgb(31, 102, 138),
                )
            )
        else:
            await ctx.respond(
                embed=pycordapi.get_embed(
                    "Error\nNot an available slash command, do `/help` to check all available slash command",
                    discord.Colour.brand_red(),
                )
            )


@bot.slash_command(
    name="hist",
    guild_ids=[pycordapi.TEST_SER_ID, pycordapi.DC_SER_ID, pycordapi.DEMO_SER_ID],
    description="Fetch a specified number of messages from the history and save to GCS bucket",
)
async def hist(ctx, limit: int = 10):
    await ctx.defer()

    requestor = str(ctx.author).split("#")[0]
    logger.info(f"{requestor} requested for the last {limit} message history")

    if limit < 1 or limit > 100:
        await ctx.respond(
            embed=pycordapi.get_embed(
                "Error\nHistory command format: `/hist {int: 1-100}`",
                discord.Colour.brand_red(),
            )
        )
        return

    messages = await ctx.channel.history(limit=limit).flatten()

    history = ""
    for message in messages:
        message_time = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        history += f"{message.author.name} - {message_time}: {message.content}\n"
        for embed in message.embeds:
            history += f"{embed.title}\n"
            history += f"{embed.description}\n"
            for field in embed.fields:
                history += f"{field.value}\n"
        history += "---END---\n\n\n"

    print(history)
    gcsapi.upload_text(
        f"chat-history/{datetime.now().strftime('%Y%m%d')}/{requestor}_{limit}_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt",
        pycordapi.DC_BUCKET,
        history,
    )

    await ctx.respond(
        f"Successfully saved the last {limit} message history to [GCS bucket](https://console.cloud.google.com/storage/browser/discord-gcpai-bot/chat-history) requested by {requestor}"
    )


@bot.slash_command(
    name="rag",
    guild_ids=[pycordapi.TEST_SER_ID, pycordapi.DC_SER_ID, pycordapi.DEMO_SER_ID],
    description="Gemini RAG for Formula 1 info",
)
async def rag(ctx, *, question):
    await ctx.defer()
    received_msg = "".join(question)
    logger.info(f"Received message: {received_msg} from user {ctx.author} ")

    try:
        ans = qa_system.ask(received_msg)
    except Exception as e:
        await ctx.respond(f"Response Error from Google API\n```{e}```")
        return

    response_chunks = pycordapi.split_response(ans, 1000)

    for chunk in response_chunks:
        embed = pycordapi.format_embed(
            chunk,
            "Google Gemini Powered AI Bot",
            discord.Colour.blurple(),
            "Gemini",
        )
        await ctx.respond(embed=embed)


@bot.slash_command(
    name="gemini",
    guild_ids=[pycordapi.TEST_SER_ID, pycordapi.DC_SER_ID, pycordapi.DEMO_SER_ID],
    description="Chat with Gemini AI",
)
async def gemini(ctx, *, prompt):
    received_msg = "".join(prompt)
    await ctx.defer()
    logger.info(f"Received message: {received_msg} from user {ctx.author} ")

    try:
        gemini_response = gcpaiapi.get_response(
            received_msg, response_type="gem", use_existing_session=False
        )
    except Exception as e:
        await ctx.respond(f"Response Error from Google API\n```{e}```")
        return

    response_chunks = pycordapi.split_response(gemini_response, 1000)

    for chunk in response_chunks:
        embed = pycordapi.format_embed(
            chunk,
            "Google Gemini Powered AI Bot",
            discord.Colour.blurple(),
            "Gemini",
        )
        await ctx.respond(embed=embed)


@bot.slash_command(
    name="py",
    guild_ids=[pycordapi.TEST_SER_ID, pycordapi.DC_SER_ID, pycordapi.DEMO_SER_ID],
    description="Get Python help from Google Gemini AI",
)
async def py(ctx, *, prompt):
    received_msg = "".join(prompt)
    await ctx.defer()
    logger.info(f"Received message: {received_msg} from user {ctx.author} ")

    try:
        gemini_response = gcpaiapi.get_response(
            received_msg, response_type="gem_code", use_existing_session=False
        )
    except Exception as e:
        await ctx.respond(f"Response Error from Google API\n```{e}```")
        return

    response_chunks = pycordapi.split_response(gemini_response, 1000)

    for chunk in response_chunks:
        embed = pycordapi.format_embed(
            chunk,
            "Google Gemini Powered Python Assistant AI Bot",
            discord.Colour.blurple(),
            "Gemini",
        )
        await ctx.respond(embed=embed)


@bot.slash_command(
    name="lang",
    guild_ids=[pycordapi.TEST_SER_ID, pycordapi.DC_SER_ID, pycordapi.DEMO_SER_ID],
    description="Chat with Google Bison LLM",
)
async def lang(ctx, *, prompt):
    received_msg = "".join(prompt)
    await ctx.defer()
    logger.info(f"Received message: {received_msg} from user {ctx.author} ")

    try:
        response = gcpaiapi.get_response(
            received_msg, response_type="chat", use_existing_session=False
        )
    except Exception as e:
        await ctx.respond(f"Response Error from Google API\n```{e}```")
        return

    response_chunks = pycordapi.split_response(response, 1000)

    for chunk in response_chunks:
        embed = pycordapi.format_embed(
            chunk,
            "Google Language Model Powered AI Bot",
            discord.Colour.brand_red(),
            "Bison v2 Language Model",
        )
        await ctx.respond(embed=embed)


@bot.slash_command(
    name="pycode",
    guild_ids=[pycordapi.TEST_SER_ID, pycordapi.DC_SER_ID, pycordapi.DEMO_SER_ID],
    description="Get Python help from Google Codey",
)
async def pycode(ctx, *, prompt):
    received_msg = "".join(prompt)
    await ctx.defer()
    logger.info(f"Received message: {received_msg} from user {ctx.author} ")

    try:
        pycode_response = gcpaiapi.get_response(
            received_msg, response_type="code_chat", use_existing_session=False
        )
    except Exception as e:
        await ctx.respond(f"Response Error from Google API\n```{e}```")
        return

    response_chunks = pycordapi.split_response(pycode_response, 1000)

    for chunk in response_chunks:
        embed = pycordapi.format_embed(
            chunk,
            "Google Codey Powered AI Bot",
            discord.Colour.dark_gold(),
            "Google Codey",
        )
        await ctx.respond(embed=embed)


@bot.slash_command(
    name="img",
    guild_ids=[pycordapi.TEST_SER_ID, pycordapi.DC_SER_ID, pycordapi.DEMO_SER_ID],
    description="Generate AI image with Google Vertex AI",
)
async def img(ctx, *, prompt, style: str = None):
    await ctx.defer()
    if style is not None and style not in gcpaiapi.img_styles:
        await ctx.respond(
            embed=pycordapi.get_embed(
                "Error\nNot an available image style, do `/help img` to check all available image styles",
                discord.Colour.brand_red(),
            )
        )
        return

    received_msg = "".join(prompt)

    logger.info(f"Received message: {received_msg} from user {ctx.author} ")

    key_word = helpers.get_file_suffix(received_msg)

    try:
        response = gcpaiapi.get_img_url(received_msg, key_word, style)
    except Exception as e:
        await ctx.respond(
            f"Response Error from Google API\n```The response is blocked, as it may violate our policies```"
        )
        return

    await ctx.respond(response)

