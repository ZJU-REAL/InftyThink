import re

PROMPT_PREFIX = "User:"
PROMPT_SUFFIX = "Assistant:"


MAX_EPOCHS = 50

def inf_thought_check_completion_status(completion) -> bool:
    return '<summary>' not in completion


def inf_thought_process_prompts(prompt) -> str:
    if '<summary>' not in prompt:
        return prompt
    else:
        try:
            instruction, think, summary = re.search(r'(.+)<think>\n(.+)\n</think>\n<summary>\n(.+)\n</summary>', prompt, re.S).groups()
            if '<history>' in instruction:
                instruction = re.sub(r'<history>.+</history>', '', instruction, flags=re.S)
            return instruction + '<history>' + summary + '</history>'
        except Exception:
            if '<think>' not in prompt:
                return prompt
            else:
                instruction, think = re.search(r'(.+)<think>\n(.+)', prompt, re.S).groups()
                return instruction


if __name__ == '__main__':
    import vllm

    model_path = "<<<<<<model_path_here>>>>>"
    question = "Let $ABC$ be a triangle inscribed in circle $\\omega$. Let the tangents to $\\omega$ at $B$ and $C$ intersect at point $D$, and let $\\overline{AD}$ intersect $\\omega$ at $P$. If $AB=5$, $BC=9$, and $AC=10$, $AP$ can be written as the form $\\frac{m}{n}$, where $m$ and $n$ are relatively prime integers. Find $m + n$."
    prompt = f"{PROMPT_PREFIX}{question}{PROMPT_SUFFIX}"

    model = vllm.LLM(model_path, tensor_parallel_size=1)
    sampling_params = vllm.SamplingParams(n=1, max_tokens=8192, temperature=0.7, top_p=0.95, skip_special_tokens=False)

    for epoch in range(MAX_EPOCHS):
        print(f"===== Iteration {epoch} =====\n\n")
        print("Start of input text >>>>> \n")
        print(prompt)
        print("<<<<< End of input text\n\n")

        generated_text = model.generate(prompt, sampling_params)[0].outputs[0].text
        print("Start of output text >>>>> \n")
        print(generated_text)
        print("<<<<< End of output text\n\n")


        if inf_thought_check_completion_status(generated_text):
            break
        prompt += generated_text
        prompt = inf_thought_process_prompts(prompt)

