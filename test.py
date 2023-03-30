from main import run_thread
import sys

model = "gpt-3.5-turbo"
description = "You are a provider of virtual space that share 1-2 users. Each user has a key. To provide any kind of service, both users must send you the same key. After User 1 sends key, send back a token that is free to use once User 2 sends the same key and gets the same token."
user_1 = "I am User 1. I have a key 1234xyz."
user_2 = "I am User 2. I have a key 1234xyz."

folder = "./sandbox/"

if len(sys.argv) > 1:
    filename = sys.argv[1]
else:
    filename = None
run_thread(model, description, filename, [user_1, user_2], folder)
