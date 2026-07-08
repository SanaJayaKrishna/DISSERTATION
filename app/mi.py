import json
import torch

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM
)

model_name = "meta-llama/Llama-3.1-8B-Instruct"
model_name = "google/gemma-4-E4B-it"
model_name = 

def generate_plan():

    # Load the tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
                    model_name
                )
    
    
    # Load the model
    model = AutoModelForCausalLM.from_pretrained(
                model_name,
                dtype=torch.bfloat16,
                device_map="cpu"
            )
    
    messages = [
        {
            "role": "user",
            "content": "Tell me a technical joke."
        }
    ]

    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt"
    )

    # if not isinstance(inputs, torch.Tensor):
    #     inputs = torch.tensor(inputs)

    if hasattr(inputs, "input_ids"):
        inputs = inputs.input_ids

    inputs = inputs.to(model.device)

    outputs = model.generate(
        inputs,
        max_new_tokens=200,
        do_sample=True,
        temperature=0.7
    )

    response = tokenizer.decode(
        outputs[0][inputs.shape[-1]:],
        skip_special_tokens=True
    )

    return response 

