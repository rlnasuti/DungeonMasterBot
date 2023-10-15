import openai
import json
import ast
import os
import chainlit as cl

from bot.utils.functions import FUNCTIONS
from bot.main import consult_rulebook, create_and_save_character, get_character_state, load_game, save_game, update_character
from bot.setup import check_and_build_vectorstore, initialize_conversation
from bot.models.conversation import Conversation

openai.api_key = os.environ.get("OPENAI_API_KEY")

MAX_ITER = 5

async def process_new_delta(
    new_delta, openai_message, content_ui_message, function_ui_message
):
    if "role" in new_delta:
        openai_message["role"] = new_delta["role"]
    if "content" in new_delta:
        new_content = new_delta.get("content") or ""
        openai_message["content"] += new_content
        await content_ui_message.stream_token(new_content)
    if "function_call" in new_delta:
        if "name" in new_delta["function_call"]:
            openai_message["function_call"] = {
                "name": new_delta["function_call"]["name"]
            }
            function_ui_message = cl.Message(
                author=new_delta["function_call"]["name"],
                content="",
                indent=1,
                language="json",
            )
            await function_ui_message.stream_token(new_delta["function_call"]["name"])

        if "arguments" in new_delta["function_call"]:
            if "arguments" not in openai_message["function_call"]:
                openai_message["function_call"]["arguments"] = ""
            openai_message["function_call"]["arguments"] += new_delta["function_call"][
                "arguments"
            ]
            await function_ui_message.stream_token(
                new_delta["function_call"]["arguments"]
            )
    return openai_message, content_ui_message, function_ui_message

@cl.on_chat_start
def start_chat():
    check_and_build_vectorstore()
    conversation = initialize_conversation()
    cl.user_session.set(
        "conversation",
        conversation,
    )

@cl.on_message
async def run_conversation(user_message: str):
    conversation: Conversation = cl.user_session.get("conversation")
    conversation.add_user_message(user_message)

    cur_iter = 0

    while cur_iter < MAX_ITER:
        # OpenAI call
        openai_message = {"role": "", "content": ""}
        function_ui_message = None
        content_ui_message = cl.Message(content="")
        async for stream_resp in await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo-0613",
            messages=conversation.get_messages(),
            stream=True,
            function_call="auto",
            functions=FUNCTIONS,
            temperature=0,
        ):
            new_delta = stream_resp.choices[0]["delta"]
            (
                openai_message,
                content_ui_message,
                function_ui_message,
            ) = await process_new_delta(
                new_delta, openai_message, content_ui_message, function_ui_message
            )

        await content_ui_message.send()

        conversation.add_assistant_message(openai_message['content'])
        if function_ui_message is not None:
            await function_ui_message.send()

        if stream_resp.choices[0]["finish_reason"] == "stop":
            break

        elif stream_resp.choices[0]["finish_reason"] != "function_call":
            raise ValueError(stream_resp.choices[0]["finish_reason"])

        # if code arrives here, it means there is a function call
        function_name = openai_message.get("function_call").get("name")
        function_args = ast.literal_eval(
            openai_message.get("function_call").get("arguments")
        )

        if function_name == "consult_rulebook":
            function_response = consult_rulebook(
                question=function_args.get("question"),
            )
        if function_name == "create_and_save_character":
            function_response = create_and_save_character(
                name=function_args.get("name"),
                character_class=function_args.get("character_class"),
                race=function_args.get("race"),
                level=function_args.get("level"),
                background=function_args.get("background"),
                alignment=function_args.get("alignment"),
                experience_points=function_args.get("experience_points"),
                strength=function_args.get("strength"),
                dexterity=function_args.get("dexterity"),
                constitution=function_args.get("constitution"),
                wisdom=function_args.get("wisdom"),
                intelligence=function_args.get("intelligence"),
                charisma=function_args.get("charisma"),
                proficiency_bonus=function_args.get("proficiency_bonus"),
                skills=function_args.get("skills"),
                saving_throws=function_args.get("saving_throws"),
                max_hit_points=function_args.get("max_hit_points"),
                hit_dice=function_args.get("hit_dice"),
                death_saves=function_args.get("death_saves"),
                equipment=function_args.get("equipment"),
                spells=function_args.get("spells"),
                languages=function_args.get("languages"),
                features_and_traits=function_args.get("features_and_traits"),
                notes=function_args.get("notes")
            )
        if function_name == "update_character":
            function_response = update_character(
                name=function_args.get("name"),
                additional_experience_points=function_args.get("additional_experience_points"),
                additional_death_saves_successes=function_args.get("additional_death_saves_successes"),
                additional_death_saves_failures=function_args.get("additional_death_saves_failures"),
                delta_hit_points=function_args.get("delta_hit_points"),
                additional_level_1_spell_slots_used=function_args.get("additional_level_1_spell_slots_used")
            )            
        if function_name == "load_game":
            name=function_args.get("name")
            conversation.messages = load_game(name)
            function_response=f"The game for {name} was stopped by the user after the prior save. Everything worked perfectly and now it has now been successfully reloaded."
            conversation.add_user_message("Let's resume the game. Please provide a summary for what's happening.")
        if function_name == "save_game":
            function_response = save_game(function_args.get("name"), conversation.messages)
        if function_name == "get_character_state":
            function_response = get_character_state(function_args.get("name"))

        conversation.add_function_message(function_name=function_name, function_response=function_response)

        await cl.Message(
            author=function_name,
            content=str(function_response),
            language="json",
            indent=1,
        ).send()

        cur_iter += 1