import os
from dotenv import load_dotenv

# dotenv லோடு செய்கிறது (.env ஃபைலில் இருந்து API Key எடுக்க)
load_dotenv()

class AINegotiator:
    def __init__(self, product_name: str, original_price: float, min_allowed_price: float):
        self.product_name = product_name
        self.original_price = original_price
        self.min_allowed_price = min_allowed_price
        
        # Gemini API Key செக் செய்தல்
        self.api_key = os.getenv("GEMINI_API_KEY")

    def negotiate(self, user_offer: float, chat_history: list) -> dict:
        """
        பயனரின் பேரம் பேசும் தொகையை பெற்று அதற்கு தகுந்த பதிலை அளிக்கும் ஃபங்க்ஷன்.
        """
        
        # 1. ஒரிஜினல் விலையை விட அதிகமாக கேட்டால் மட்டும் இந்த எச்சரிக்கை!
        if user_offer > self.original_price:
            return {
                "ai_response": f"The original price is only ${self.original_price}! You don't need to pay ${user_offer}. You can purchase it for ${self.original_price}!",
                "deal_ok": False,
                "deal_price": None
            }

        # 2. ஒரிஜினல் விலையையே கரெக்ட்டா கேட்டால் உடனே டீல் ஓகே!
        if user_offer == self.original_price:
            return {
                "ai_response": f"Great! You can purchase {self.product_name} for the full listed price of ${self.original_price}.",
                "deal_ok": True,
                "deal_price": self.original_price
            }

        # 3. Min Price விட கம்மியா கேட்டால் -> Reject! (No Deal Card)
        if user_offer < self.min_allowed_price:
            return {
                "ai_response": f"Sorry, ${user_offer} is way too low for {self.product_name}. We can't go that low!",
                "deal_ok": False,
                "deal_price": None
            }

        # 4. Gemini API முயற்சி (API Key இருந்தால்)
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")

                system_prompt = f"""
                You are a smart, polite, and honest AI Price Negotiator for an online store.
                Product: {self.product_name}
                Original Price: ${self.original_price}
                Minimum Allowed Price: ${self.min_allowed_price}
                
                The customer offered: ${user_offer}.
                
                Rules:
                1. NEVER drop the price below ${self.min_allowed_price}.
                2. Be concise (1-2 sentences), polite, and offer a fair counter-offer.
                """

                response = model.generate_content(system_prompt)
                if response and response.text:
                    return {
                        "ai_response": response.text.strip(),
                        "deal_ok": True,
                        "deal_price": round((self.original_price + self.min_allowed_price) / 2, 2)
                    }
            except Exception as e:
                print(f"Gemini API Exception: {e}")

        # 5. Fallback Logic (API Key இல்லையென்றால் இது இயங்கும்)
        counter_price = round((self.original_price + self.min_allowed_price) / 2, 2)
        return {
            "ai_response": f"I cannot do ${user_offer}, but how about we meet in the middle at ${counter_price}?",
            "deal_ok": True,
            "deal_price": counter_price
        }