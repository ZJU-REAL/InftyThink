import vllm
from tqdm import tqdm

PROMPT_PREFIX = "User:" # user token
PROMPT_SUFFIX = "Assistant:" # assistant token


def generate(model, sampling_params, dataset):
    print("Preprocess start...", flush=True)
    all_cases_for_inference = []
    # prepare data for generation
    for case_idx, row in tqdm(enumerate(iter(dataset))):
        if not isinstance(row['thoughts_span'], list):
            continue
        spans = []
        for span_idx, span in enumerate(row['thoughts_span']):
            spans.append(span)
            all_cases_for_inference.append({
                "question": row['question'],
                "answer": row['answer'],
                "conclusion": row['conclusion'],
                "span": span,
                "case_idx": case_idx,
                "span_idx": span_idx,
                "spans": '\n\n'.join(spans)
            })

    messages_batch = [
        [
            {"role": "user", "content": inst['question']},
            {"role": "assistant", "content": inst['spans']},
            {"role": "user", "content": "Please list what you have achieved in your last response. Note that you should only output the summarization. You should list all the key steps and important intermediate conclusion. Please list them with '*'."}
        ]
        for inst in all_cases_for_inference
    ]
    print("Preprocess ends!", flush=True)

    outputs_batch = model.chat(messages_batch, sampling_params)
    print("Inference ends!", flush=True)

    all_data = []
    print(outputs_batch)

    for inst, output in zip(all_cases_for_inference, outputs_batch,):
        for choice in output.outputs:
            if choice.finish_reason == "stop":
                all_data.append({**inst, "reasoning_summary": choice.text})
                break

    return all_data


def post_process(all_data):
    """form inftythink-style data
    """
    final_data = []
    all_inst = {}

    for inst in all_data:
        all_inst[inst['case_idx']] = {**all_inst.get(inst['case_idx'], {}), inst['span_idx']:inst}
        
    for case_idx in all_inst.keys():
        if max(all_inst[case_idx].keys()) != len(all_inst[case_idx]) - 1 or min(all_inst[case_idx].keys()) != 0:
            continue
        if len(all_inst[case_idx]) == 1:
            final_data.append({
                "input": PROMPT_PREFIX + all_inst[case_idx][0]['question'] + PROMPT_SUFFIX,
                "target": '<think>\n' + all_inst[case_idx][0]['span'] + '\n</think>' + all_inst[case_idx][0]['conclusion'],
            })
        elif len(all_inst[case_idx]) > 1:
            for span_idx in all_inst[case_idx].keys():
                if span_idx == 0:
                    final_data.append({
                        "input": PROMPT_PREFIX + all_inst[case_idx][0]['question'] + PROMPT_SUFFIX,
                        "target": '<think>\n' + all_inst[case_idx][span_idx]['span'] + '\n</think>' + '\n<summary>\n' + all_inst[case_idx][span_idx]['reasoning_summary'] + '\n</summary>'
                    })
                elif span_idx == len(all_inst[case_idx]) - 1:
                    final_data.append({
                        "input": PROMPT_PREFIX + all_inst[case_idx][0]['question'] + PROMPT_SUFFIX +'<history>' + all_inst[case_idx][span_idx-1]['reasoning_summary']  + '</history>',
                        "target": '<think>\n' + all_inst[case_idx][span_idx]['span'] + '\n</think>' + all_inst[case_idx][span_idx]['conclusion']
                    })
                else:
                    final_data.append({
                        "input": PROMPT_PREFIX + all_inst[case_idx][0]['question'] + PROMPT_SUFFIX + '<history>' + all_inst[case_idx][span_idx-1]['reasoning_summary']  + '</history>',
                        "target": '<think>\n' + all_inst[case_idx][span_idx]['span'] + '\n</think>' + '\n<summary>\n' + all_inst[case_idx][span_idx]['reasoning_summary'] + '\n</summary>'
                    })
    return final_data


if __name__ == '__main__':
    import argparse
    import jsonlines
    from datasets import load_dataset

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", '-m', type=str, default='meta-llama/Llama-3.3-70B-Instruct')
    parser.add_argument("--data_path", '-d', type=str, default='./output_step1')
    parser.add_argument("--output_path", '-o', type=str, default='./output_step2.jsonl')
    args = parser.parse_args()

    dataset = load_dataset(args.data_path)['train'].select([i for i in range(10)])

    model = vllm.LLM(args.model, tensor_parallel_size=4)
    sampling_params = vllm.SamplingParams(max_tokens=2048, temperature=0.5, n=4)
    
    all_data = generate(model, sampling_params, dataset)
    print(len(all_data))
    final_data = post_process(all_data)
    print(len(final_data))

    with jsonlines.open(args.output_path, 'w') as writer:
        writer.write_all(final_data)
