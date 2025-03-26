import os
from openai import OpenAI
import logging
import tiktoken
from pathlib import Path
from dotenv import load_dotenv
import re
import argparse
from tqdm import tqdm

os.makedirs(f'logs', exist_ok=True)
logging.basicConfig(filename=f"logs/translation.log", level=logging.INFO, format='%(asctime)s %(levelname)s %(module)s - %(funcName)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')


class Translator:
    EXTENSTIONS = {
        "Java": "java",
        "Python": "py"
    }

    def __init__(self, dataset) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("GPT_MODEL")
        self.dataset = dataset

    def __enter__(self):
        logging.info(f"successfully set up openai api key")

        self.main_dir = os.getcwd()
        self.input_dir = Path(self.main_dir).joinpath("dataset", self.dataset)
        self.output_dir = os.path.join(self.main_dir, "output")

        if not self.input_dir.exists():
            logging.error(f"directory {str(self.input_dir)} does not exist. raising FileNotFoundError")
            raise FileNotFoundError(f"Directory {str(self.input_dir)} does not exist.")

        self.out_dir = Path(self.output_dir).joinpath(self.model, self.dataset)
        if not self.out_dir.exists():
            self.out_dir.mkdir(parents=True)

        return self

    def generate_response_with_openai(self, message_log):
        # encoding = tiktoken.encoding_for_model("gpt-4o")
        # num_tokens = len(encoding.encode(message_log[1]["content"]))

        endpoint = "https://models.inference.ai.azure.com"

        client = OpenAI(
            base_url=endpoint,
            api_key=self.api_key,
        )

        response = "exceptional case"
        is_success = False
        max_attempts = 5
        while max_attempts > 0:
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=message_log,
                    temperature=0.7,
                )
                is_success = True
                break
            except Exception as e:
                return "# Token size exceeded."
            except:
                max_attempts -= 1
                continue

        if not is_success:
            return response

        # Find the first response from the chatbot that has text in it (some responses may not have text)
        for choice in response.choices:
            if "text" in choice:
                return choice.text

        # If no response with text is found, return the first response's content (which may be empty)
        return response.choices[0].message.content

    def get_translated_code(self, source, code_as_str, to):
        content = code_as_str + f"\n# Translate the above {source} code to {to}. Print only the {to} code and end with the comment \"End of Code\".\n"

        message = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": content}
        ]
        
        response = self.generate_response_with_openai(message)

        return response.replace(f"```{to.lower()}", "").replace("```", "")

    def translate(self, source, target):
        snippets = list(self.input_dir.joinpath(str(source), "Code").iterdir())

        for source_file in tqdm(snippets, total=len(snippets), bar_format="{desc:<5.5}{percentage:3.0f}%|{bar:10}{r_bar}"):
            code_id = source_file.stem
            code_as_str = source_file.read_text(encoding="utf-8")

            target_dir = self.out_dir.joinpath(f"{source}", f"{target}")
            if not target_dir.exists():
                target_dir.mkdir(parents=True)

            filename_of_translated_code = target_dir.joinpath(f"{code_id}.{Translator.EXTENSTIONS[target]}")

            translated_code_fp = Path(filename_of_translated_code)
            if translated_code_fp.exists():
                continue

            translated_code = self.get_translated_code(source, code_as_str, target)
            translated_code = re.sub('public\s*class\s*.+', 'public class ' + code_id + ' {', translated_code)

            if self.dataset == 'evalplus' and target == 'Java':
                translated_code = 'package com.example;\n' + translated_code

            with open(filename_of_translated_code, "w") as f:
                print(translated_code, file=f)
                    
    def __exit__(self, exception, _, __):
        print(exception)


if __name__ == "__main__":

    load_dotenv()

    parser = argparse.ArgumentParser(description='run translation with GPT-4 with a given dataset and languages')
    parser.add_argument('--dataset', help='dataset to use for code translation. should be one of [codenet,avatar,evalplus]', required=True, type=str)
    parser.add_argument('--source_lang', help='source language to use for code translation. should be one of [Python,Java,C,C++,Go]', required=True, type=str)
    parser.add_argument('--target_lang', help='target language to use for code translation. should be one of [Python,Java,C,C++,Go]', required=True, type=str)
    parser.add_argument('--k', help='The number of highest probability vocabulary tokens to keep for top-k-filtering. Only applies for sampling mode, with range from 1 to 100.', required=True, type=int)
    parser.add_argument('--p', help='Only the most probable tokens with probabilities that add up to top_p or higher are considered during decoding. The valid range is 0.0 to 1.0. 1.0 is equivalent to disabled and is the default. Only applies to sampling mode. Also known as nucleus sampling.', required=True, type=float)
    parser.add_argument('--temperature', help='A value used to warp next-token probabilities in sampling mode. Values less than 1.0 sharpen the probability distribution, resulting in "less random" output. Values greater than 1.0 flatten the probability distribution, resulting in "more random" output. A value of 1.0 has no effect and is the default. The allowed range is 0.0 to 2.0.', required=True, type=float)
    args = parser.parse_args()

    source = args.source_lang
    target = args.target_lang
    with Translator(args.dataset) as translator:
        logging.info(f"translating examples from {source} to {target} using GPT-4 and {args.dataset} dataset")
        translator.translate(source, target)
