import os
import dotenv

dotenv.load_dotenv()


test_env = {
    "url":os.getenv("TEST_URL"),
    "content_type":"application/json",
    "tenant_id":"1",
}

if __name__ == "__main__":
    print(test_env)