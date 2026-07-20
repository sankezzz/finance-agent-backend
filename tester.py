# from app.db.supabase_client import get_supabase
# get_supabase()

# print("supaarrrrr ookkkk")
import os
from dotenv import load_dotenv

load_dotenv()
#uuid - fd87f41c-7a51-4a54-aa29-562d433449a3

# need a whole data flwo whta data goes in each agent adn what comes out and goes in anther one 


from google import genai
api_key=os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

interaction = client.interactions.create(
    model="gemini-3.5-flash",
    input="How does AI work?"
)
print(interaction.output_text)