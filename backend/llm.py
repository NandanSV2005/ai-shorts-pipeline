import os
from backend.config import LLM_PROVIDER, GEMINI_API_KEY, OPENAI_API_KEY, MOCK_PIPELINE

def clean_json_response(text: str) -> str:
    """Strips markdown code block backticks if present in LLM response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text

def generate_text(prompt: str, system_instruction: str | None = None) -> str:
    """
    Unified entry point for text generation. Swaps between Gemini and OpenAI
    based on LLM_PROVIDER in config. Falls back to mock data if MOCK_PIPELINE is True.
    """
    if MOCK_PIPELINE:
        print("[LLM Interface] MOCK_PIPELINE is enabled. Generating simulated response...")
        prompt_lower = prompt.lower()
        
        # Step 01: Topic Generator
        if "generate a single new video topic" in prompt_lower:
            return """
            {
              "title": "The Strange History of the Dynasphere",
              "concept": "The Dynasphere was a bizarre cabin-in-a-wheel monowheel vehicle patented in 1930. We explore its futuristic design, how it worked, and why it ultimately rolled into oblivion.",
              "keywords": ["Dynasphere monowheel", "vintage invention 1930s", "odd retro vehicles", "failed transportation technology"],
              "visual_style": "vintage archival aesthetic, historical sepia tones, quirky mechanics"
            }
            """
        
        # Step 04: Fact Checker
        elif "compare the following script against the research report" in prompt_lower or "fact-check" in prompt_lower:
            return """[
              {
                "claim": "The Dynasphere was patented in 1930.",
                "status": "VERIFIED",
                "explanation": "Confirmed. Dr. Purves patented the Dynasphere in 1930."
              },
              {
                "claim": "It could reach speeds of up to fifty miles per hour.",
                "status": "FLAGGED",
                "explanation": "Dr. Purves claimed it could reach 50 mph, but actual tests only recorded 25-30 mph. Speeds of 50 mph were never verified."
              },
              {
                "claim": "Leonardo da Vinci inspired the concept.",
                "status": "VERIFIED",
                "explanation": "Supported by research showing the monowheel concept was inspired by Leonardo da Vinci sketches."
              }
            ]"""

        # Step 03: Script Writer
        elif "draft a complete, detailed youtube script" in prompt_lower:
            return """[HOOK]
[SCENE: Vintage footage of a giant rolling wheel on a beach]
Have you ever wanted to travel inside a giant rolling wheel? In 1930, one British inventor thought this was the future of transportation.

[BODY]
[SCENE: Historical photographs of Dr. J. A. Purves and his blueprints]
Meet the Dynasphere. Invented by Dr. John Archibald Purves, this ten-foot-tall steel monowheel was designed to revolutionize how we commute. Powered by a small gasoline engine, the driver sat inside the wheel itself.

[SCENE: Old video of the Dynasphere driving on sand]
Dr. Purves was highly optimistic, claiming his monowheel could eventually hit speeds of fifty miles per hour. But in reality, it barely scraped thirty. And it had one major, dizzying flaw.

[SCENE: Close up of the inner wheels and gears mechanism]
When the driver accelerated or slammed on the brakes, the passenger carriage would slide up the interior walls of the wheel, swinging back and forth in an effect known as 'gerbilling'. Imagine being stuck in a spinning dryer at thirty miles per hour!

[SCENE: Newspaper clipping reporting on the failure of the vehicle]
Add to that the fact that steering was nearly impossible, and mud would fly directly into the driver's face, and it's easy to see why the Dynasphere rolled straight into the history books as a failed invention.

[CTA/OUTRO]
[SCENE: Modern graphic showing subscribe button]
What failed invention should we cover next? Let us know in the comments, and don't forget to subscribe for more forgotten history.
"""

        # Step 02: Research Agent
        elif "generate a detailed research report" in prompt_lower:
            return """# Research Report: The Dynasphere Monowheel

## Background
- The Dynasphere was invented by Dr. J. A. Purves from Taunton, England, in 1930.
- The concept was inspired by a sketch made by Leonardo da Vinci, aiming to create a simplified vehicle where the driver sits inside the wheel.

## Technical Specifications & Design
- The vehicle consisted of an outer steel wheel (3 meters / 10 feet high) lined with rubber, and an inner frame.
- The inner carriage was mounted on rollers running along rails on the inside of the wheel.
- Powered by a two-cylinder gasoline engine (or an electric motor in some prototypes) coupled with a three-speed gearbox.
- Steering was achieved by the driver leaning their body or shifting the gears/gearing to tilt the outer wheel.

## Claims & Performance
- Dr. Purves claimed it was the vehicle of the future and could eventually reach speeds of up to 50 miles per hour (80 km/h).
- In actual tests on Brean Sands and at Brooklands, it reached top speeds of approximately 25-30 miles per hour.
- A smaller electric version was also built.

## Why it Failed
- "Gerbilling": When accelerating or braking, the inner carriage tended to roll up the inside of the wheel instead of staying level, causing a dizzying motion similar to a hamster in a wheel.
- steering was extremely difficult and imprecise.
- The open sides exposed the driver and passengers to dirt, rain, and mud thrown up by the wheel.
- Braking was highly unstable.
"""

        # Step 10: SEO Generator
        elif "seo" in prompt_lower or "tags" in prompt_lower:
            return """{
              "title": "The Bizarre 1930 Monowheel That Failed: The Dynasphere",
              "description": "Step back in time to 1930 to explore the Dynasphere—a giant rolling wheel designed to replace the car. Learn how it worked and why it failed!",
              "tags": ["Dynasphere", "failed technology", "forgotten inventions", "retro tech", "history of transport", "monowheel"]
            }"""
        
        else:
            return "This is a generic mock response from the LLM pipeline."

    # Active LLM Logic

    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in the environment or .env file.")
        
        import google.genai as genai
        from google.genai import types
        
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
            max_output_tokens=8192,
            system_instruction=system_instruction
        )
        
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=config
        )
        
        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")
        return response.text

    elif LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in the environment or .env file.")
        
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
        )
        content = response.choices[0].message.content  # type: ignore
        if not content:
            raise RuntimeError("OpenAI returned an empty response.")
        return content

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}. Supported providers are 'gemini' and 'openai'.")
