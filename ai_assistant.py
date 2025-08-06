# ai_assistant.py

from openai import OpenAI
import os

class AITravelAssistant:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_itinerary(self, destination):
        prompt = f"""
        Create a detailed, day-by-day travel itinerary for {destination.city}, {destination.country}
        from {destination.start_date} to {destination.end_date}.
        Budget: ${destination.budget:,.2f} USD.
        Activities of interest: {', '.join(destination.activities)}.
        Please make sure the itinerary is realistic for the given dates and budget.
        Include suggestions for morning, afternoon, and evening activities.
        """
        return self._get_ai_response(prompt, "itinerary")

    def generate_budget_tips(self, destination):
        prompt = f"""
        Provide specific budget-saving tips and travel advice for a trip to {destination.city}, {destination.country}
        with a budget of ${destination.budget:,.2f} USD.
        Consider activities like: {', '.join(destination.activities)}.
        Focus on practical advice for accommodations, food, transportation, and activities.
        """
        return self._get_ai_response(prompt, "budget tips")

    def _get_ai_response(self, prompt, context):
        try:
            print(f"\nGenerating {context} for {prompt.splitlines()[1].strip()}... This may take a moment.")
            chat_completion = self.client.chat.completions.create(
                model="gpt-3.5-turbo", # You can use a newer model if available and budget allows, e.g., "gpt-4o"
                messages=[
                    {"role": "system", "content": "You are a helpful travel assistant. Provide clear and concise travel information."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000 # Adjust based on desired length of response
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Error communicating with OpenAI API for {context}: {e}")
            print("Please ensure your API key is correct and you have sufficient credits.")
            return "Could not generate AI response."