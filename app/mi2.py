import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from huggingface_hub import login

login("hf_")

def generate_plan(model_name, prompt, temperature):

    # Load the tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
                    model_name
                )
    
    
    # Load the model
    model = AutoModelForCausalLM.from_pretrained(
                model_name,
                dtype=torch.bfloat16,
                device_map= "auto"
            )
    
    messages = [
        {
            "role": "user",
            "content": prompt
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
        temperature= temperature
    )

    response = tokenizer.decode(
        outputs[0][inputs.shape[-1]:],
        skip_special_tokens=True
    )

    return response 

