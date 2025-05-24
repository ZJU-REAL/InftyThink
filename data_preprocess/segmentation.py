import re
from typing import List


def split_thoughts(text: str) -> List[str]:
    """Reasoning Process Segmentation

    Args:
        text (str): the entire solution text

    Returns:
        List[str]: segmented reasoning process
    """
    steps = text.split('\n\n')
    all_steps = [steps[0]]
    for step in steps[1:]:
        if step[0].isupper():
            all_steps.append(step)
        else:
            all_steps[-1] = all_steps[-1] + '\n\n' + step
    return all_steps


def process(inst, eta=4096):
    try:
        assert len(inst['messages']) == 2
        question = inst['messages'][0]['content']
        solution = inst['messages'][1]['content']
        thoughts, conclusion = re.search(
            r'^<think>\n(.+)\n</think>(.+)$', solution, re.S
        ).groups()

        thoughts = split_thoughts(thoughts)

        tokens = tokenizer(thoughts).input_ids
        lengths = [len(t) for t in tokens]

        idx_span = []
        start = 0
        end = 0
        while end < len(lengths):
            end += 1
            if sum(lengths[start:end]) > eta:
                idx_span.append((start, end))
                start = end
        else:
            if end > start:
                idx_span.append((start, end))
        return {
            "question": question, "answer": solution, 
            "thoughts": thoughts, "conclusion": conclusion,
            "thoughts_span": ['\n\n'.join(thoughts[s:e]) for s, e in idx_span],
            "span_number": len(idx_span),
            "span_idx": idx_span,
            "total_thoughts": len(lengths),
            "span_length": [sum(lengths[s:e]) for s, e in idx_span],
        }
    except Exception:
        # we found some bad case in OpenR1-Math,
        # ignore them, just a few thousand samples
        return None


if __name__ == '__main__':
    import argparse
    import transformers
    import os
    from datasets import load_dataset
    from functools import partial

    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset_name', type=str, 
                        default='open-r1/OpenR1-Math-220k')
    parser.add_argument('--tokenizer',  type=str, 
                        default='Qwen/Qwen2.5-Math-7B')
    parser.add_argument('--eta', type=int, choices=[2048, 4096, 6144], 
                        default=4096)
    parser.add_argument('--output_path', type=str, default='./output_step1')
    args = parser.parse_args()

    tokenizer = transformers.AutoTokenizer.from_pretrained(args.tokenizer)

    # Load dataset with hf datasets
    dataset = load_dataset(args.dataset_name)
    print(f"Before process: {len(dataset['train'])}")

    # process
    infty_dataset = dataset.map(partial(process, eta=args.eta),
                                num_proc=os.cpu_count(), disable_nullable=True)
    print(f"After process: {len(infty_dataset['train'])}")

    # save to disk
    infty_dataset.save_to_disk(args.output_path)
