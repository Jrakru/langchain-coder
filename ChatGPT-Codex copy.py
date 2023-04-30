import os
import sys
import subprocess
import time
import openai
from io import StringIO
from dotenv import load_dotenv
import langchain.agents as lc_agents
from langchain.llms import OpenAI as LangChainOpenAI

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


class PythonREPL:
    """Simulates a standalone Python REPL."""

    def __init__(self):
        pass

    def run(self, command: str) -> str:
        """Run command and returns anything printed."""
        old_stdout = sys.stdout
        sys.stdout = mystdout = StringIO()
        try:
            exec(command, globals())
            sys.stdout = old_stdout
            output = mystdout.getvalue()
        except Exception as e:
            sys.stdout = old_stdout
            output = str(e)
        return output

# Define method to remove any special characters from the generated code


def remove_special_characters(language, code):
    # check if code has ``` then remove it
    if "```" in code:
        code = code.replace("```", "")

    if language == "Python":
        code = code.replace(">>>", "")
        code = code.replace("...", "")
        code = code.replace("python", "")

    if language == "C" or language == "C++":
        code = code.replace("$", "")
        code = code.replace("gcc", "")
        code = code.replace("g++", "")
        code = code.replace("./", "")

    if language == "Javascript":
        code = code.replace(">", "")

    return code


def run_code(language, code):

    # Remove any special characters from the generated code.
    code = remove_special_characters(language, code)

    if language == "Python":
        with open("temp_code.py", "w") as f:
            f.write(code)

        output = subprocess.run(
            ["python", "temp_code.py"], capture_output=True, text=True)
        return output.stdout + output.stderr

    elif language == "C" or language == "C++":
        ext = ".c" if language == "C" else ".cpp"
        with open("temp_code" + ext, "w") as f:
            f.write(code)

        compile_output = subprocess.run(["gcc" if language == "C" else "g++", "-o",
                                        "temp_executable", "temp_code" + ext], capture_output=True, text=True)
        if compile_output.returncode != 0:
            return compile_output.stderr

        run_output = subprocess.run(
            ["./temp_executable"], capture_output=True, text=True)
        return run_output.stdout + run_output.stderr

    elif language == "Javascript":
        with open("temp_code.js", "w") as f:
            f.write(code)

        output = subprocess.run(
            ["node", "temp_code.js"], capture_output=True, text=True)
        return output.stdout + output.stderr

    else:
        return "Unsupported language."


def run_query(query, model_kwargs, max_iterations):
    llm = LangChainOpenAI(**model_kwargs)
    python_repl = lc_agents.Tool("Python REPL", PythonREPL().run,
                                 "A Python shell. Use this to execute python commands.")
    tools = [python_repl]
    agent = lc_agents.initialize_agent(tools, llm, agent="zero-shot-react-description",
                                       model_kwargs=model_kwargs, verbose=True, max_iterations=max_iterations)
    response = agent.run(query)
    return response


# Create method for running the chat with arguments as prompt and language
def execute_chat(prompt, language):
    chat_completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": f"Write a {language} code full source code including main method for the following prompt: {prompt}."},
            {"role": "system", "content": "Generate code in raw text format only. Your response should consist of only code and nothing else. Please do not provide any explanations or descriptions of the code,"
             "and avoid using any special characters or formatting that might interfere with copying and pasting the code into a programming environment."
             "Your code should be complete and functional, and should accomplish the task specified in the prompt."
             ".And if there is input required dont ask user from input just use some random input."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1000,
        temperature=0.7,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )
    return chat_completion.choices[0].message.content.strip()


# define main method
if __name__ == "__main__":
    languages = ["C", "C++", "Python", "Javascript"]
    print("Select a programming language: ")
    for i, lang in enumerate(languages):
        print(f"{i + 1}. {lang}")

    lang_choice = int(
        input("Enter the number corresponding to your choice: ")) - 1
    language = languages[lang_choice]
    prompt = input("Enter a prompt: ")
    generated_code = execute_chat(prompt, language)

    print("\nRunning the generated code...\n")
    output = run_code(language, generated_code)
    print("Output:", output)

    if "error" in output.lower():
        model_kwargs = {"temperature": 0.0,
                        "model": "text-davinci-003", "api_key": openai.api_key}
        max_iterations = 50
        fixed_code = generated_code
        iteration = 1

        with open(f"{language}_fix_attempts.log", "w") as log_file:
                log_file.write(
                    f"Iteration {iteration}:\nCode:\n{fixed_code}\nOutput:\n{output}\n\n")

                while "error" in output.lower() and iteration < max_iterations:
                    iteration += 1
                    query = f"Fix the error in the following {language} code:\n{fixed_code}\nError message:\n{output} and give the full source code including main method."
                    response = run_query(query, model_kwargs, max_iterations)
                    #response = execute_chat(query, language)
                    fixed_code = remove_special_characters(response.strip())

                    output = run_code(language, fixed_code)
                    print(f"Iteration {iteration}:")
                    print("Fixed code:", fixed_code)
                    print("Output:", output)

                    log_file.write(
                        f"Iteration {iteration}:\nCode:\n{fixed_code}\nOutput:\n{output}\n\n")
                    # Add delay to avoid hitting the API rate limit
                    #time.sleep(2.5)

        print("Final code:", fixed_code)
        print("Final output:", output)
