import os
import traceback

import litellm
import openai
import tokentrim as tt

from ...terminal_interface.utils.display_markdown_message import (
    display_markdown_message,
)


def setup_text_llm(interpreter):
    """
    Takes an Interpreter (which includes a ton of LLM settings),
    returns a text LLM (an OpenAI-compatible chat LLM with baked-in settings. Only takes `messages`).
    """

    # Pass remaining parameters to LiteLLM
    def base_llm(messages):
        """
        Returns a generator
        """

        system_message = messages[0]["content"]

        messages = messages[1:]

        try:
            if interpreter.llm.context_window and interpreter.llm.max_tokens:
                trim_to_be_this_many_tokens = (
                    interpreter.llm.context_window - interpreter.llm.max_tokens - 25
                )  # arbitrary buffer
                messages = tt.trim(
                    messages,
                    system_message=system_message,
                    max_tokens=trim_to_be_this_many_tokens,
                )
            elif interpreter.llm.context_window and not interpreter.llm.max_tokens:
                # Just trim to the context window if max_tokens not set
                messages = tt.trim(
                    messages,
                    system_message=system_message,
                    max_tokens=interpreter.llm.context_window,
                )
            else:
                try:
                    messages = tt.trim(
                        messages,
                        system_message=system_message,
                        model=interpreter.llm.model,
                    )
                except:
                    if len(messages) == 1:
                        display_markdown_message(
                            """
                        **We were unable to determine the context window of this model.** Defaulting to 3000.
                        If your model can handle more, run `interpreter --context_window {token limit}` or `interpreter.llm.context_window = {token limit}`.
                        Also, please set max_tokens: `interpreter --max_tokens {max tokens per response}` or `interpreter.llm.max_tokens = {max tokens per response}`
                        """
                        )
                    messages = tt.trim(
                        messages, system_message=system_message, max_tokens=3000
                    )

        except TypeError as e:
            if interpreter.vision and str(e) == "expected string or buffer":
                # There's just no way to use tokentrim on vision-enabled models yet.
                # We instead handle this outside setup_text_llm!

                if interpreter.debug_mode:
                    print("Won't token trim image messages. ", e)

                ### DISABLED image trimming
                # To maintain the order of messages while simulating trimming, we will iterate through the messages
                # and keep only the first 2 and last 2 images, while keeping all non-image messages.
                # trimmed_messages = []
                # image_counter = 0
                # for message in messages:
                #     if (
                #         "content" in message
                #         and isinstance(message["content"], list)
                #         and len(message["content"]) > 1
                #     ):
                #         if message["content"][1]["type"] == "image":
                #             image_counter += 1
                #             if (
                #                 image_counter <= 2
                #                 or image_counter
                #                 > len(
                #                     [
                #                         m
                #                         for m in messages
                #                         if m["content"][1]["type"] == "image"
                #                     ]
                #                 )
                #                 - 2
                #             ):
                #                 # keep message normal
                #                 pass
                #             else:
                #                 message["content"].pop(1)

                #         trimmed_messages.append(message)
                # messages = trimmed_messages

                # Reunite messages with system_message
                messages = [{"role": "system", "content": system_message}] + messages
            else:
                raise

        if interpreter.debug_mode:
            print("Passing messages into LLM:", messages)

        # Create LiteLLM generator
        params = {
            "model": interpreter.llm.model,
            "messages": messages,
            "stream": True,
        }

        # Optional inputs
        if interpreter.llm.api_base:
            params["api_base"] = interpreter.llm.api_base
        if interpreter.llm.api_key:
            params["api_key"] = interpreter.llm.api_key
        if interpreter.api_version:
            params["api_version"] = interpreter.api_version
        if interpreter.llm.max_tokens:
            params["max_tokens"] = interpreter.llm.max_tokens
        if interpreter.llm.temperature is not None:
            params["temperature"] = interpreter.llm.temperature
        else:
            params["temperature"] = 0.0

        # DISABLED:
        # if the user has their api_key in a environment variable, it will be overwritten here.
        # We should just ask LiteLLM to not require an API key!
        # if not "api_key" in params:
        #     params["api_key"] = "sk-dummykey"

        if interpreter.llm.model == "gpt-4-vision-preview":
            # We need to go straight to OpenAI for this, LiteLLM doesn't work
            if interpreter.llm.api_base:
                openai.api_base = interpreter.llm.api_base
            if interpreter.llm.api_key:
                openai.api_key = interpreter.llm.api_key
            if interpreter.api_version:
                openai.api_version = interpreter.api_version
            return openai.ChatCompletion.create(**params)

        # LiteLLM

        # These are set directly on LiteLLM
        if interpreter.max_budget:
            litellm.max_budget = interpreter.max_budget
        if interpreter.debug_mode:
            litellm.set_verbose = True

        # Report what we're sending to LiteLLM
        if interpreter.debug_mode:
            print("Sending this to LiteLLM:", params)

        return litellm.completion(**params)

    return base_llm
