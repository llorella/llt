from openai import OpenAI
import time

client = OpenAI()

def get_completion(messages: list[dict[str, str]], args: dict) -> dict:
    start_time = time.time()
    completion = client.chat.completions.create(
        messages=messages,
        model=args.model,
        temperature=args.temperature,
        stream=True)

    collected_chunks = []
    collected_messages = []
    for chunk in completion:
        chunk_time = time.time() - start_time
        collected_chunks.append(chunk)
        chunk_message = chunk.choices[0].delta.content
        print(chunk_message or "\n", end="")
        collected_messages.append(chunk_message)
        
    collected_messages = [m for m in collected_messages if m is not None]
    full_reply_content = ''.join(collected_messages)
    
    return {'role': 'assistant', 'content': full_reply_content}