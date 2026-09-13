"""Local (CPU) LLM client.

See llm/protocols.py for the LLMClient Protocol this implements.
"""

from __future__ import annotations

import asyncio
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from knowledge_assistant.config import settings
from knowledge_assistant.domain import LLMResponse
from knowledge_assistant.llm.protocols import LLMClient


class LocalLLMClient(LLMClient):
    """Runs a small instruct model locally via `transformers`, entirely on CPU.

    `generate()` is declared `async` to match the LLMClient Protocol - a future Bedrock client
    is genuinely async (network I/O via boto3/aioboto3), but local inference is CPU-bound, not
    I/O-bound, so there's no event loop to cooperate with during `model.generate()`. Rather than
    block the event loop for the whole generation, the actual blocking call is offloaded to a
    worker thread via `asyncio.to_thread`, so every LLMClient implementation presents the same
    async interface regardless of whether the work underneath is really I/O-bound or CPU-bound.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.local_llm_model_name
        self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
        self._model = AutoModelForCausalLM.from_pretrained(self._model_name, dtype=torch.float32)

    async def generate(self, prompt: str, *, max_tokens: int) -> LLMResponse:
        return await asyncio.to_thread(self._generate_sync, prompt, max_tokens)

    def _generate_sync(self, prompt: str, max_tokens: int) -> LLMResponse:
        chat_text = self._tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(chat_text, return_tensors="pt")
        input_token_count = inputs["input_ids"].shape[1]

        start = time.perf_counter()
        output = self._model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=False,
            pad_token_id=self._tokenizer.eos_token_id,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        # Only the newly generated continuation, not prompt + continuation.
        generated_tokens = output[0][input_token_count:]
        answer = self._tokenizer.decode(generated_tokens, skip_special_tokens=True)

        return LLMResponse(
            answer=answer,
            input_tokens=input_token_count,
            output_tokens=len(generated_tokens),
            latency_ms=latency_ms,
            model_id=self._model_name,
        )
