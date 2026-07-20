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
        
        # Helper to get current run date directory from CLI args
        import sys
        from datetime import datetime
        def get_active_date() -> str:
            date_str = datetime.now().strftime("%Y-%m-%d")
            for idx, arg in enumerate(sys.argv):
                if arg == "--date" and idx + 1 < len(sys.argv):
                    date_str = sys.argv[idx + 1]
                    break
            return date_str

        # Pool of distinct topics for mock series episodes
        MOCK_TOPICS = [
            {
                "title": "The Strange History of the Dynasphere",
                "concept": "The Dynasphere was a bizarre cabin-in-a-wheel monowheel vehicle patented in 1930. We explore its futuristic design, how it worked, and why it ultimately rolled into oblivion.",
                "keywords": ["Dynasphere monowheel", "vintage invention 1930s", "odd retro vehicles", "failed transportation technology"],
                "visual_style": "vintage archival aesthetic, historical sepia tones, quirky mechanics"
            },
            {
                "title": "The Ford Flivver Fail",
                "concept": "Henry Ford wanted to make an 'everyman's airplane' called the Flivver. We look at its high-profile development, safety challenges, and the crash that shut down the project.",
                "keywords": ["Ford Flivver airplane", "Henry Ford aviation", "historic small aircraft", "failed flight technology"],
                "visual_style": "retro hangar look, black and white newsreels, early aviation vibe"
            },
            {
                "title": "The Apple Pippin Disaster",
                "concept": "In the mid-90s, Apple tried to conquer the living room with the Pippin game console. We explore how its high price and lack of games led to a swift defeat by PlayStation.",
                "keywords": ["Apple Pippin console", "retro gaming fail", "Apple 1990s history", "forgotten video game systems"],
                "visual_style": "90s tech neon, retro game graphics, high-contrast digital"
            },
            {
                "title": "The Sinclair C5 Flop",
                "concept": "The Sinclair C5 was a futuristic electric trike launched in 1985. We examine the massive hype, its dangerous low-profile design, and why consumers refused to drive it.",
                "keywords": ["Sinclair C5 electric trike", "80s electric vehicles", "Clive Sinclair inventions", "failed urban transport"],
                "visual_style": "80s commercial aesthetic, bright plastic textures, futuristic retro styling"
            },
            {
                "title": "The Pawnee Flying Platform",
                "concept": "The Hiller VZ-1 Pawnee was a flying platform designed for the US military where pilots steered by leaning. We explore its hover mechanics and why it was abandoned.",
                "keywords": ["Hiller VZ-1 Pawnee", "flying platform hover", "military prototype aircraft", "odd cold war tech"],
                "visual_style": "military blueprint style, grainy cold war footage, industrial metal tones"
            }
        ]

        # Try to extract the title from the prompt
        title = None
        for line in prompt.splitlines():
            if line.startswith("Topic Title:"):
                title = line.replace("Topic Title:", "").strip()
                break
        if not title:
            try:
                from backend.config import OUTPUTS_DIR
                date_str = get_active_date()
                topic_file = OUTPUTS_DIR / date_str / "topic.json"
                if topic_file.exists():
                    import json
                    with open(topic_file, "r", encoding="utf-8") as f:
                        title = json.load(f).get("title")
            except Exception:
                pass

        # Step 01: Topic Generator
        if "generate a single new video topic" in prompt_lower:
            date_str = get_active_date()
            series = None
            episode = None
            try:
                from backend.config import OUTPUTS_DIR
                import json
                metadata_file = OUTPUTS_DIR / date_str / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        series = meta.get("series")
                        episode = meta.get("episode")
            except Exception:
                pass
                
            hash_key = date_str
            if series:
                hash_key += f"_{series}"
            if episode is not None:
                hash_key += f"_ep{episode}"
                
            if episode is not None:
                topic_index = (episode - 1) % len(MOCK_TOPICS)
            else:
                import hashlib
                h = int(hashlib.md5(hash_key.encode()).hexdigest(), 16)
                topic_index = h % len(MOCK_TOPICS)
                
            selected_topic = MOCK_TOPICS[topic_index]
            import json
            return json.dumps(selected_topic, indent=2, ensure_ascii=False)
        
        # Step 04: Fact Checker
        elif "compare the following script against the research report" in prompt_lower or "fact-check" in prompt_lower:
            display_title = title or "The Dynasphere"
            return f"""[
              {{
                "claim": "The prototype is named the {display_title}.",
                "status": "VERIFIED",
                "explanation": "Verified from research records."
              }},
              {{
                "claim": "It was highly successful in all early tests.",
                "status": "FLAGGED",
                "explanation": "Exaggeration: documented tests showed stability and control issues during operation."
              }}
            ]"""
        # Step 03: Script Writer
        elif "draft a complete youtube script" in prompt_lower or "script to revise" in prompt_lower:
            display_title = title or "The Dynasphere"
            return f"""[HOOK]
[SCENE: Vintage footage matching the style of {display_title}]
Have you ever wanted to learn about {display_title}? In this episode, we explore the fascinating history of this forgotten invention.

[BODY]
[SCENE: Historical blueprints and blueprints showing details of {display_title}]
Meet {display_title}. Designed to revolutionize its field, it was highly anticipated by its creators.

[SCENE: Old footage demonstrating {display_title} in action]
People were extremely optimistic, claiming it could change the future of technology. But in reality, it had some major flaws.

[SCENE: Close up of the mechanical details and problematic features]
Add to that the fact that it was difficult to steer, expensive to manufacture, and prone to breaking down. It's easy to see why it rolled straight into the history books.
[SPLIT POINT]
[SCENE: Summary collage of the invention's legacy]
Ultimately, {display_title} stands as a testament to human ingenuity and the trials of innovation.

[CTA/OUTRO]
[SCENE: Modern graphic showing subscribe button]
What failed invention should we cover next? Let us know in the comments, and don't forget to subscribe for more forgotten history.
"""

        # Step 02: Research Agent
        elif "generate a detailed research report" in prompt_lower:
            display_title = title or "The Dynasphere"
            return f"""# Research Report: {display_title}
            
## Background
- The {display_title} was a pioneering historical concept developed in the 20th century.
- Developed by ambitious inventors aiming to simplify transit and create the ultimate vehicle.

## Technical Specifications & Design
- Features a unique mechanics assembly with custom power drives and steering dynamics.
- Powered by a compact motor and built using experimental industrial materials of the era.

## Claims & Performance
- Initial testing showed great promise, with inventors claiming it was highly efficient and fast.
- Documented testing revealed significant engineering limitations during operation.

## Why it Failed
- Main causes of abandonment included steering issues, safety concerns, and high production costs.
- The project was eventually shelved, becoming a classic example of fascinating but failed technology.
"""

        # Step 10: SEO Generator
        elif "seo" in prompt_lower or "tags" in prompt_lower:
            display_title = title or "The Dynasphere"
            return f"""{{
              "title": "The Bizarre Story of {display_title}: A Forgotten Innovation",
              "description": "Step back in time to explore the fascinating history of {display_title}. Learn how it worked, the high hopes, and why it ultimately failed!",
              "tags": ["{display_title}", "failed technology", "forgotten inventions", "retro tech", "history of transport"]
            }}"""
        
        else:
            return "This is a generic mock response from the LLM pipeline."

    # Active LLM Logic

    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in the environment or .env file.")
        
        import google.genai as genai
        from google.genai import types
        import time
        
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
            max_output_tokens=8192,
            system_instruction=system_instruction
        )
        
        max_retries = 3
        backoff_sec = 2.0
        response = None
        for attempt in range(max_retries + 1):
            try:
                response = client.models.generate_content(
                    model="gemini-3.5-flash",
                    contents=prompt,
                    config=config
                )
                break
            except Exception as e:
                err_str = str(e).lower()
                if ("429" in err_str or "resource_exhausted" in err_str or "quota" in err_str) and attempt < max_retries:
                    print(f"[LLM Interface] Gemini rate limit hit (429/quota). Retrying in {backoff_sec} seconds (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(backoff_sec)
                    backoff_sec *= 2
                else:
                    raise e
        
        if not response or not response.text:
            raise RuntimeError("Gemini returned an empty response.")
        return response.text

    elif LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in the environment or .env file.")
        
        from openai import OpenAI
        import time
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        max_retries = 3
        backoff_sec = 2.0
        response = None
        for attempt in range(max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.7,
                )
                break
            except Exception as e:
                err_str = str(e).lower()
                if ("429" in err_str or "rate" in err_str or "quota" in err_str) and attempt < max_retries:
                    print(f"[LLM Interface] OpenAI rate limit hit (429/quota). Retrying in {backoff_sec} seconds (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(backoff_sec)
                    backoff_sec *= 2
                else:
                    raise e
                    
        content = response.choices[0].message.content  # type: ignore
        if not content:
            raise RuntimeError("OpenAI returned an empty response.")
        return content

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}. Supported providers are 'gemini' and 'openai'.")
