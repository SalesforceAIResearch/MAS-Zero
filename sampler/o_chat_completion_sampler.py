import time
from typing import Any

import openai
from openai import OpenAI

from dataclasses import dataclass, field
from typing import Any

Message = dict[str, Any]  # keys role, content
MessageList = list[Message]


class SamplerBase:
    """
    Base class for defining a sampling model, which can be evaluated,
    or used as part of the grading process.
    """

    def __call__(self, message_list: MessageList) -> str:
        raise NotImplementedError


@dataclass
class EvalResult:
    """
    Result of running an evaluation (usually consisting of many samples)
    """

    score: float | None  # top-line metric
    metrics: dict[str, float] | None  # other metrics
    htmls: list[str]  # strings of valid HTML
    convos: list[MessageList]  # sampled conversations


@dataclass
class SingleEvalResult:
    """
    Result of evaluating a single sample
    """

    score: float | None
    metrics: dict[str, float] = field(default_factory=dict)
    html: str | None = None
    convo: MessageList | None = None  # sampled conversation


class Eval:
    """
    Base class for defining an evaluation.
    """

    def __call__(self, sampler: SamplerBase) -> EvalResult:
        raise NotImplementedError


class OChatCompletionSampler(SamplerBase):
    """
    Sample from OpenAI's chat completion API for o series models
    """

    def __init__(
        self,
        *,
        reasoning_effort: str | None = None,
        model: str = "o1-mini",
    ):
        self.api_key_name = "OPENAI_API_KEY"
        self.client = OpenAI()
        # using api_key=os.environ.get("OPENAI_API_KEY")  # please set your API_KEY
        self.model = model
        self.image_format = "url"
        self.reasoning_effort = reasoning_effort

    def _handle_image(
        self, image: str, encoding: str = "base64", format: str = "png", fovea: int = 768
    ):
        new_image = {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/{format};{encoding},{image}",
            },
        }
        return new_image

    def _handle_text(self, text: str):
        return {"type": "text", "text": text}

    def _pack_message(self, role: str, content: Any):
        return {"role": str(role), "content": content}

    def __call__(self, message_list: MessageList) -> str:
        #TODO: tempreture cannot be set
        trial = 0
        while True:
            try:
                for message_id, message in enumerate(message_list):
                    if type(message['content']) != str:
                        message_list[message_id]['content'] = str(message['content'])
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=message_list,
                    reasoning_effort=self.reasoning_effort,
                    response_format={"type": "json_object"}

                )
                return response.choices[0].message.content, response.usage
            # NOTE: BadRequestError is triggered once for MMMU, please uncomment if you are reruning MMMU
            except openai.BadRequestError as e:
                print("Bad Request Error", e)
                return ""
            except Exception as e:
                exception_backoff = 2**trial  # expontial back off
                print(
                    f"Rate limit exception so wait and retry {trial} after {exception_backoff} sec",
                    e,
                )
                time.sleep(exception_backoff)
                trial += 1
            # unknown error shall throw exception
