from langchain_openai import ChatOpenAI
from llm_guard import scan_prompt, scan_output
from llm_guard.input_scanners import BanSubstrings, TokenLimit
from llm_guard.input_scanners.ban_substrings import stop_file_path
from llm_guard.output_scanners import BanSubstrings as OutputBanSubstrings
from llm_guard.util import read_json_file
import os
from dotenv import load_dotenv


def _banned_substrings():
    phrases = []
    for group in read_json_file(stop_file_path).values():
        phrases.extend(group)
    phrases.extend(
        [
            "ignore previous instructions",
            "ignore all previous instructions",
            "jailbreak",
        ]
    )
    return phrases


class LLMWithGuardrails():
    def __init__(self, modelName="gpt-4.1"):
        load_dotenv()
        self.llm = ChatOpenAI(
            model=modelName,
            temperature=0,
            api_key=os.environ["OPENAI_API_KEY"],
        )
        self.input_scanners = [
            BanSubstrings(substrings=_banned_substrings()),
            TokenLimit(),
        ]
        self.output_scanners = [
            OutputBanSubstrings(substrings=_banned_substrings()),
        ]

    def invoke(self, user_input):
        input_clean, input_results = scan_prompt(
            self.input_scanners, user_input)
        if all(input_results.values()):
            response = self.llm.invoke(input_clean)
            print("----------------------------")
            print(response.content)
            return True
        else:
            invalid = {name: valid for name,
                       valid in input_results.items() if not valid}
            print("----------------------------")
            print(" Blocked due to invalid input:", invalid)
            return False

    def checkOutput(self, prompt, output):
        output_clean, output_results = scan_output(
            self.output_scanners, prompt, output)
        if all(output_results.values()):
            return True, output_clean
        invalid = {name: valid for name,
                   valid in output_results.items() if not valid}
        print("----------------------------")
        print(" Blocked due to invalid output:", invalid)
        return False, output_clean
